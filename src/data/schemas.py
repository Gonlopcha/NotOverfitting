"""
Schemas: Modelos de validación con Pydantic para la capa de datos.

Define la estructura y validación de datos OHLCV, metadatos y configuración.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator
import pandas as pd


class OHLCVRecord(BaseModel):
    """
    Representa una vela OHLCV individual.
    
    Attributes:
        time: Timestamp de la vela
        open: Precio de apertura
        high: Precio máximo
        low: Precio mínimo
        close: Precio de cierre
        volume: Volumen (en ticks)
    """
    time: datetime
    open: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: int = Field(..., ge=0)

    @validator('high')
    def high_must_be_max(cls, v, values):
        """Valida que high >= max(open, close, low)."""
        if 'open' in values and 'close' in values and 'low' in values:
            prices = [values['open'], values['close'], values['low']]
            if v < max(prices):
                raise ValueError(f'high ({v}) debe ser >= max(open, close, low)')
        return v

    @validator('low')
    def low_must_be_min(cls, v, values):
        """Valida que low <= min(open, close, high)."""
        if 'open' in values and 'close' in values:
            prices = [values['open'], values['close']]
            if v > min(prices):
                raise ValueError(f'low ({v}) debe ser <= min(open, close)')
        return v


class DataMetadata(BaseModel):
    """
    Metadatos de un conjunto de datos históricos almacenado.
    
    Attributes:
        symbol: Símbolo (ej: 'EURUSD')
        timeframe: Marco temporal (ej: 'H1', 'D1')
        date_from: Fecha de inicio de datos
        date_to: Fecha de fin de datos
        rows: Número de registros
        checksum: Hash para verificar integridad
        created_at: Timestamp de creación
        last_updated: Timestamp de última actualización
    """
    symbol: str = Field(..., min_length=1, max_length=20)
    timeframe: str = Field(..., regex=r'^(M1|M5|M15|M30|H1|H4|D1|W1|MN1)$')
    date_from: datetime
    date_to: datetime
    rows: int = Field(..., ge=0)
    checksum: str = Field(..., min_length=32, max_length=64)  # SHA256 hex
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)

    @validator('date_to')
    def date_to_after_from(cls, v, values):
        """Valida que date_to > date_from."""
        if 'date_from' in values and v <= values['date_from']:
            raise ValueError('date_to debe ser mayor que date_from')
        return v


class CacheEntry(BaseModel):
    """
    Representa una entrada en el caché de datos.
    
    Attributes:
        symbol: Símbolo
        timeframe: Marco temporal
        date_from: Fecha inicio del rango cacheado
        date_to: Fecha fin del rango cacheado
        cached_at: Timestamp de cuando se cacheó
        expiry: Timestamp cuando expira (None = no expira)
        rows: Número de registros en caché
    """
    symbol: str = Field(..., min_length=1, max_length=20)
    timeframe: str = Field(..., regex=r'^(M1|M5|M15|M30|H1|H4|D1|W1|MN1)$')
    date_from: datetime
    date_to: datetime
    cached_at: datetime = Field(default_factory=datetime.now)
    expiry: Optional[datetime] = None
    rows: int = Field(..., ge=0)

    def is_expired(self) -> bool:
        """Verifica si la entrada ha expirado."""
        if self.expiry is None:
            return False
        return datetime.now() > self.expiry


class DownloadRequest(BaseModel):
    """
    Solicitud de descarga de datos.
    
    Attributes:
        symbol: Símbolo a descargar
        timeframe: Marco temporal
        date_from: Fecha inicio (inclusiva)
        date_to: Fecha fin (inclusiva)
        force_refresh: Si True, ignora caché y descarga siempre
    """
    symbol: str = Field(..., min_length=1, max_length=20)
    timeframe: str = Field(..., regex=r'^(M1|M5|M15|M30|H1|H4|D1|W1|MN1)$')
    date_from: datetime
    date_to: datetime = Field(default_factory=datetime.now)
    force_refresh: bool = False

    @validator('date_to')
    def date_to_after_from(cls, v, values):
        """Valida que date_to >= date_from."""
        if 'date_from' in values and v < values['date_from']:
            raise ValueError('date_to debe ser >= date_from')
        return v


class DataValidationResult(BaseModel):
    """
    Resultado de validación de datos.
    
    Attributes:
        is_valid: Si los datos pasaron validación
        rows_total: Total de registros evaluados
        rows_valid: Registros válidos
        rows_invalid: Registros con errores
        errors: Lista de errores encontrados
        warnings: Lista de advertencias
        missing_pct: Porcentaje de datos faltantes
    """
    is_valid: bool
    rows_total: int
    rows_valid: int
    rows_invalid: int
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    missing_pct: float = Field(..., ge=0, le=100)


def validate_ohlcv_dataframe(df: pd.DataFrame) -> DataValidationResult:
    """
    Valida un DataFrame de OHLCV.
    
    Args:
        df: DataFrame con columnas ['time', 'open', 'high', 'low', 'close', 'volume']
        
    Returns:
        DataValidationResult con resultado de validación
    """
    errors = []
    warnings = []
    rows_valid = 0
    rows_invalid = 0
    
    # Verificar columnas requeridas
    required_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return DataValidationResult(
            is_valid=False,
            rows_total=len(df),
            rows_valid=0,
            rows_invalid=len(df),
            errors=[f"Columnas faltantes: {missing_cols}"],
            missing_pct=100.0
        )
    
    # Verificar tipos
    try:
        df_copy = df.copy()
        df_copy['time'] = pd.to_datetime(df_copy['time'])
        df_copy[['open', 'high', 'low', 'close']] = df_copy[['open', 'high', 'low', 'close']].astype(float)
        df_copy['volume'] = df_copy['volume'].astype(int)
    except Exception as e:
        errors.append(f"Error de tipo de datos: {e}")
        return DataValidationResult(
            is_valid=False,
            rows_total=len(df),
            rows_valid=0,
            rows_invalid=len(df),
            errors=errors,
            missing_pct=100.0
        )
    
    # Validar cada registro
    for idx, row in df_copy.iterrows():
        try:
            record = OHLCVRecord(**row.to_dict())
            rows_valid += 1
        except Exception as e:
            rows_invalid += 1
            errors.append(f"Row {idx}: {str(e)}")
    
    # Detectar valores faltantes
    missing_count = df.isnull().sum().sum()
    missing_pct = (missing_count / (len(df) * len(df.columns))) * 100 if len(df) > 0 else 0
    
    if missing_pct > 0:
        warnings.append(f"{missing_pct:.2f}% de datos faltantes")
    
    is_valid = rows_invalid == 0 and missing_pct == 0
    
    return DataValidationResult(
        is_valid=is_valid,
        rows_total=len(df),
        rows_valid=rows_valid,
        rows_invalid=rows_invalid,
        errors=errors[:10],  # Limitar a 10 errores
        warnings=warnings,
        missing_pct=missing_pct
    )
