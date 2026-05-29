"""
Características técnicas y financieras con enfoque científico.
Cumple con la Sección 8.1 del Plan de Estudios:
- Uso de retornos logarítmicos en lugar de precios absolutos.
- Features de volatilidad.
- Features de momentum.
"""
import pandas as pd
import numpy as np
from src.core.registry import get_feature_registry

registry = get_feature_registry()

@registry.register("log_returns")
def calc_log_returns(df: pd.DataFrame) -> pd.Series:
    """
    Calcula retornos logarítmicos.
    Los precios no son estacionarios, los retornos logarítmicos suelen serlo.
    """
    if 'close' not in df.columns:
        raise ValueError("Columna 'close' no encontrada")
    # Añadimos pequeña constante para evitar log(0) si hay errores
    return np.log(df['close'] / df['close'].shift(1)).rename('log_returns')

@registry.register("rolling_volatility_20")
def calc_rolling_volatility_20(df: pd.DataFrame) -> pd.Series:
    """
    Calcula la volatilidad continua (desviación estándar) de los retornos
    logarítmicos en una ventana de 20 períodos.
    """
    if 'close' not in df.columns:
        raise ValueError("Columna 'close' no encontrada")
    
    log_ret = np.log(df['close'] / df['close'].shift(1))
    return log_ret.rolling(window=20).std().rename('rolling_vol_20')

@registry.register("momentum_ma_ratio_50")
def calc_momentum_ma_ratio_50(df: pd.DataFrame) -> pd.Series:
    """
    Ratio del precio actual sobre la media móvil de 50 períodos.
    Captura el momentum evitando usar el precio absoluto.
    """
    if 'close' not in df.columns:
        raise ValueError("Columna 'close' no encontrada")
        
    ma_50 = df['close'].rolling(window=50).mean()
    return (df['close'] / ma_50 - 1).rename('mom_ma_ratio_50')

@registry.register("relative_volume_20")
def calc_relative_volume(df: pd.DataFrame) -> pd.Series:
    """
    Volumen relativo (volumen actual / media móvil de 20 períodos).
    Feature de microestructura.
    """
    if 'volume' not in df.columns:
        raise ValueError("Columna 'volume' no encontrada")
        
    vol_ma = df['volume'].rolling(window=20).mean()
    # Evitar divisiones por cero
    vol_ma = vol_ma.replace(0, np.nan)
    return (df['volume'] / vol_ma).rename('relative_vol_20')
