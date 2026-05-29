"""
Módulo de características técnicas avanzadas.
Se calculan usando puramente pandas y numpy para evitar dependencias pesadas como TA-Lib.
"""
import pandas as pd
import numpy as np
from src.core.registry import get_feature_registry

registry = get_feature_registry()

@registry.register("atr_14")
def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calcula el Average True Range (ATR). Mide la volatilidad absoluta."""
    req_cols = ['high', 'low', 'close']
    if not all(col in df.columns for col in req_cols):
        raise ValueError(f"Faltan columnas para ATR. Se requiere: {req_cols}")
        
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift(1))
    low_close = np.abs(df['low'] - df['close'].shift(1))
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    
    # Usamos rolling mean simple por aproximación (Wilder's Smoothing es más complejo pero esto es funcional)
    return true_range.rolling(window=period).mean().rename(f'atr_{period}')


@registry.register("rsi_14")
def calc_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calcula el Relative Strength Index (RSI)."""
    if 'close' not in df.columns:
        raise ValueError("Columna 'close' no encontrada para RSI")
        
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.rename(f'rsi_{period}')


@registry.register("macd")
def calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    Calcula MACD, Señal y el Histograma.
    Devuelve un DataFrame con 3 columnas.
    """
    if 'close' not in df.columns:
        raise ValueError("Columna 'close' no encontrada para MACD")
        
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return pd.DataFrame({
        'macd_line': macd_line,
        'macd_signal': signal_line,
        'macd_hist': histogram
    })


@registry.register("bollinger_bands")
def calc_bollinger_bands(df: pd.DataFrame, period: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """
    Bandas de Bollinger y porcentaje B (%B).
    """
    if 'close' not in df.columns:
        raise ValueError("Columna 'close' no encontrada para Bollinger Bands")
        
    sma = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    
    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)
    
    # %B cuantifica dónde está el precio respecto a las bandas
    # %B = (Precio - Banda Inferior) / (Banda Superior - Banda Inferior)
    band_width = upper_band - lower_band
    pct_b = (df['close'] - lower_band) / band_width.replace(0, np.nan)
    
    return pd.DataFrame({
        'bb_upper': upper_band,
        'bb_lower': lower_band,
        'bb_pct_b': pct_b
    })


@registry.register("ema_distances")
def calc_ema_distances(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula la distancia porcentual del precio a las EMAs clave (Tendencia).
    """
    if 'close' not in df.columns:
        raise ValueError("Columna 'close' no encontrada para EMA Distances")
        
    ema_20 = df['close'].ewm(span=20, adjust=False).mean()
    ema_50 = df['close'].ewm(span=50, adjust=False).mean()
    ema_200 = df['close'].ewm(span=200, adjust=False).mean()
    
    dist_20 = (df['close'] - ema_20) / ema_20
    dist_50 = (df['close'] - ema_50) / ema_50
    dist_200 = (df['close'] - ema_200) / ema_200
    
    return pd.DataFrame({
        'dist_ema_20': dist_20,
        'dist_ema_50': dist_50,
        'dist_ema_200': dist_200
    })
