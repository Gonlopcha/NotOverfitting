"""
Orquestador del Pipeline de Datos.
"""
import pandas as pd
from typing import Any, List
from src.pipeline.base import PipelineStep
from src.pipeline.cleaner import DataCleaner
from src.pipeline.feature_generator import FeatureGenerator
from src.pipeline.pca_transformer import PCATransformer
from src.core.logger import get_logger

logger = get_logger(__name__)

class PipelineOrchestrator(PipelineStep):
    """
    Coordina la ejecución secuencial de los pasos del pipeline.
    Asegura la reproducibilidad (same input -> same output).
    """

    def __init__(self, steps: List[PipelineStep] = None, **kwargs):
        super().__init__(**kwargs)
        self.steps = steps or []

    def fit(self, X: pd.DataFrame, y: Any = None) -> 'PipelineOrchestrator':
        """
        Ejecuta fit() secuencialmente en cada paso.
        Para transformar los datos que se pasan al siguiente step en fit(),
        se usa fit_transform().
        """
        X_current = X.copy()
        
        logger.info(f"Iniciando ajuste (fit) de {len(self.steps)} pasos en el Pipeline.")
        for step in self.steps:
            logger.debug(f"Ajustando {step.__class__.__name__}...")
            # fit_transform modifica X_current para que el siguiente paso lo reciba procesado
            X_current = step.fit_transform(X_current, y)
            
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Aplica las transformaciones aprendidas secuencialmente."""
        X_current = X.copy()
        
        logger.info(f"Transformando datos a través de {len(self.steps)} pasos en el Pipeline.")
        for step in self.steps:
            X_current = step.transform(X_current)
            
        return X_current

    @classmethod
    def create_default(
        cls, 
        features: List[str] = None, 
        use_pca: bool = False, 
        pca_variance: float = 0.95
    ) -> 'PipelineOrchestrator':
        """Crea el pipeline estándar definido en la arquitectura."""
        steps = [
            DataCleaner(fill_method='ffill', outlier_std=3.0, columns_to_clean=['volume', 'close']),
            FeatureGenerator(features=features)
        ]
        
        if use_pca:
            steps.append(PCATransformer(variance_threshold=pca_variance))
            
        return cls(steps=steps)
