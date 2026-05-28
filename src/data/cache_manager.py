"""
CacheManager: Sistema de caché inteligente para datos OHLCV.

Gestiona caché en memoria con validación de rangos, invalidación temporal
y persistencia opcional en disco.
"""

import threading
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger(__name__)


class CacheEntry:
    """Representa una entrada en el caché con metadatos."""

    def __init__(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        date_from: datetime,
        date_to: datetime,
        ttl_seconds: int = 3600
    ):
        """
        Inicializa una entrada de caché.

        Args:
            symbol: Símbolo (ej: 'EURUSD')
            timeframe: Marco temporal (ej: 'H1')
            df: DataFrame con datos
            date_from: Fecha inicio del rango
            date_to: Fecha fin del rango
            ttl_seconds: Tiempo de vida en segundos (0 = infinito)
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.df = df.copy()
        self.date_from = date_from
        self.date_to = date_to
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.ttl_seconds = ttl_seconds
        self.access_count = 0

    def is_expired(self) -> bool:
        """Verifica si la entrada ha expirado."""
        if self.ttl_seconds == 0:
            return False
        expiry = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiry

    def covers_range(self, from_date: datetime, to_date: datetime) -> bool:
        """
        Verifica si el caché cubre el rango solicitado.

        Args:
            from_date: Fecha inicio solicitada
            to_date: Fecha fin solicitada

        Returns:
            True si [from_date, to_date] ⊆ [self.date_from, self.date_to]
        """
        return from_date >= self.date_from and to_date <= self.date_to

    def get_missing_ranges(
        self,
        from_date: datetime,
        to_date: datetime
    ) -> list:
        """
        Calcula qué rangos de fechas faltan en el caché.

        Args:
            from_date: Fecha inicio solicitada
            to_date: Fecha fin solicitada

        Returns:
            Lista de tuplas (start, end) con rangos faltantes
        """
        missing = []

        if from_date < self.date_from:
            missing.append((from_date, min(to_date, self.date_from)))

        if to_date > self.date_to:
            missing.append((max(from_date, self.date_to), to_date))

        return missing

    def get_data(self, from_date: datetime = None, to_date: datetime = None) -> pd.DataFrame:
        """
        Obtiene datos del caché, opcionalmente filtrados por rango.

        Args:
            from_date: Fecha inicio (si None, usa self.date_from)
            to_date: Fecha fin (si None, usa self.date_to)

        Returns:
            DataFrame filtrado
        """
        self.last_accessed = datetime.now()
        self.access_count += 1

        if from_date is None:
            from_date = self.date_from
        if to_date is None:
            to_date = self.date_to

        mask = (self.df['time'] >= from_date) & (self.df['time'] <= to_date)
        return self.df[mask].copy()

    def __repr__(self) -> str:
        expired = "EXPIRED" if self.is_expired() else "VALID"
        rows = len(self.df)
        return (
            f"CacheEntry({self.symbol}/{self.timeframe}, "
            f"{rows} rows, {self.date_from.date()} → {self.date_to.date()}, "
            f"{expired}, access_count={self.access_count})"
        )


class CacheManager:
    """
    Sistema de caché thread-safe para datos OHLCV.

    Maneja:
    - Caché en memoria por símbolo/timeframe
    - Validación de cobertura de rangos
    - Invalidación temporal (TTL)
    - Estadísticas de hits/misses
    """

    def __init__(
        self,
        ttl_seconds: int = 3600,
        cache_dir: Optional[Path] = None,
        enable_disk_cache: bool = False
    ):
        """
        Inicializa el CacheManager.

        Args:
            ttl_seconds: Tiempo de vida de entradas (0 = infinito)
            cache_dir: Directorio para caché en disco (si enable_disk_cache=True)
            enable_disk_cache: Si True, persiste caché en disco
        """
        self.ttl_seconds = ttl_seconds
        self.cache_dir = cache_dir or Path("./cache")
        self.enable_disk_cache = enable_disk_cache
        
        # Caché en memoria: {(symbol, timeframe): CacheEntry}
        self._cache: Dict[Tuple[str, str], CacheEntry] = {}
        self._lock = threading.RLock()
        
        # Estadísticas
        self._hits = 0
        self._misses = 0
        self._total_requests = 0
        
        if self.enable_disk_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Caché en disco habilitado: {self.cache_dir}")

    def has_data(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime
    ) -> bool:
        """
        Verifica si el caché tiene datos que cubren el rango solicitado.

        Args:
            symbol: Símbolo
            timeframe: Marco temporal
            from_date: Fecha inicio
            to_date: Fecha fin

        Returns:
            True si el caché cubre completamente el rango
        """
        with self._lock:
            key = (symbol, timeframe)
            
            if key not in self._cache:
                self._misses += 1
                self._total_requests += 1
                return False
            
            entry = self._cache[key]
            
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                self._total_requests += 1
                return False
            
            if entry.covers_range(from_date, to_date):
                self._hits += 1
                self._total_requests += 1
                return True
            
            self._misses += 1
            self._total_requests += 1
            return False

    def get_data(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Obtiene datos del caché si están disponibles.

        Args:
            symbol: Símbolo
            timeframe: Marco temporal
            from_date: Fecha inicio
            to_date: Fecha fin

        Returns:
            DataFrame si hay caché válido y cubre el rango, None en caso contrario
        """
        with self._lock:
            key = (symbol, timeframe)
            
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            if entry.is_expired():
                del self._cache[key]
                return None
            
            if not entry.covers_range(from_date, to_date):
                return None
            
            return entry.get_data(from_date, to_date)

    def get_missing_ranges(
        self,
        symbol: str,
        timeframe: str,
        from_date: datetime,
        to_date: datetime
    ) -> list:
        """
        Calcula qué rangos de fechas faltan en el caché.

        Args:
            symbol: Símbolo
            timeframe: Marco temporal
            from_date: Fecha inicio solicitada
            to_date: Fecha fin solicitada

        Returns:
            Lista de tuplas (start, end) con rangos faltantes.
            Si no hay caché, retorna [(from_date, to_date)]
        """
        with self._lock:
            key = (symbol, timeframe)
            
            if key not in self._cache:
                return [(from_date, to_date)]
            
            entry = self._cache[key]
            
            if entry.is_expired():
                del self._cache[key]
                return [(from_date, to_date)]
            
            return entry.get_missing_ranges(from_date, to_date)

    def update(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        from_date: datetime,
        to_date: datetime
    ) -> None:
        """
        Actualiza o agrega datos al caché.

        Args:
            symbol: Símbolo
            timeframe: Marco temporal
            df: DataFrame con datos nuevos
            from_date: Fecha inicio del rango
            to_date: Fecha fin del rango
        """
        with self._lock:
            key = (symbol, timeframe)
            
            entry = CacheEntry(
                symbol=symbol,
                timeframe=timeframe,
                df=df,
                date_from=from_date,
                date_to=to_date,
                ttl_seconds=self.ttl_seconds
            )
            
            self._cache[key] = entry
            logger.debug(f"Caché actualizado: {entry}")

    def invalidate(self, symbol: str = None, timeframe: str = None) -> None:
        """
        Invalida entradas de caché.

        Args:
            symbol: Si especificado, invalida solo este símbolo
            timeframe: Si especificado, invalida solo este timeframe
        """
        with self._lock:
            if symbol is None and timeframe is None:
                # Limpiar todo
                self._cache.clear()
                logger.info("Caché completamente limpiado")
            else:
                # Limpiar específico
                keys_to_delete = []
                for (sym, tf) in self._cache.keys():
                    if (symbol is None or sym == symbol) and \
                       (timeframe is None or tf == timeframe):
                        keys_to_delete.append((sym, tf))
                
                for key in keys_to_delete:
                    del self._cache[key]
                
                logger.info(f"Invalidadas {len(keys_to_delete)} entradas de caché")

    def clear_expired(self) -> int:
        """
        Limpia todas las entradas expiradas.

        Returns:
            Número de entradas removidas
        """
        with self._lock:
            keys_to_delete = []
            for key, entry in self._cache.items():
                if entry.is_expired():
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self._cache[key]
            
            if keys_to_delete:
                logger.debug(f"Removidas {len(keys_to_delete)} entradas expiradas")
            
            return len(keys_to_delete)

    def get_stats(self) -> Dict[str, any]:
        """
        Obtiene estadísticas del caché.

        Returns:
            Dict con hits, misses, hit_rate, num_entries
        """
        with self._lock:
            hit_rate = (
                (self._hits / self._total_requests * 100)
                if self._total_requests > 0 else 0
            )
            
            # Contar datos en caché
            total_rows = sum(len(entry.df) for entry in self._cache.values())
            
            return {
                'hits': self._hits,
                'misses': self._misses,
                'total_requests': self._total_requests,
                'hit_rate_pct': round(hit_rate, 2),
                'num_entries': len(self._cache),
                'total_rows_cached': total_rows,
            }

    def list_cached(self) -> Dict[Tuple[str, str], CacheEntry]:
        """
        Lista todas las entradas en caché.

        Returns:
            Dict con (symbol, timeframe) -> CacheEntry
        """
        with self._lock:
            return {key: entry for key, entry in self._cache.items()}

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"CacheManager(entries={stats['num_entries']}, "
            f"hits={stats['hits']}, misses={stats['misses']}, "
            f"hit_rate={stats['hit_rate_pct']}%)"
        )
