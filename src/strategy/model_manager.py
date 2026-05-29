"""
Administrador de modelos de Machine Learning y evaluación Anti-Overfitting (MDA).
"""
import pandas as pd
import numpy as np
import joblib
import os
from typing import Any, Dict, List, Tuple
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from src.core.logger import get_logger

logger = get_logger(__name__)

class ModelManager:
    """
    Entrena, evalúa (incluyendo MDA) y guarda/carga modelos predictivos.
    Por defecto usa Random Forest que es robusto al overfitting.
    """

    def __init__(self, model: Any = None, model_dir: str = "models", **kwargs):
        if model is None:
            rf_kwargs = {
                'n_estimators': kwargs.get('n_estimators', 100),
                'max_depth': kwargs.get('max_depth', 5),
                'random_state': 42,
                'class_weight': 'balanced'
            }
            self.model = RandomForestClassifier(**rf_kwargs)
        else:
            self.model = model
        self.model_dir = model_dir
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)

    def train(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        """Entrena el modelo."""
        logger.info(f"Entrenando modelo {self.model.__class__.__name__} con {len(X_train)} muestras...")
        self.model.fit(X_train, y_train)
        logger.info("Entrenamiento finalizado.")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Realiza predicciones."""
        return self.model.predict(X)

    def predict_proba(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Devuelve las probabilidades predichas como un DataFrame alineado con las clases (-1, 0, 1).
        Asegura que siempre existan las columnas para todas las clases esperadas, 
        incluso si la muestra de entrenamiento no tenía alguna clase.
        """
        probs = self.model.predict_proba(X)
        classes = self.model.classes_
        
        df_probs = pd.DataFrame(probs, columns=classes, index=X.index)
        
        # Asegurar que existan las 3 clases de Triple Barrera
        for expected_class in [-1, 0, 1]:
            if expected_class not in df_probs.columns:
                df_probs[expected_class] = 0.0
                
        # Reordenar las columnas consistentemente
        return df_probs[[-1, 0, 1]]

    def calculate_mda(self, X_val: pd.DataFrame, y_val: pd.Series, n_repeats: int = 5) -> pd.DataFrame:
        """
        Calcula Mean Decrease Accuracy (MDA) / Permutation Feature Importance.
        Evalúa el impacto real de cada feature en datos de validación (out-of-sample).
        
        Args:
            X_val: Features de validación.
            y_val: Etiquetas de validación.
            n_repeats: Número de permutaciones.
            
        Returns:
            DataFrame con las importancias ordenadas.
        """
        logger.info("Calculando MDA (Permutation Feature Importance)...")
        result = permutation_importance(
            self.model, X_val, y_val, 
            n_repeats=n_repeats, 
            random_state=42, 
            n_jobs=-1
        )
        
        mda_df = pd.DataFrame({
            'feature': X_val.columns,
            'importance_mean': result.importances_mean,
            'importance_std': result.importances_std
        }).sort_values('importance_mean', ascending=False)
        
        # Loggear advertencias si hay features con importancia negativa o cero
        useless_features = mda_df[mda_df['importance_mean'] <= 0]
        if not useless_features.empty:
            logger.warning(f"Se detectaron {len(useless_features)} features inútiles (MDA <= 0). "
                           f"Se recomienda eliminarlas para reducir overfitting.")
            
        return mda_df

    def save_model(self, name: str) -> str:
        """Serializa el modelo a disco."""
        filepath = os.path.join(self.model_dir, f"{name}.joblib")
        joblib.dump(self.model, filepath)
        logger.info(f"Modelo guardado en {filepath}")
        return filepath

    def load_model(self, name: str) -> None:
        """Carga el modelo desde el disco."""
        filepath = os.path.join(self.model_dir, f"{name}.joblib")
        self.model = joblib.load(filepath)
        logger.info(f"Modelo cargado desde {filepath}")
