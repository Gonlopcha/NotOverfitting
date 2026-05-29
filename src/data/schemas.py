"""
Schemas: Modelos de validación con Pydantic para la capa de datos.

Define la estructura y validación de datos OHLCV, Ticks, metadatos y configuración.
"""

from typing import Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import pandas as pd


class DataType(str, Enum):
    """Tipos de datos soportados."""
    OHLCV = "ohlcv"
    TICKS = "ticks"


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


class TickRecord(BaseModel):
    """
    Representa un tick individual.
    
    Attributes:
        time: Timestamp del tick (microsegundos si disponible)
        bid: Precio bid
        ask: Precio ask
        bid_volume: Volumen disponible en bid (opcional)
        ask_volume: Volumen disponible en ask (opcional)
    """
    time: datetime
    bid: float = Field(..., gt=0)
    ask: float = Field(..., gt=0)
    bid_volume: Optional[int] = Field(None, ge=0)
    ask_volume: Optional[int] = Field(None, ge=0)

    @validator('ask')
    def ask_must_be_gte_bid(cls, v, values):
        """Valida que ask >= bid."""
        if 'bid' in values and v < values['bid']:
            raise ValueError(f'ask ({v}) debe ser >= bid ({values["bid"]})')
        return v


class DataMetadata(BaseModel):
    """
    Metadatos de un conjunto de datos históricos almacenado.
    
    Attributes:
        symbol: Símbolo (ej: 'EURUSD')
        timeframe: Marco temporal (ej: 'H1', 'D1') - N/A para ticks
        data_type: Tipo de datos (ohlcv o ticks)
        date_from: Fecha de inicio de datos
        date_to: Fecha de fin de datos
        rows: Número de registros
        checksum: Hash para verificar integridad
        created_at: Timestamp de creación
        last_updated: Timestamp de última actualización
    """
    symbol: str = Field(..., min_length=1, max_length=20)
    timeframe: Optional[str] = Field(None, regex=r'^(M1|M5|M15|M30|H1|H4|D1|W1|MN1)$')
    data_type: DataType = DataType.OHLCV
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
    
    @validator('timeframe')
    def timeframe_required_for_ohlcv(cls, v, values):
        """Valida que timeframe sea requerido para OHLCV."""
        if 'data_type' in values and values['data_type'] == DataType.OHLCV and v is None:
            raise ValueError('timeframe es requerido para datos OHLCV')
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
        timeframe: Marco temporal (obligatorio para OHLCV, ignorado para ticks)
        data_type: Tipo de datos a descargar (ohlcv o ticks)
        date_from: Fecha inicio (inclusiva)
        date_to: Fecha fin (inclusiva)
        force_refresh: Si True, ignora caché y descarga siempre
    """
    symbol: str = Field(..., min_length=1, max_length=20)
    timeframe: Optional[str] = Field(None, regex=r'^(M1|M5|M15|M30|H1|H4|D1|W1|MN1)$')
    data_type: DataType = DataType.OHLCV
    date_from: datetime
    date_to: datetime = Field(default_factory=datetime.now)
    force_refresh: bool = False

    @validator('date_to')
    def date_to_after_from(cls, v, values):
        """Valida que date_to >= date_from."""
        if 'date_from' in values and v < values['date_from']:
            raise ValueError('date_to debe ser >= date_from')
        return v
    
    @validator('timeframe')
    def timeframe_required_for_ohlcv(cls, v, values):
        """Valida que timeframe sea requerido para OHLCV."""
        if 'data_type' in values and values['data_type'] == DataType.OHLCV and v is None:
            raise ValueError('timeframe es requerido para datos OHLCV')
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


def validate_ticks_dataframe(df: pd.DataFrame) -> DataValidationResult:
    """
    Valida un DataFrame de ticks.
    
    Args:
        df: DataFrame con columnas ['time', 'bid', 'ask'] y opcionalmente 'bid_volume', 'ask_volume'
        
    Returns:
        DataValidationResult con resultado de validación
    """
    errors = []
    warnings = []
    rows_valid = 0
    rows_invalid = 0
    
    # Verificar columnas requeridas
    required_cols = ['time', 'bid', 'ask']
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
        df_copy[['bid', 'ask']] = df_copy[['bid', 'ask']].astype(float)
        
        # Columnas opcionales
        if 'bid_volume' in df_copy.columns:
            df_copy['bid_volume'] = pd.to_numeric(df_copy['bid_volume'], errors='coerce').astype('Int64')
        if 'ask_volume' in df_copy.columns:
            df_copy['ask_volume'] = pd.to_numeric(df_copy['ask_volume'], errors='coerce').astype('Int64')
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
            record_data = {
                'time': row['time'],
                'bid': row['bid'],
                'ask': row['ask']
            }
            if 'bid_volume' in row and pd.notna(row['bid_volume']):
                record_data['bid_volume'] = int(row['bid_volume'])
            if 'ask_volume' in row and pd.notna(row['ask_volume']):
                record_data['ask_volume'] = int(row['ask_volume'])
            
            record = TickRecord(**record_data)
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
