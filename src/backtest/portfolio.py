"""
Módulo de gestión de capital, posiciones y riesgo.
Basado en la Sección 7.1 del Plan de Estudios.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from src.core.logger import get_logger

logger = get_logger(__name__)

class Position:
    """Representa una posición abierta en el mercado."""
    def __init__(self, symbol: str, direction: int, entry_price: float, size: float, entry_time: pd.Timestamp):
        self.symbol = symbol
        self.direction = direction  # 1: Long, -1: Short
        self.entry_price = entry_price
        self.size = size
        self.entry_time = entry_time
        
    def get_unrealized_pnl(self, current_price: float) -> float:
        """Calcula el PnL no realizado de la posición (sin apalancamiento/pip value por simplicidad)."""
        return (current_price - self.entry_price) * self.direction * self.size

class Portfolio:
    """
    Gestor de capital y posiciones con controles estrictos de riesgo.
    """
    def __init__(self, initial_capital: float = 10000.0, max_drawdown_limit: float = 0.20, kelly_fraction: float = 0.5):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_drawdown_limit = max_drawdown_limit
        self.kelly_fraction = kelly_fraction
        self.positions: Dict[str, Position] = {}
        self.equity_curve: List[float] = [initial_capital]
        self.peak_capital = initial_capital
        
        # Historial de trades cerrados
        self.trade_history: List[Dict] = []
        
    def update_peak(self):
        """Actualiza el pico de capital para el cálculo del drawdown."""
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
            
    def get_current_drawdown(self) -> float:
        """Calcula el drawdown actual."""
        if self.peak_capital == 0:
            return 0.0
        return (self.peak_capital - self.current_capital) / self.peak_capital

    def is_risk_limit_exceeded(self) -> bool:
        """Verifica si se ha excedido la tolerancia máxima al drawdown (Kill Switch)."""
        dd = self.get_current_drawdown()
        if dd >= self.max_drawdown_limit:
            logger.critical(f"KILL SWITCH ACTIVADO: Drawdown actual {dd:.2%} supera límite de {self.max_drawdown_limit:.2%}.")
            return True
        return False

    def calculate_position_size(self, win_rate: float, reward_risk_ratio: float) -> float:
        """
        Calcula el tamaño de posición usando Criterio de Kelly fraccionado.
        Kelly = W - ((1 - W) / R)
        W = win_rate, R = reward_risk_ratio
        
        Retorna el porcentaje de capital a arriesgar (0.0 a 1.0).
        """
        if reward_risk_ratio <= 0:
            return 0.0
            
        kelly = win_rate - ((1.0 - win_rate) / reward_risk_ratio)
        kelly = max(0.0, kelly) # No arriesgar negativo
        
        # Fracción de Kelly (Half-Kelly, Quarter-Kelly) para seguridad
        safe_kelly = kelly * self.kelly_fraction
        
        # Cap máximo de riesgo por operación (ej. 5% de la cuenta)
        return min(safe_kelly, 0.05)

    def execute_trade(self, symbol: str, signal: int, price: float, time: pd.Timestamp, size: float):
        """Abre o cierra una posición según la señal."""
        if self.is_risk_limit_exceeded():
            logger.warning("No se permiten más operaciones, se excedió el límite de drawdown.")
            return

        # Señal de salida si hay posición abierta contraria
        if symbol in self.positions:
            pos = self.positions[symbol]
            if signal == 0 or signal != pos.direction:
                # Cerrar posición actual
                pnl = pos.get_unrealized_pnl(price)
                self.current_capital += pnl
                self.update_peak()
                
                self.trade_history.append({
                    'symbol': symbol,
                    'direction': pos.direction,
                    'entry_time': pos.entry_time,
                    'exit_time': time,
                    'entry_price': pos.entry_price,
                    'exit_price': price,
                    'pnl': pnl,
                    'size': pos.size
                })
                logger.info(f"Cerrada posición {symbol} PnL: {pnl:.2f} Capital: {self.current_capital:.2f}")
                del self.positions[symbol]

        # Abrir nueva posición si hay señal
        if signal in [1, -1] and symbol not in self.positions:
            self.positions[symbol] = Position(symbol, signal, price, size, time)
            logger.info(f"Abierta posición {symbol} Dir: {signal} Tamaño: {size} Precio: {price:.5f}")

    def update_equity_curve(self):
        """Registra el capital actual en la curva de equity."""
        self.equity_curve.append(self.current_capital)
        
    def get_summary(self) -> pd.DataFrame:
        """Retorna el historial de trades como DataFrame."""
        return pd.DataFrame(self.trade_history)
