"""
MT5Connector: Singleton Thread-Safe para conexión con MetaTrader 5.

Proporciona una única instancia de conexión a MT5, con manejo de errores,
validación y thread-safety para operaciones concurrentes.
"""

import threading
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime, timedelta
import time

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

import pandas as pd

from src.core.exceptions import MT5ConnectionError, DataDownloadError
from src.core.event_bus import emit
from src.core.logger import get_logger


logger = get_logger(__name__)


class MT5Connector:
    """
    Singleton thread-safe para conexión con MetaTrader 5.
    
    Garantiza una única instancia de conexión activa. Implementa:
    - Conexión lazy (se conecta cuando es necesario)
    - Reconexión automática si se pierde la conexión
    - Thread-safety con locks
    - Caché de información de símbolos
    - Logging detallado de operaciones
    """
    
    _instance: Optional['MT5Connector'] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'MT5Connector':
        """Implementa el patrón singleton thread-safe."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MT5Connector, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Inicializa el connector (solo la primera vez)."""
        if self._initialized:
            return
        
        if mt5 is None:
            raise ImportError(
                "MetaTrader5 no está instalado. Instala con: pip install MetaTrader5"
            )
        
        self._connected = False
        self._connection_lock = threading.RLock()
        self._symbols_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_expires = datetime.now()
        self._cache_ttl = 3600  # 1 hora en segundos
        self._max_retries = 3
        self._retry_delay = 2
        self._initialized = True
        
        logger.info("MT5Connector inicializado (singleton)")

    def connect(
        self,
        login: int,
        password: str,
        server: str,
        timeout: int = 5000
    ) -> bool:
        """
        Conecta a MetaTrader 5.
        
        Args:
            login: Número de login de la cuenta
            password: Contraseña de la cuenta
            server: Nombre del servidor (ej: 'XAUUSD-Demo' o 'ICMarketsDemoCent')
            timeout: Timeout en milisegundos
            
        Returns:
            True si la conexión fue exitosa
            
        Raises:
            MT5ConnectionError: Si la conexión falla después de reintentos
            
        Example:
            >>> connector = MT5Connector()
            >>> connector.connect(12345678, 'mypassword', 'XAUUSD-Demo')
            True
        """
        with self._connection_lock:
            if self._connected:
                logger.debug("Ya hay una conexión activa a MT5")
                return True
            
            for attempt in range(1, self._max_retries + 1):
                try:
                    logger.info(f"Intento {attempt}/{self._max_retries}: Conectando a MT5...")
                    
                    # Inicializar MT5
                    if not mt5.initialize(login=login, password=password, server=server, timeout=timeout):
                        error = mt5.last_error()
                        logger.warning(f"MT5.initialize falló: {error}")
                        time.sleep(self._retry_delay)
                        continue
                    
                    # Verificar que la conexión está activa
                    account_info = mt5.account_info()
                    if account_info is None:
                        logger.warning("No se pudo obtener info de la cuenta")
                        mt5.shutdown()
                        time.sleep(self._retry_delay)
                        continue
                    
                    self._connected = True
                    self._login = login
                    
                    emit(
                        'mt5.connected',
                        source='MT5Connector',
                        login=login,
                        server=server,
                        account_balance=float(account_info.balance)
                    )
                    
                    logger.info(
                        f"✓ Conectado a MT5 exitosamente. "
                        f"Balance: {account_info.balance} {account_info.currency}"
                    )
                    return True
                    
                except Exception as e:
                    logger.error(f"Intento {attempt} falló: {e}")
                    time.sleep(self._retry_delay)
            
            # Si llegamos aquí, todos los intentos fallaron
            error_msg = f"No se pudo conectar a MT5 después de {self._max_retries} intentos"
            logger.error(error_msg)
            raise MT5ConnectionError(error_msg)

    def disconnect(self) -> None:
        """
        Desconecta de MetaTrader 5 de forma segura.
        
        Example:
            >>> connector.disconnect()
        """
        with self._connection_lock:
            if self._connected:
                try:
                    mt5.shutdown()
                    self._connected = False
                    self._symbols_cache.clear()
                    
                    emit('mt5.disconnected', source='MT5Connector')
                    logger.info("✓ Desconectado de MT5")
                except Exception as e:
                    logger.error(f"Error al desconectar de MT5: {e}")

    def is_connected(self) -> bool:
        """Verifica si hay conexión activa con MT5."""
        with self._connection_lock:
            if not self._connected:
                return False
            
            # Verificar que la conexión sigue activa
            try:
                account_info = mt5.account_info()
                return account_info is not None
            except Exception:
                self._connected = False
                return False

    def download_ohlc(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime = None
    ) -> pd.DataFrame:
        """
        Descarga datos OHLCV de un símbolo en el rango de fechas especificado.
        
        Args:
            symbol: Símbolo a descargar (ej: 'EURUSD')
            timeframe: Marco temporal ('M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', etc.)
            start_date: Fecha inicio (datetime)
            end_date: Fecha final (datetime, si None usa la fecha actual)
            
        Returns:
            DataFrame con columnas: time, open, high, low, close, tick_volume
            
        Raises:
            DataDownloadError: Si la descarga falla
            MT5ConnectionError: Si no hay conexión activa
            
        Example:
            >>> connector = MT5Connector()
            >>> df = connector.download_ohlc(
            ...     'EURUSD',
            ...     'H1',
            ...     datetime(2023, 1, 1),
            ...     datetime(2023, 12, 31)
            ... )
        """
        if not self.is_connected():
            raise MT5ConnectionError("No hay conexión activa con MT5")
        
        if end_date is None:
            end_date = datetime.now()
        
        # Mapear nombres de timeframes a constantes MT5
        timeframe_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1,
            'W1': mt5.TIMEFRAME_W1,
            'MN1': mt5.TIMEFRAME_MN1,
        }
        
        if timeframe not in timeframe_map:
            raise DataDownloadError(
                f"Timeframe '{timeframe}' no válido. "
                f"Disponibles: {', '.join(timeframe_map.keys())}"
            )
        
        mt5_timeframe = timeframe_map[timeframe]
        
        try:
            with self._connection_lock:
                emit(
                    'data.download.started',
                    source='MT5Connector',
                    symbol=symbol,
                    timeframe=timeframe
                )
                
                logger.info(f"Descargando {symbol} {timeframe} desde {start_date} hasta {end_date}...")
                
                # Descargar datos
                rates = mt5.copy_rates_range(symbol, mt5_timeframe, start_date, end_date)
                
                if rates is None or len(rates) == 0:
                    error = mt5.last_error()
                    raise DataDownloadError(
                        f"No se obtuvieron datos para {symbol} {timeframe}: {error}"
                    )
                
                # Convertir a DataFrame
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df = df.rename(columns={
                    'open': 'open',
                    'high': 'high',
                    'low': 'low',
                    'close': 'close',
                    'tick_volume': 'volume',
                    'real_volume': 'real_volume',
                })
                
                # Reordenar y seleccionar columnas
                df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
                df = df.sort_values('time').reset_index(drop=True)
                
                emit(
                    'data.download.completed',
                    source='MT5Connector',
                    symbol=symbol,
                    timeframe=timeframe,
                    rows=len(df),
                    start=df['time'].iloc[0],
                    end=df['time'].iloc[-1]
                )
                
                logger.info(f"✓ Descargado {len(df)} barras de {symbol} {timeframe}")
                return df
                
        except Exception as e:
            error_msg = f"Error descargando datos de {symbol} {timeframe}: {e}"
            logger.error(error_msg)
            emit(
                'data.download.error',
                source='MT5Connector',
                symbol=symbol,
                error=str(e)
            )
            raise DataDownloadError(error_msg)

    def download_ticks(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime = None,
        group: str = 'TICK_ALL'
    ) -> pd.DataFrame:
        """
        Descarga datos de ticks de un símbolo en el rango de fechas especificado.
        
        Args:
            symbol: Símbolo a descargar (ej: 'EURUSD')
            start_date: Fecha inicio (datetime)
            end_date: Fecha final (datetime, si None usa la fecha actual)
            group: Tipo de ticks ('TICK_ALL', 'TICK_BID', 'TICK_ASK')
            
        Returns:
            DataFrame con columnas: time, bid, ask, bid_volume, ask_volume
            
        Raises:
            DataDownloadError: Si la descarga falla
            MT5ConnectionError: Si no hay conexión activa
            
        Note:
            - TICK_ALL: Todos los ticks disponibles
            - TICK_BID: Solo cambios en bid
            - TICK_ASK: Solo cambios en ask
            
        Example:
            >>> connector = MT5Connector()
            >>> df = connector.download_ticks(
            ...     'EURUSD',
            ...     datetime(2023, 1, 1),
            ...     datetime(2023, 1, 2),
            ...     group='TICK_ALL'
            ... )
        """
        if not self.is_connected():
            raise MT5ConnectionError("No hay conexión activa con MT5")
        
        if end_date is None:
            end_date = datetime.now()
        
        # Mapear grupos de ticks
        group_map = {
            'TICK_ALL': mt5.COPY_TICKS_ALL,
            'TICK_BID': mt5.COPY_TICKS_BID,
            'TICK_ASK': mt5.COPY_TICKS_ASK,
        }
        
        if group not in group_map:
            raise DataDownloadError(
                f"Grupo de ticks '{group}' no válido. "
                f"Disponibles: {', '.join(group_map.keys())}"
            )
        
        mt5_group = group_map[group]
        
        try:
            with self._connection_lock:
                emit(
                    'ticks.download.started',
                    source='MT5Connector',
                    symbol=symbol,
                    group=group
                )
                
                logger.info(f"Descargando ticks de {symbol} ({group}) desde {start_date} hasta {end_date}...")
                
                # Descargar ticks
                ticks = mt5.copy_ticks_range(symbol, start_date, end_date, mt5_group)
                
                if ticks is None or len(ticks) == 0:
                    error = mt5.last_error()
                    raise DataDownloadError(
                        f"No se obtuvieron ticks para {symbol} ({group}): {error}"
                    )
                
                # Convertir a DataFrame
                df = pd.DataFrame(ticks)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                # Convertir microsegundos a nanosegundos si disponible
                if 'time_msc' in df.columns:
                    df['time'] = pd.to_datetime(df['time_msc'], unit='ms')
                
                # Seleccionar columnas relevantes
                available_cols = [col for col in ['time', 'bid', 'ask', 'bid_volume', 'ask_volume'] 
                                 if col in df.columns]
                df = df[available_cols]
                df = df.sort_values('time').reset_index(drop=True)
                
                emit(
                    'ticks.download.completed',
                    source='MT5Connector',
                    symbol=symbol,
                    group=group,
                    rows=len(df),
                    start=df['time'].iloc[0],
                    end=df['time'].iloc[-1]
                )
                
                logger.info(f"✓ Descargados {len(df)} ticks de {symbol} ({group})")
                return df
                
        except Exception as e:
            error_msg = f"Error descargando ticks de {symbol} ({group}): {e}"
            logger.error(error_msg)
            emit(
                'ticks.download.error',
                source='MT5Connector',
                symbol=symbol,
                group=group,
                error=str(e)
            )
            raise DataDownloadError(error_msg)

    def get_symbol_info(self, symbol: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Obtiene información de un símbolo (digits, point, spread, etc.).
        
        Args:
            symbol: Símbolo (ej: 'EURUSD')
            use_cache: Si True, usa caché (se refresca cada hora)
            
        Returns:
            Dict con información del símbolo
            
        Raises:
            DataDownloadError: Si no se puede obtener la información
        """
        if not self.is_connected():
            raise MT5ConnectionError("No hay conexión activa con MT5")
        
        # Usar caché si está vigente
        if use_cache and symbol in self._symbols_cache:
            if datetime.now() < self._cache_expires:
                return self._symbols_cache[symbol]
        
        try:
            with self._connection_lock:
                symbol_info = mt5.symbol_info(symbol)
                
                if symbol_info is None:
                    raise DataDownloadError(f"Símbolo '{symbol}' no encontrado en MT5")
                
                info_dict = {
                    'symbol': symbol_info.name,
                    'description': symbol_info.description,
                    'digits': symbol_info.digits,
                    'point': symbol_info.point,
                    'bid': symbol_info.bid,
                    'ask': symbol_info.ask,
                    'spread': (symbol_info.ask - symbol_info.bid) / symbol_info.point,
                    'volume_min': symbol_info.volume_min,
                    'volume_max': symbol_info.volume_max,
                    'volume_step': symbol_info.volume_step,
                }
                
                # Actualizar caché
                self._symbols_cache[symbol] = info_dict
                self._cache_expires = datetime.now() + timedelta(seconds=self._cache_ttl)
                
                return info_dict
                
        except Exception as e:
            logger.error(f"Error obteniendo info del símbolo {symbol}: {e}")
            raise

    def get_account_info(self) -> Dict[str, Any]:
        """
        Obtiene información de la cuenta (balance, equity, margin, etc.).
        
        Returns:
            Dict con información de la cuenta
            
        Raises:
            MT5ConnectionError: Si no hay conexión activa
        """
        if not self.is_connected():
            raise MT5ConnectionError("No hay conexión activa con MT5")
        
        try:
            with self._connection_lock:
                account = mt5.account_info()
                
                if account is None:
                    raise MT5ConnectionError("No se pudo obtener información de la cuenta")
                
                return {
                    'login': account.login,
                    'server': account.server,
                    'currency': account.currency,
                    'balance': float(account.balance),
                    'equity': float(account.equity),
                    'margin': float(account.margin),
                    'free_margin': float(account.free_margin),
                    'margin_level': float(account.margin_level) if account.margin_level > 0 else None,
                    'profit': float(account.profit),
                    'trade_allowed': account.trade_allowed,
                }
                
        except Exception as e:
            logger.error(f"Error obteniendo información de la cuenta: {e}")
            raise

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.disconnect()

    def __repr__(self) -> str:
        status = "conectado" if self.is_connected() else "desconectado"
        return f"MT5Connector({status})"
