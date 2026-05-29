"""
Transformador de Reducción Dimensional (PCA).
Alineado con la Sección 8.2 del Plan de Estudios:
- Retiene los componentes que expliquen al menos el X% (ej: 90%) de la varianza.
- Requiere que los datos estén normalizados (StandardScaler) internamente antes de aplicar PCA.
"""
import pandas as pd
from typing import Any
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from src.pipeline.base import PipelineStep
from src.core.logger import get_logger

logger = get_logger(__name__)

class PCATransformer(PipelineStep):
    """
    Paso del pipeline que aplica Análisis de Componentes Principales.
    Primero estandariza las features (media 0, varianza 1) y luego calcula
    los componentes principales para reducir el ruido y la dimensionalidad.
    """

    def __init__(self, variance_threshold: float = 0.95, max_components: int = 50, **kwargs):
        """
        Args:
            variance_threshold: Fracción de la varianza total a retener (ej. 0.95 para 95%).
            max_components: Límite duro de componentes máximos.
        """
        super().__init__(**kwargs)
        self.params.update({
            'variance_threshold': variance_threshold,
            'max_components': max_components
        })
        # scikit-learn models
        self.scaler = StandardScaler()
        # Si le pasamos un float (0.0 a 1.0) a n_components, scikit-learn retiene la 
        # cantidad de componentes necesarios para explicar esa varianza.
        self.pca = PCA(n_components=variance_threshold)
        
        # Para evitar aplicar PCA a columnas como 'open', 'high', 'low', 'close', 'time'
        self.exclude_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
        self.feature_cols = []

    def fit(self, X: pd.DataFrame, y: Any = None) -> 'PCATransformer':
        """Ajusta el scaler y el modelo PCA a las features numéricas del dataframe."""
        self.feature_cols = [c for c in X.columns if c not in self.exclude_cols and pd.api.types.is_numeric_dtype(X[c])]
        
        if not self.feature_cols:
            logger.warning("PCATransformer: No hay columnas válidas para aplicar PCA.")
            return self
            
        X_features = X[self.feature_cols]
        # Validar si no hay NAs antes de escalar
        if X_features.isna().any().any():
            logger.warning("PCATransformer detectó NAs en las features. Se espera que DataCleaner se haya ejecutado.")
            X_features = X_features.fillna(0)  # Fallback
            
        X_scaled = self.scaler.fit_transform(X_features)
        self.pca.fit(X_scaled)
        
        n_comps = self.pca.n_components_
        # Aplicamos límite duro si aplica
        if n_comps > self.params['max_components']:
            logger.info(f"PCA encontró {n_comps} componentes para la varianza {self.params['variance_threshold']}, limitando a {self.params['max_components']}.")
            self.pca = PCA(n_components=self.params['max_components'])
            self.pca.fit(X_scaled)
            n_comps = self.pca.n_components_
            
        logger.info(f"PCA ajustado: {len(self.feature_cols)} features -> {n_comps} componentes principales.")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Transforma las features y devuelve el DataFrame modificado."""
        if not self.feature_cols or not hasattr(self.pca, 'components_'):
            return X
            
        df = X.copy()
        
        # Extraer solo las features conocidas
        X_features = df[self.feature_cols]
        if X_features.isna().any().any():
            X_features = X_features.fillna(0)
            
        # Escalar y transformar
        X_scaled = self.scaler.transform(X_features)
        pca_features = self.pca.transform(X_scaled)
        
        # Opcional: Eliminar las features originales y reemplazarlas por los componentes PCA?
        # En la mayoría de pipelines puros, las features originales se descartan.
        df = df.drop(columns=self.feature_cols)
        
        # Añadir componentes al DataFrame
        n_comps = pca_features.shape[1]
        for i in range(n_comps):
            df[f'pca_{i}'] = pca_features[:, i]
            
        return df
