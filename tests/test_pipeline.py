import unittest
import pandas as pd
import numpy as np
from src.pipeline.orchestrator import PipelineOrchestrator
from src.pipeline.cleaner import DataCleaner
from src.pipeline.feature_generator import FeatureGenerator
from src.core.registry import get_feature_registry

class TestPipelineReproducibility(unittest.TestCase):
    
    def setUp(self):
        # Crear un dataset sintético con algo de ruido y NAs
        np.random.seed(42)
        dates = pd.date_range(start='2023-01-01', periods=100, freq='H')
        self.df_raw = pd.DataFrame({
            'time': dates,
            'open': np.random.normal(1.1, 0.01, 100),
            'high': np.random.normal(1.12, 0.01, 100),
            'low': np.random.normal(1.08, 0.01, 100),
            'close': np.random.normal(1.11, 0.01, 100),
            'volume': np.random.randint(100, 1000, 100)
        })
        # Introducir anomalías (outliers y NAs) para probar el cleaner
        self.df_raw.loc[10, 'close'] = np.nan
        self.df_raw.loc[20, 'volume'] = 0
        self.df_raw.loc[30, 'close'] = 5.0  # Outlier masivo
        
        # Nos aseguramos de tener funciones en el registry
        import src.pipeline.features.technical  # Fuerza el registro
        self.registry = get_feature_registry()
        
    def test_pipeline_reproducibility(self):
        """
        Prueba que el pipeline completo produce exactamente los mismos resultados 
        dada la misma entrada (determinismo crítico para evitar data leakage).
        """
        orchestrator = PipelineOrchestrator.create_default(use_pca=True, pca_variance=0.95)
        
        # Ejecución 1
        df_1 = orchestrator.fit_transform(self.df_raw)
        
        # Ejecución 2
        df_2 = orchestrator.transform(self.df_raw)
        
        # Ambos DataFrames deben ser estructural y numéricamente idénticos
        pd.testing.assert_frame_equal(df_1, df_2)
        
        # Validar que los outliers se limpiaron (el outlier de 5.0 debió ser capeado)
        self.assertTrue(df_1['close'].max() < 4.0)
        
        # Validar que se generaron las features de PCA (el transformer debió dropear columnas y crear pca_*)
        pca_cols = [c for c in df_1.columns if c.startswith('pca_')]
        self.assertTrue(len(pca_cols) > 0)
        
    def test_feature_generator_no_leakage(self):
        """
        Verifica que al calcular features no haya filtración temporal (look-ahead bias).
        """
        generator = FeatureGenerator(features=['log_returns', 'rolling_volatility_20'])
        df_processed = generator.fit_transform(self.df_raw)
        
        # El retorno en el índice 0 debe ser NaN porque no hay dato previo
        self.assertTrue(np.isnan(df_processed.loc[0, 'log_returns']))
        
        # La volatilidad rodante a 20 periodos debe ser NaN en los primeros 19 periodos
        self.assertTrue(np.isnan(df_processed.loc[18, 'rolling_vol_20']))
        # Como inyectamos un NaN en el índice 10 de 'close', comprobamos más adelante
        self.assertFalse(np.isnan(df_processed.loc[35, 'rolling_vol_20']))

if __name__ == '__main__':
    unittest.main()
