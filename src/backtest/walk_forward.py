import pandas as pd
import numpy as np
from typing import List, Tuple
from src.core.logger import get_logger

logger = get_logger(__name__)

class WalkForwardValidator:
    """
    Divide los datos en ventanas temporales (folds) para evaluación Walk-Forward.
    Previene el sobreajuste asegurando que el modelo se prueba en datos futuros
    estrictamente secuenciales.
    """
    
    def __init__(self, n_splits: int = 3, train_size: float = 0.7):
        """
        Args:
            n_splits: Número de ventanas.
            train_size: Porcentaje del fold que se usa para entrenamiento.
        """
        self.n_splits = n_splits
        self.train_size = train_size
        
    def split(self, data: pd.DataFrame) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Divide el dataframe en n_splits ventanas secuenciales.
        Cada ventana tiene un conjunto de entrenamiento y uno de prueba.
        """
        n_samples = len(data)
        fold_size = n_samples // self.n_splits
        
        folds = []
        for i in range(self.n_splits):
            start_idx = i * fold_size
            end_idx = start_idx + fold_size if i < self.n_splits - 1 else n_samples
            
            fold_data = data.iloc[start_idx:end_idx]
            
            train_len = int(len(fold_data) * self.train_size)
            train_data = fold_data.iloc[:train_len]
            test_data = fold_data.iloc[train_len:]
            
            folds.append((train_data, test_data))
            
            logger.debug(f"Fold {i+1}: Train {len(train_data)} velas, Test {len(test_data)} velas.")
            
        return folds
