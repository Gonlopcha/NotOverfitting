"""
Módulo de limpieza de datos.
"""
import pandas as pd
import numpy as np
from typing import Any, List, Dict
from src.pipeline.base import PipelineStep
from src.core.logger import get_logger

logger = get_logger(__name__)

class DataCleaner(PipelineStep):
    """
    Paso de pipeline para limpieza de datos OHLCV.
    Maneja:
    - Imputación de valores faltantes
    - Detección y remoción/capping de outliers
    - Tratamiento de ceros en el volumen
    """

    def __init__(
        self, 
        fill_method: str = 'ffill', 
        outlier_std: float = 3.0,
        columns_to_clean: List[str] = None,
        **kwargs
    ):
        """
        Args:
            fill_method: Método para llenar NAs ('ffill', 'bfill', 'interpolate')
            outlier_std: Umbral de desviación estándar para capping de outliers
            columns_to_clean: Columnas a las que aplicar capping (por defecto: 'volume')
        """
        super().__init__(**kwargs)
        self.params.update({
            'fill_method': fill_method,
            'outlier_std': outlier_std,
            'columns_to_clean': columns_to_clean or ['volume']
        })
        self._stats: Dict[str, Dict[str, float]] = {}

    def fit(self, X: pd.DataFrame, y: Any = None) -> 'DataCleaner':
        """
        Calcula las estadísticas necesarias (medias, std) para imputación o capping de outliers.
        """
        outlier_std = self.params['outlier_std']
        cols = self.params['columns_to_clean']
        
        for col in cols:
            if col in X.columns:
                mean = X[col].mean()
                std = X[col].std()
                self._stats[col] = {
                    'mean': mean,
                    'std': std,
                    'upper_bound': mean + (outlier_std * std),
                    'lower_bound': max(0, mean - (outlier_std * std))  # Asumimos que los precios/volumen no pueden ser negativos
                }
                
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Aplica la limpieza a los datos.
        """
        df = X.copy()
        initial_len = len(df)
        
        # 1. Tratar ceros y NAs en open, high, low, close
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            if col in df.columns:
                df.loc[df[col] <= 0, col] = np.nan
                
        # 2. Imputación de valores faltantes
        fill_method = self.params['fill_method']
        if fill_method == 'ffill':
            df = df.ffill().bfill()
        elif fill_method == 'bfill':
            df = df.bfill().ffill()
        elif fill_method == 'interpolate':
            df = df.interpolate(method='linear').bfill().ffill()
            
        # 3. Capping de outliers (basado en lo aprendido en fit)
        for col, stats in self._stats.items():
            if col in df.columns:
                upper = stats['upper_bound']
                df[col] = np.clip(df[col], a_min=0, a_max=upper)
                
        logger.debug(f"DataCleaner procesó {initial_len} filas. {df.isna().sum().sum()} NAs restantes.")
        return df
