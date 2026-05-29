"""
Implementación del Método de la Triple Barrera (Marcos López de Prado).
Evita el etiquetado ingenuo de "siguiente vela" y permite a los modelos
aprender si una posición tocará Take Profit o Stop Loss antes de un tiempo límite.
"""
import pandas as pd
import numpy as np

def apply_triple_barrier(df: pd.DataFrame, 
                         pt_factor: float = 2.0, 
                         sl_factor: float = 1.0, 
                         horizon: int = 24,
                         atr_col: str = 'atr_14') -> pd.Series:
    """
    Etiqueta los datos usando la Triple Barrera.
    
    Args:
        df: DataFrame con precios ('close', 'high', 'low') y el ATR calculado.
        pt_factor: Multiplicador del ATR para el Take Profit (Barrera Superior).
        sl_factor: Multiplicador del ATR para el Stop Loss (Barrera Inferior).
        horizon: Límite de tiempo en velas (Barrera Vertical).
        atr_col: Nombre de la columna de volatilidad.
        
    Returns:
        pd.Series con etiquetas:
            1: Toca Take Profit (Oportunidad de Compra)
           -1: Toca Stop Loss (Oportunidad de Venta Corta)
            0: Toca la Barrera de Tiempo (Mercado lateral, no operar)
    """
    labels = pd.Series(index=df.index, data=0, dtype=int)
    
    # Verificación de requisitos
    if atr_col not in df.columns:
        # Fallback a volatilidad simple si no existe el ATR
        df[atr_col] = df['close'].rolling(14).std()
        
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    atrs = df[atr_col].fillna(method='bfill').values
    
    n = len(df)
    
    # Bucle optimizado en numpy
    for i in range(n):
        if i + horizon >= n:
            # Muy cerca del final para evaluar
            labels.iloc[i] = np.nan
            continue
            
        start_price = closes[i]
        atr = atrs[i]
        
        # Si el ATR es 0 o muy pequeño, saltar
        if atr < 1e-5:
            continue
            
        tp_price = start_price + (atr * pt_factor)
        sl_price = start_price - (atr * sl_factor)
        
        # Mirar hacia el futuro hasta 'horizon' velas
        for j in range(i + 1, i + horizon + 1):
            if j >= n:
                break
                
            curr_high = highs[j]
            curr_low = lows[j]
            
            # Condición de Take Profit (Long)
            if curr_high >= tp_price:
                labels.iloc[i] = 1
                break
            
            # Condición de Stop Loss (Equivalente a TP para Short)
            if curr_low <= sl_price:
                labels.iloc[i] = -1
                break
                
        # Si el bucle termina sin breaks, la etiqueta queda en 0 (Time Barrier)
        
    return labels.rename('target_tb')
