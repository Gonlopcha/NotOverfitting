"""
Base interface for pipeline steps.
"""
from abc import ABC, abstractmethod
import pandas as pd
from typing import Any, Dict

class PipelineStep(ABC):
    """
    Clase base abstracta para todos los pasos del pipeline de datos.
    Sigue una interfaz similar a scikit-learn (fit, transform, fit_transform).
    """

    def __init__(self, **kwargs):
        self.params = kwargs

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: Any = None) -> 'PipelineStep':
        """
        Ajusta el paso del pipeline a los datos (aprende parámetros si es necesario).
        
        Args:
            X: DataFrame de características
            y: Etiquetas (opcional, para transformadores supervisados)
            
        Returns:
            self (la instancia ajustada)
        """
        return self

    @abstractmethod
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Aplica la transformación a los datos.
        
        Args:
            X: DataFrame de entrada
            
        Returns:
            DataFrame transformado
        """
        pass

    def fit_transform(self, X: pd.DataFrame, y: Any = None) -> pd.DataFrame:
        """
        Ajusta a los datos y luego los transforma en un solo paso.
        
        Args:
            X: DataFrame de características
            y: Etiquetas (opcional)
            
        Returns:
            DataFrame transformado
        """
        return self.fit(X, y).transform(X)

    def get_params(self) -> Dict[str, Any]:
        """Obtiene los parámetros actuales del paso."""
        return self.params

    def set_params(self, **params) -> 'PipelineStep':
        """Actualiza los parámetros del paso."""
        self.params.update(params)
        return self
