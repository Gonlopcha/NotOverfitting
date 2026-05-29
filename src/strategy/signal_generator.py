"""
Módulo para transformar predicciones en señales de trading.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any

class SignalGenerator:
    """
    Toma las probabilidades predichas por el modelo y las convierte en
    señales de trading discretas (1: Compra, -1: Venta, 0: Mantener).
    Permite aplicar lógica asimétrica y umbrales ajustados para datos desbalanceados.
    """
    
    def __init__(self, buy_threshold: float = 0.5, sell_threshold: float = 0.5, enable_short: bool = False):
        """
        Args:
            buy_threshold: Probabilidad mínima para generar señal de compra.
            sell_threshold: Probabilidad máxima (de la clase 1) para generar señal de venta corta.
            enable_short: Si es True, generará señales -1. Si es False, solo 1 o 0.
        """
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.enable_short = enable_short
        
    def generate(self, probabilities: np.ndarray) -> pd.Series:
        """
        Genera señales a partir de probabilidades.
        
        Args:
            probabilities: Array de probabilidades predichas. 
                           Si es 2D (ej: output de predict_proba), usamos la col 1.
            
        Returns:
            pd.Series con señales (1, -1, 0).
        """
        if len(probabilities.shape) == 2:
            if probabilities.shape[1] == 3:
                # Caso Multiclase (-1, 0, 1)
                prob_short = probabilities[:, 0]
                prob_long = probabilities[:, 2]
                
                signals = np.zeros(len(probabilities), dtype=int)
                signals[prob_long >= self.buy_threshold] = 1
                if self.enable_short:
                    # En multiclase usamos un umbral directo para el corto, no el sell_threshold binario
                    signals[prob_short >= self.buy_threshold] = -1
                return pd.Series(signals, name='signal')
            else:
                # Caso Binario (0, 1)
                prob_pos = probabilities[:, 1]
        else:
            prob_pos = probabilities
            
        signals = np.zeros(len(prob_pos), dtype=int)
        
        # Generar señal de compra
        signals[prob_pos >= self.buy_threshold] = 1
        
        # Si la estrategia permite cortos
        if self.enable_short:
            signals[prob_pos <= self.sell_threshold] = -1
            
        return pd.Series(signals, name='signal')
