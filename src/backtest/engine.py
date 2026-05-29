"""
Motor de Backtesting Event-Driven.
"""
import pandas as pd
from typing import Dict, Any, List
from src.backtest.portfolio import Portfolio
from src.core.logger import get_logger

logger = get_logger(__name__)

class BacktestEngine:
    """
    Simula el paso del tiempo bar por bar (Event-Driven) para evitar
    totalmente el look-ahead bias y asegurar un backtest realista.
    """
    
    def __init__(self, portfolio: Portfolio, commission_pct: float = 0.00007, slippage_pips: float = 0.5):
        self.portfolio = portfolio
        self.commission_pct = commission_pct
        self.slippage_pips = slippage_pips 
        
    def run(self, data: pd.DataFrame, signals: pd.Series, symbol: str) -> None:
        """
        Ejecuta el backtest bar a bar.
        
        Args:
            data: DataFrame con datos OHLCV. Debe tener 'close'.
            signals: Series con las señales generadas (1, -1, 0) indexadas igual que data.
            symbol: El símbolo operado.
        """
        logger.info(f"Iniciando backtest para {symbol} ({len(data)} barras)...")
        
        # Horizonte temporal de la triple barrera
        horizon = 24
        
        # Iterar barra por barra simulando eventos
        for i in range(len(data)):
            current_bar = data.iloc[i]
            current_signal = signals.iloc[i]
            
            # Extraer tiempo
            if isinstance(data.index, pd.DatetimeIndex):
                current_time = data.index[i]
            elif 'time' in data.columns:
                current_time = current_bar['time']
            else:
                current_time = pd.Timestamp.now()
                
            price = current_bar['close']
            high = current_bar['high'] if 'high' in current_bar else price
            low = current_bar['low'] if 'low' in current_bar else price
            
            # Revisar si las posiciones existentes tocan TP/SL o alcanzan el horizonte
            if symbol in self.portfolio.positions:
                pos = self.portfolio.positions[symbol]
                pos.bars_held += 1
                
                close_signal = False
                exit_price = price
                
                if pos.direction == 1:
                    if pos.tp_price and high >= pos.tp_price:
                        close_signal = True
                        exit_price = pos.tp_price
                    elif pos.sl_price and low <= pos.sl_price:
                        close_signal = True
                        exit_price = pos.sl_price
                elif pos.direction == -1:
                    # Para cortos, TP es abajo y SL es arriba
                    if pos.tp_price and low <= pos.tp_price:
                        close_signal = True
                        exit_price = pos.tp_price
                    elif pos.sl_price and high >= pos.sl_price:
                        close_signal = True
                        exit_price = pos.sl_price
                        
                # Condición de Tiempo (Horizonte)
                if not close_signal and pos.bars_held >= horizon:
                    close_signal = True
                    exit_price = price # Cierra al cierre actual
                    
                # Si otra señal contraria viene del modelo, también cerramos
                if not close_signal and current_signal in [1, -1] and current_signal != pos.direction:
                    close_signal = True
                    exit_price = price
                    
                if close_signal:
                    # Forzar el cierre enviando señal 0 a la ejecución, pero al precio de salida simulado
                    self.portfolio.execute_trade(symbol, 0, exit_price, current_time, pos.size)

            # Si después de las comprobaciones no hay posición, y hay señal nueva, abrir
            if symbol not in self.portfolio.positions and current_signal in [1, -1]:
                from src.core.config_manager import ConfigManager
                config = ConfigManager()
                lot_sizes = config.get("backtest.lot_sizes", {})
                size = lot_sizes.get(symbol, lot_sizes.get("default", 100000.0))
                
                # Calcular TP y SL usando un ATR aproximado
                # Usamos la volatilidad de los últimos 14 periodos
                if i >= 14:
                    atr = data['close'].iloc[i-14:i+1].std()
                else:
                    atr = price * 0.005 # Fallback (0.5% del precio)
                    
                if atr < 1e-5: atr = price * 0.005
                
                if current_signal == 1:
                    entry_price = price * (1 + (self.slippage_pips / 10000.0))
                    tp_price = entry_price + (atr * 2.0)
                    sl_price = entry_price - (atr * 1.0)
                else:
                    entry_price = price * (1 - (self.slippage_pips / 10000.0))
                    tp_price = entry_price - (atr * 2.0)
                    sl_price = entry_price + (atr * 1.0)
                
                comision = entry_price * size * self.commission_pct
                self.portfolio.current_capital -= comision
                
                self.portfolio.execute_trade(symbol, current_signal, entry_price, current_time, size, tp_price=tp_price, sl_price=sl_price)
                     
            # 3. Actualizar la curva de capital al cierre actual (mark-to-market temporal)
            mtm_capital = self.portfolio.current_capital
            if symbol in self.portfolio.positions:
                pos = self.portfolio.positions[symbol]
                mtm_capital += pos.get_unrealized_pnl(current_bar['close'])
                
            # hack the portfolio's internal recording to use MTM
            temp_cap = self.portfolio.current_capital
            self.portfolio.current_capital = mtm_capital
            self.portfolio.update_equity_curve()
            self.portfolio.current_capital = temp_cap
            
        logger.info(f"Backtest finalizado. Capital final MTM: {self.portfolio.equity_curve[-1]:.2f}")
