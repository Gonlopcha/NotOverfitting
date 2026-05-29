"""
Módulo base de estrategias.
"""
from abc import ABC, abstractmethod
import pandas as pd
from typing import Any, Dict

class StrategyBase(ABC):
    """
    Clase base abstracta para todas las estrategias de trading.
    """
    
    def __init__(self, name: str, params: Dict[str, Any] = None):
        self.name = name
        self.params = params or {}
        
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Genera señales de trading (ej: 1 = COMPRAR, -1 = VENDER, 0 = MANTENER)
        basado en el DataFrame procesado (con features).
        """
        pass
