"""
DataManager: Orquestador centralizado de descarga, validación y almacenamiento de datos.

Integra MT5Connector, CacheManager, DataStore y esquemas de validación en un flujo unificado.
Emite eventos del sistema y maneja errores de forma robusta.
Soporta datos OHLCV y Ticks.
"""

import threading
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import pandas as pd

from src.core.logger import get_logger
from src.core.event_bus import emit
from src.core.exceptions import DataDownloadError
from src.core.mt5_connector import MT5Connector
from src.data.cache_manager import CacheManager
from src.data.data_store import DataStore
from src.data.schemas import validate_ohlcv_dataframe, validate_ticks_dataframe, DownloadRequest, DataType

logger = get_logger(__name__)


class DataManager:
    """
    Orquestador centralizado para gestión de datos OHLCV y Ticks.

    Integra:
    - MT5Connector: Descarga de datos desde MetaTrader 5
    - CacheManager: Caché en memoria con TTL
    - DataStore: Almacenamiento persistente (SQLite + Parquet)
    - Validación: Esquemas Pydantic y DataValidationResult

    Soporta:
    - Datos OHLCV (velas de diferentes timeframes)
    - Datos de Ticks (bid/ask en tiempo real)

    Flujo para OHLCV:
    1. Usuario solicita datos (symbol, timeframe, date_from, date_to)
    2. Verificar caché (¿datos vigentes?)
    3. Si no está en caché, consultar DataStore (¿datos persistidos?)
    4. Si no está en disk, descargar de MT5
    5. Validar datos
    6. Guardar en DataStore
    7. Actualizar caché
    8. Retornar datos + emitir evento

    Flujo para Ticks:
    1. Usuario solicita ticks (symbol, date_from, date_to)
    2. Verificar caché
    3. Si no está en caché, consultar DataStore
    4. Si no está en disk, descargar de MT5
    5. Validar datos
    6. Guardar en DataStore
    7. Actualizar caché
    8. Retornar datos + emitir evento
    """

    def __init__(
        self,
        mt5_connector: Optional[MT5Connector] = None,
        cache_manager: Optional[CacheManager] = None,
        data_store: Optional[DataStore] = None,
        cache_ttl: int = 3600
    ):
        """
        Inicializa el DataManager.

        Args:
            mt5_connector: Instancia de MT5Connector (si None, crea una)
            cache_manager: Instancia de CacheManager (si None, crea una)
            data_store: Instancia de DataStore (si None, crea una)
            cache_ttl: TTL de caché en segundos
        """
        self.mt5 = mt5_connector or MT5Connector()
        self.cache = cache_manager or CacheManager(ttl_seconds=cache_ttl)
        self.store = data_store or DataStore()
        
        self._lock = threading.RLock()
        self._download_queue: Dict[str, datetime] = {}  # Evitar descargas duplicadas simultáneas

    def download(
        self,
        symbol: str,
        timeframe: str,
        from_dt: datetime,
        to_dt: datetime = None,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Descarga datos OHLCV con lógica inteligente de caché y persistencia.

        Args:
            symbol: Símbolo (ej: 'EURUSD')
            timeframe: Marco temporal (ej: 'H1')
            from_dt: Fecha inicio
            to_dt: Fecha fin (si None, usa hoy)
            force_refresh: Si True, ignora caché y descarga siempre

        Returns:
            DataFrame con datos validados

        Raises:
            DataDownloadError: Si falla la descarga o validación
        """
        if to_dt is None:
            to_dt = datetime.now()

        # Validar request
        try:
            request = DownloadRequest(
                symbol=symbol,
                timeframe=timeframe,
                from_dt=from_dt,
                to_dt=to_dt,
                force_refresh=force_refresh
            )
        except Exception as e:
            logger.error(f"Request inválido: {e}")
            raise DataDownloadError(f"Solicitud inválida: {e}")

        logger.info(
            f"Descargando {symbol} {timeframe} "
            f"({from_dt.date()} → {to_dt.date()})"
        )

        emit(
            'data.download.started',
            source='DataManager',
            symbol=symbol,
            timeframe=timeframe,
            from_dt=from_dt,
            to_dt=to_dt
        )

        try:
            # Paso 1: Verificar caché si no force_refresh
            if not force_refresh:
                cached_df = self.cache.get_data(symbol, timeframe, from_dt, to_dt)
                if cached_df is not None:
                    logger.info(f"✓ Hit en caché: {symbol}/{timeframe}")
                    emit(
                        'data.download.completed',
                        source='DataManager',
                        symbol=symbol,
                        timeframe=timeframe,
                        rows=len(cached_df),
                        source_type='cache'
                    )
                    return cached_df

            # Paso 2: Obtener rangos faltantes
            missing_ranges = self.cache.get_missing_ranges(symbol, timeframe, from_dt, to_dt)

            if not missing_ranges:
                # Datos completos en caché (pero pasamos fuerza_refresh)
                cached_df = self.cache.get_data(symbol, timeframe, from_dt, to_dt)
                return cached_df

            # Paso 3: Descargar datos faltantes
            all_data = []

            for miss_from, miss_to in missing_ranges:
                logger.debug(f"Rango faltante: {miss_from.date()} → {miss_to.date()}")

                # Evitar descargas concurrentes del mismo símbolo/timeframe
                with self._lock:
                    queue_key = f"{symbol}:{timeframe}"
                    if queue_key in self._download_queue:
                        wait_until = self._download_queue[queue_key] + timedelta(seconds=2)
                        if datetime.now() < wait_until:
                            logger.debug(f"Esperando descarga anterior de {queue_key}...")
                            # En lugar de esperar, usar datos del store si existen
                            stored_df = self.store.load(symbol, timeframe, miss_from, miss_to)
                            if stored_df is not None:
                                all_data.append(stored_df)
                                continue
                    
                    self._download_queue[queue_key] = datetime.now()

                # Descargar de MT5
                try:
                    df = self.mt5.download_ohlc(symbol, timeframe, miss_from, miss_to)
                    all_data.append(df)
                except Exception as e:
                    logger.warning(f"Error descargando {symbol} {timeframe}: {e}")
                    # Intentar cargar del almacenamiento como fallback
                    stored_df = self.store.load(symbol, timeframe, miss_from, miss_to)
                    if stored_df is not None:
                        all_data.append(stored_df)
                    else:
                        raise DataDownloadError(f"No se pudo obtener datos para {symbol} {timeframe}: {e}")

            if not all_data:
                raise DataDownloadError(f"No se obtuvieron datos para {symbol}")

            # Paso 4: Combinar datos
            df = pd.concat(all_data, ignore_index=True)
            df['time'] = pd.to_datetime(df['time'])
            df = df.drop_duplicates(subset=['time']).sort_values('time').reset_index(drop=True)

            # Paso 5: Validar
            validation_result = validate_ohlcv_dataframe(df)

            if not validation_result.is_valid:
                logger.warning(f"Validación con advertencias: {validation_result.errors}")
                emit(
                    'data.validation.warning',
                    source='DataManager',
                    symbol=symbol,
                    errors=validation_result.errors[:3]
                )

            # Paso 6: Almacenar persistentemente
            try:
                self.store.store(symbol, timeframe, df)
            except Exception as e:
                logger.error(f"Error almacenando datos: {e}")
                # No fallar si el almacenamiento tiene problemas

            # Paso 7: Actualizar caché
            self.cache.update(symbol, timeframe, df, from_dt, to_dt)

            # Paso 8: Retornar datos filtrados por rango solicitado
            mask = (df['time'] >= from_dt) & (df['time'] <= to_dt)
            result_df = df[mask].reset_index(drop=True)

            emit(
                'data.download.completed',
                source='DataManager',
                symbol=symbol,
                timeframe=timeframe,
                rows=len(result_df),
                source_type='mt5',
                start_date=result_df['time'].min(),
                end_date=result_df['time'].max()
            )

            logger.info(f"✓ Descargados {len(result_df)} registros de {symbol} {timeframe}")
            return result_df

        except Exception as e:
            logger.error(f"Error descargando datos: {e}")
            emit(
                'data.download.error',
                source='DataManager',
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            raise DataDownloadError(f"Error descargando {symbol} {timeframe}: {e}")

    def get_tick_data(
        self,
        symbol: str,
        from_dt: datetime,
        to_dt: datetime = None,
        force_refresh: bool = False,
        group: str = 'TICK_ALL'
    ) -> pd.DataFrame:
        """
        Descarga datos de ticks con lógica inteligente de caché y persistencia.

        Args:
            symbol: Símbolo (ej: 'EURUSD')
            from_dt: Fecha inicio
            to_dt: Fecha fin (si None, usa hoy)
            force_refresh: Si True, ignora caché y descarga siempre
            group: Tipo de ticks ('TICK_ALL', 'TICK_BID', 'TICK_ASK')

        Returns:
            DataFrame con datos de ticks validados

        Raises:
            DataDownloadError: Si falla la descarga o validación
        """
        if to_dt is None:
            to_dt = datetime.now()

        # Validar request
        try:
            request = DownloadRequest(
                symbol=symbol,
                timeframe=None,
                data_type=DataType.TICKS,
                from_dt=from_dt,
                to_dt=to_dt,
                force_refresh=force_refresh
            )
        except Exception as e:
            logger.error(f"Request inválido: {e}")
            raise DataDownloadError(f"Solicitud inválida: {e}")

        logger.info(
            f"Descargando ticks {symbol} {group} "
            f"({from_dt.date()} → {to_dt.date()})"
        )

        emit(
            'ticks.download.started',
            source='DataManager',
            symbol=symbol,
            group=group,
            from_dt=from_dt,
            to_dt=to_dt
        )

        try:
            # Paso 1: Verificar caché si no force_refresh
            if not force_refresh:
                cached_df = self.cache.get_data(symbol, 'TICKS', from_dt, to_dt)
                if cached_df is not None:
                    logger.info(f"✓ Hit en caché: {symbol}/TICKS")
                    emit(
                        'ticks.download.completed',
                        source='DataManager',
                        symbol=symbol,
                        group=group,
                        rows=len(cached_df),
                        source_type='cache'
                    )
                    return cached_df

            # Paso 2: Obtener rangos faltantes
            missing_ranges = self.cache.get_missing_ranges(symbol, 'TICKS', from_dt, to_dt)

            if not missing_ranges:
                # Datos completos en caché
                cached_df = self.cache.get_data(symbol, 'TICKS', from_dt, to_dt)
                return cached_df

            # Paso 3: Descargar datos faltantes
            all_data = []

            for miss_from, miss_to in missing_ranges:
                logger.debug(f"Rango faltante: {miss_from.date()} → {miss_to.date()}")

                # Evitar descargas concurrentes del mismo símbolo/ticks
                with self._lock:
                    queue_key = f"{symbol}:TICKS"
                    if queue_key in self._download_queue:
                        wait_until = self._download_queue[queue_key] + timedelta(seconds=2)
                        if datetime.now() < wait_until:
                            logger.debug(f"Esperando descarga anterior de {queue_key}...")
                            # En lugar de esperar, usar datos del store si existen
                            stored_df = self.store.load(symbol, 'TICKS', miss_from, miss_to)
                            if stored_df is not None:
                                all_data.append(stored_df)
                                continue
                    
                    self._download_queue[queue_key] = datetime.now()

                # Descargar de MT5
                try:
                    df = self.mt5.get_tick_data(symbol, miss_from, miss_to, group)
                    all_data.append(df)
                except Exception as e:
                    logger.warning(f"Error descargando ticks {symbol} ({group}): {e}")
                    # Intentar cargar del almacenamiento como fallback
                    stored_df = self.store.load(symbol, 'TICKS', miss_from, miss_to)
                    if stored_df is not None:
                        all_data.append(stored_df)
                    else:
                        raise DataDownloadError(f"No se pudo obtener ticks para {symbol}: {e}")

            if not all_data:
                raise DataDownloadError(f"No se obtuvieron ticks para {symbol}")

            # Paso 4: Combinar datos
            df = pd.concat(all_data, ignore_index=True)
            df['time'] = pd.to_datetime(df['time'])
            df = df.drop_duplicates(subset=['time', 'bid', 'ask']).sort_values('time').reset_index(drop=True)

            # Paso 5: Validar
            validation_result = validate_ticks_dataframe(df)

            if not validation_result.is_valid:
                logger.warning(f"Validación con advertencias: {validation_result.errors}")
                emit(
                    'ticks.validation.warning',
                    source='DataManager',
                    symbol=symbol,
                    errors=validation_result.errors[:3]
                )

            # Paso 6: Almacenar persistentemente
            try:
                self.store.store(symbol, 'TICKS', df)
            except Exception as e:
                logger.error(f"Error almacenando ticks: {e}")
                # No fallar si el almacenamiento tiene problemas

            # Paso 7: Actualizar caché
            self.cache.update(symbol, 'TICKS', df, from_dt, to_dt)

            # Paso 8: Retornar datos filtrados por rango solicitado
            mask = (df['time'] >= from_dt) & (df['time'] <= to_dt)
            result_df = df[mask].reset_index(drop=True)

            emit(
                'ticks.download.completed',
                source='DataManager',
                symbol=symbol,
                group=group,
                rows=len(result_df),
                source_type='mt5',
                start_date=result_df['time'].min(),
                end_date=result_df['time'].max()
            )

            logger.info(f"✓ Descargados {len(result_df)} ticks de {symbol} ({group})")
            return result_df

        except Exception as e:
            logger.error(f"Error descargando ticks: {e}")
            emit(
                'ticks.download.error',
                source='DataManager',
                symbol=symbol,
                group=group,
                error=str(e)
            )
            raise DataDownloadError(f"Error descargando ticks {symbol} ({group}): {e}")

    def batch_download(
        self,
        requests: List[Dict],
        parallel: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        Descarga múltiples símbolos/timeframes en lote.

        Args:
            requests: Lista de dicts con keys: symbol, timeframe, from_dt, to_dt
            parallel: Si True, descarga en paralelo (con thread pool)

        Returns:
            Dict con {(symbol, timeframe): DataFrame}
        """
        results = {}

        if parallel:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {}
                for req in requests:
                    future = executor.submit(
                        self.download,
                        req['symbol'],
                        req['timeframe'],
                        req['from_dt'],
                        req.get('to_dt'),
                        req.get('force_refresh', False)
                    )
                    futures[future] = (req['symbol'], req['timeframe'])

                for future in concurrent.futures.as_completed(futures):
                    symbol, timeframe = futures[future]
                    try:
                        df = future.result()
                        results[(symbol, timeframe)] = df
                    except Exception as e:
                        logger.error(f"Error en {symbol}/{timeframe}: {e}")
        else:
            for req in requests:
                try:
                    df = self.download(
                        req['symbol'],
                        req['timeframe'],
                        req['from_dt'],
                        req.get('to_dt'),
                        req.get('force_refresh', False)
                    )
                    results[(req['symbol'], req['timeframe'])] = df
                except Exception as e:
                    logger.error(f"Error en {req['symbol']}/{req['timeframe']}: {e}")

        return results

    def get_available_data(self, symbol: str, timeframe: str) -> Optional[tuple]:
        """
        Obtiene el rango de fechas disponibles para un símbolo/timeframe.

        Args:
            symbol: Símbolo
            timeframe: Marco temporal

        Returns:
            Tupla (date_min, date_max) o None si no hay datos
        """
        return self.store.get_date_range(symbol, timeframe)

    def clear_cache(self, symbol: str = None, timeframe: str = None) -> None:
        """
        Limpia la caché.

        Args:
            symbol: Si especificado, limpia solo este símbolo
            timeframe: Si especificado, limpia solo este timeframe
        """
        self.cache.invalidate(symbol, timeframe)
        logger.info(f"Caché limpiada: symbol={symbol}, timeframe={timeframe}")

    def get_cache_stats(self) -> Dict:
        """Obtiene estadísticas del caché."""
        return self.cache.get_stats()

    def get_store_stats(self) -> Dict:
        """Obtiene estadísticas del almacenamiento."""
        return self.store.get_stats()

    def __repr__(self) -> str:
        cache_stats = self.get_cache_stats()
        store_stats = self.get_store_stats()
        return (
            f"DataManager(cache_hit_rate={cache_stats['hit_rate_pct']}%, "
            f"stored_symbols={store_stats['num_symbols']}, "
            f"total_rows={store_stats['total_rows']})"
        )
