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
            
            # 1. Actualizar el portfolio a los precios de mercado actuales (mark-to-market)
            # Para simplificar, asumimos que podemos operar al precio de cierre de la barra
            price = current_bar['close']
            
            # Aplicar "slippage"
            if current_signal == 1:
                price = price * (1 + (self.slippage_pips / 10000.0))  # Aumenta precio de compra
            elif current_signal == -1:
                price = price * (1 - (self.slippage_pips / 10000.0))  # Disminuye precio de venta
            
            # 2. Ejecutar la operación (abrir/cerrar)
            # Solo actuamos si hay señal clara (1 o -1). Si es 0, mantenemos posiciones abiertas.
            if current_signal in [1, -1]:
                size = 1.0
                
                # Descontar comision si la operación es una entrada nueva o reversa
                if symbol not in self.portfolio.positions or current_signal != self.portfolio.positions[symbol].direction:
                     comision = price * size * self.commission_pct
                     self.portfolio.current_capital -= comision
                     
                self.portfolio.execute_trade(symbol, current_signal, price, current_time, size)
                     
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
