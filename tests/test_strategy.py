import unittest
import pandas as pd
import numpy as np
import os
import shutil
from sklearn.datasets import make_classification
from src.strategy.model_manager import ModelManager
from src.strategy.signal_generator import SignalGenerator

class TestStrategyLayer(unittest.TestCase):
    
    def setUp(self):
        self.model_dir = "tests/test_models"
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)
            
        # Generar dataset sintético para clasificación binaria
        X, y = make_classification(
            n_samples=200, n_features=5, n_informative=3, n_redundant=1,
            random_state=42
        )
        self.X_train = pd.DataFrame(X, columns=[f'feat_{i}' for i in range(5)])
        self.y_train = pd.Series(y)
        
    def tearDown(self):
        if os.path.exists(self.model_dir):
            shutil.rmtree(self.model_dir)
            
    def test_model_manager_train_and_predict(self):
        manager = ModelManager(model_dir=self.model_dir)
        manager.train(self.X_train, self.y_train)
        
        preds = manager.predict(self.X_train)
        self.assertEqual(len(preds), 200)
        
        probs = manager.predict_proba(self.X_train)
        self.assertEqual(probs.shape, (200, 2))
        
    def test_model_manager_mda(self):
        manager = ModelManager(model_dir=self.model_dir)
        manager.train(self.X_train, self.y_train)
        
        # Calcular MDA en los mismos datos de entrenamiento (solo para testear la API)
        mda_df = manager.calculate_mda(self.X_train, self.y_train, n_repeats=3)
        
        self.assertEqual(len(mda_df), 5)
        self.assertIn('feature', mda_df.columns)
        self.assertIn('importance_mean', mda_df.columns)
        
        # La feature con mayor MDA debe tener un importance > 0
        self.assertTrue(mda_df.iloc[0]['importance_mean'] > 0)
        
    def test_signal_generator(self):
        probs = np.array([[0.9, 0.1], [0.4, 0.6], [0.2, 0.8], [0.6, 0.4]])
        
        generator = SignalGenerator(buy_threshold=0.7, enable_short=False)
        signals = generator.generate(probs)
        # La columna 1 (prob de comprar) es: [0.1, 0.6, 0.8, 0.4]
        # > 0.7 está solo en el índice 2
        np.testing.assert_array_equal(signals.values, np.array([0, 0, 1, 0]))

if __name__ == '__main__':
    unittest.main()
