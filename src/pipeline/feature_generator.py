"""
Módulo para generación dinámica de features usando el Registry.
"""
import pandas as pd
from typing import Any, List
from src.pipeline.base import PipelineStep
from src.core.registry import get_feature_registry
from src.core.logger import get_logger

logger = get_logger(__name__)

class FeatureGenerator(PipelineStep):
    """
    Paso del pipeline que aplica las funciones registradas como 'features' al DataFrame.
    """

    def __init__(self, features: List[str] = None, **kwargs):
        """
        Args:
            features: Lista de nombres de features a generar. 
                     Si es None, generará todas las registradas.
        """
        super().__init__(**kwargs)
        self.params['features'] = features
        self.registry = get_feature_registry()

    def fit(self, X: pd.DataFrame, y: Any = None) -> 'FeatureGenerator':
        """
        La mayoría de las funciones de feature engineering no tienen estado.
        Si alguna lo requiere, se debería crear un transformer específico en lugar de una función simple.
        """
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Aplica todas las funciones solicitadas.
        """
        df = X.copy()
        
        features_to_apply = self.params['features']
        if features_to_apply is None:
            # Aplicar todas las registradas
            features_to_apply = list(self.registry.get_all().keys())
            
        logger.info(f"FeatureGenerator aplicando {len(features_to_apply)} features: {features_to_apply}")
        
        for feat_name in features_to_apply:
            try:
                feature_func = self.registry.get(feat_name)
                # Asumimos que la función retorna un pd.Series, un pd.DataFrame
                # o el DataFrame completo modificado.
                result = feature_func(df)
                
                if isinstance(result, pd.Series):
                    if result.name is None:
                        result.name = feat_name
                    df[result.name] = result
                elif isinstance(result, pd.DataFrame):
                    # Si devuelve un dataframe nuevo (con las features)
                    # evitamos duplicar columnas
                    for col in result.columns:
                        if col not in df.columns or result is df:
                            df[col] = result[col]
            except Exception as e:
                logger.error(f"Error aplicando feature '{feat_name}': {e}")
                
        # Llenar los NaNs generados por las ventanas móviles (RSI, ATR, etc.) 
        # hacia atrás (bfill) para que el PCATransformer no reciba NAs en las primeras filas.
        df = df.bfill()
        
        return df
