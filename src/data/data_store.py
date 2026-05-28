"""
DataStore: Almacenamiento dual SQLite + Parquet para datos OHLCV.

Gestiona persistencia de metadatos (SQLite) y datos históricos (Parquet particionado).
Interfaz unificada para lectura/escritura.
"""

import sqlite3
import hashlib
import threading
from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path
import pandas as pd

from src.core.logger import get_logger
from src.data.schemas import DataMetadata

logger = get_logger(__name__)


class DataStore:
    """
    Almacenamiento dual thread-safe para datos OHLCV.

    Estructura:
    - metadata.db: SQLite con catálogo de archivos
    - ohlcv/{symbol}/{timeframe}/*.parquet: Datos particionados por año
    """

    def __init__(self, store_path: Path = None):
        """
        Inicializa el DataStore.

        Args:
            store_path: Ruta base para almacenamiento (default: ./data_store)
        """
        self.store_path = Path(store_path or "./data_store")
        self.ohlcv_path = self.store_path / "ohlcv"
        self.metadata_db = self.store_path / "metadata.db"
        
        self._lock = threading.RLock()
        
        # Crear directorios
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.ohlcv_path.mkdir(parents=True, exist_ok=True)
        
        # Inicializar base de datos
        self._init_database()
        logger.info(f"DataStore inicializado: {self.store_path}")

    def _init_database(self) -> None:
        """Inicializa la base de datos SQLite si no existe."""
        with sqlite3.connect(self.metadata_db) as conn:
            cursor = conn.cursor()
            
            # Tabla de metadatos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    date_from TIMESTAMP NOT NULL,
                    date_to TIMESTAMP NOT NULL,
                    rows INTEGER NOT NULL,
                    checksum TEXT NOT NULL,
                    parquet_file TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timeframe, parquet_file)
                )
            """)
            
            # Índices para búsquedas rápidas
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_timeframe
                ON metadata(symbol, timeframe)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_dates
                ON metadata(date_from, date_to)
            """)
            
            conn.commit()

    def _calculate_checksum(self, df: pd.DataFrame) -> str:
        """
        Calcula un checksum SHA256 del DataFrame.

        Args:
            df: DataFrame

        Returns:
            Checksum en hexadecimal
        """
        # Usar representación binaria del DataFrame
        data_bytes = pd.util.hash_pandas_object(df, index=True).values
        return hashlib.sha256(data_bytes).hexdigest()

    def _get_partition_path(
        self,
        symbol: str,
        timeframe: str,
        date_from: datetime
    ) -> Path:
        """
        Obtiene la ruta del archivo Parquet para una partición (por año).

        Args:
            symbol: Símbolo
            timeframe: Marco temporal
            date_from: Fecha (se usa el año para determinar la partición)

        Returns:
            Path al archivo parquet
        """
        year = date_from.year
        symbol_dir = self.ohlcv_path / symbol / timeframe
        symbol_dir.mkdir(parents=True, exist_ok=True)
        
        return symbol_dir / f"{year}.parquet"

    def store(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame
    ) -> DataMetadata:
        """
        Almacena datos OHLCV en el DataStore.

        Args:
            symbol: Símbolo (ej: 'EURUSD')
            timeframe: Marco temporal (ej: 'H1')
            df: DataFrame con columnas ['time', 'open', 'high', 'low', 'close', 'volume']

        Returns:
            DataMetadata con información del almacenamiento

        Raises:
            ValueError: Si el DataFrame no tiene las columnas requeridas
        """
        if df.empty:
            raise ValueError("DataFrame vacío")
        
        required_cols = ['time', 'open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Columnas faltantes: {missing}")
        
        with self._lock:
            # Asegurar que time es datetime
            df = df.copy()
            df['time'] = pd.to_datetime(df['time'])
            df = df.sort_values('time').reset_index(drop=True)
            
            date_from = df['time'].min()
            date_to = df['time'].max()
            checksum = self._calculate_checksum(df)
            
            # Obtener ruta de partición
            parquet_path = self._get_partition_path(symbol, timeframe, date_from)
            relative_path = parquet_path.relative_to(self.store_path)
            
            # Escribir Parquet
            try:
                df.to_parquet(parquet_path, index=False, compression='snappy')
            except Exception as e:
                logger.error(f"Error escribiendo Parquet {parquet_path}: {e}")
                raise
            
            # Registrar en SQLite
            metadata = DataMetadata(
                symbol=symbol,
                timeframe=timeframe,
                date_from=date_from,
                date_to=date_to,
                rows=len(df),
                checksum=checksum
            )
            
            with sqlite3.connect(self.metadata_db) as conn:
                cursor = conn.cursor()
                
                # Insertar o reemplazar metadatos
                cursor.execute("""
                    INSERT OR REPLACE INTO metadata
                    (symbol, timeframe, date_from, date_to, rows, checksum, parquet_file, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    symbol,
                    timeframe,
                    date_from.isoformat(),
                    date_to.isoformat(),
                    len(df),
                    checksum,
                    str(relative_path)
                ))
                
                conn.commit()
            
            logger.info(f"Almacenados {len(df)} registros: {symbol}/{timeframe} ({date_from.date()} → {date_to.date()})")
            return metadata

    def load(
        self,
        symbol: str,
        timeframe: str,
        date_from: datetime,
        date_to: datetime
    ) -> Optional[pd.DataFrame]:
        """
        Carga datos históricos del almacenamiento.

        Args:
            symbol: Símbolo
            timeframe: Marco temporal
            date_from: Fecha inicio (inclusiva)
            date_to: Fecha fin (inclusiva)

        Returns:
            DataFrame si existen datos, None si no hay nada
        """
        with self._lock:
            # Obtener archivos Parquet relevantes (pueden estar en múltiples años)
            parquet_files = []
            
            for year in range(date_from.year, date_to.year + 1):
                path = self.ohlcv_path / symbol / timeframe / f"{year}.parquet"
                if path.exists():
                    parquet_files.append(path)
            
            if not parquet_files:
                logger.debug(f"No hay datos para {symbol}/{timeframe} ({date_from.date()} → {date_to.date()})")
                return None
            
            # Cargar todos los archivos
            dfs = []
            for path in parquet_files:
                try:
                    df = pd.read_parquet(path)
                    dfs.append(df)
                except Exception as e:
                    logger.error(f"Error leyendo {path}: {e}")
                    continue
            
            if not dfs:
                return None
            
            # Combinar y filtrar por rango
            df = pd.concat(dfs, ignore_index=True)
            df['time'] = pd.to_datetime(df['time'])
            
            mask = (df['time'] >= date_from) & (df['time'] <= date_to)
            df = df[mask].sort_values('time').reset_index(drop=True)
            
            if df.empty:
                logger.debug(f"No hay datos en rango para {symbol}/{timeframe}")
                return None
            
            logger.debug(f"Cargados {len(df)} registros: {symbol}/{timeframe}")
            return df

    def get_metadata(self, symbol: str, timeframe: str) -> List[DataMetadata]:
        """
        Obtiene metadatos de todas las particiones de un símbolo/timeframe.

        Args:
            symbol: Símbolo
            timeframe: Marco temporal

        Returns:
            Lista de DataMetadata
        """
        with self._lock:
            with sqlite3.connect(self.metadata_db) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM metadata
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY date_from
                """, (symbol, timeframe))
                
                rows = cursor.fetchall()
                
                metadata_list = [
                    DataMetadata(
                        symbol=row['symbol'],
                        timeframe=row['timeframe'],
                        date_from=datetime.fromisoformat(row['date_from']),
                        date_to=datetime.fromisoformat(row['date_to']),
                        rows=row['rows'],
                        checksum=row['checksum'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        last_updated=datetime.fromisoformat(row['last_updated'])
                    )
                    for row in rows
                ]
                
                return metadata_list

    def get_date_range(self, symbol: str, timeframe: str) -> Optional[tuple]:
        """
        Obtiene el rango de fechas disponibles para un símbolo/timeframe.

        Args:
            symbol: Símbolo
            timeframe: Marco temporal

        Returns:
            Tupla (date_min, date_max) o None si no hay datos
        """
        metadata = self.get_metadata(symbol, timeframe)
        
        if not metadata:
            return None
        
        date_min = min(m.date_from for m in metadata)
        date_max = max(m.date_to for m in metadata)
        
        return (date_min, date_max)

    def list_symbols(self) -> List[str]:
        """
        Lista todos los símbolos con datos almacenados.

        Returns:
            Lista de símbolos únicos
        """
        with self._lock:
            with sqlite3.connect(self.metadata_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT symbol FROM metadata")
                symbols = [row[0] for row in cursor.fetchall()]
                return symbols

    def list_timeframes(self, symbol: str) -> List[str]:
        """
        Lista todos los timeframes disponibles para un símbolo.

        Args:
            symbol: Símbolo

        Returns:
            Lista de timeframes únicos
        """
        with self._lock:
            with sqlite3.connect(self.metadata_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT DISTINCT timeframe FROM metadata WHERE symbol = ?",
                    (symbol,)
                )
                timeframes = [row[0] for row in cursor.fetchall()]
                return timeframes

    def delete(self, symbol: str, timeframe: str, year: int = None) -> None:
        """
        Elimina datos del almacenamiento.

        Args:
            symbol: Símbolo
            timeframe: Marco temporal
            year: Año específico (si None, elimina todo el símbolo/timeframe)
        """
        with self._lock:
            with sqlite3.connect(self.metadata_db) as conn:
                cursor = conn.cursor()
                
                if year is None:
                    # Eliminar todo para este símbolo/timeframe
                    cursor.execute(
                        "DELETE FROM metadata WHERE symbol = ? AND timeframe = ?",
                        (symbol, timeframe)
                    )
                else:
                    # Eliminar año específico
                    cursor.execute(
                        """DELETE FROM metadata 
                           WHERE symbol = ? AND timeframe = ? 
                           AND strftime('%Y', date_from) = ?""",
                        (symbol, timeframe, str(year))
                    )
                
                conn.commit()
            
            # Eliminar archivos Parquet
            symbol_dir = self.ohlcv_path / symbol / timeframe
            if symbol_dir.exists():
                if year is None:
                    import shutil
                    shutil.rmtree(symbol_dir)
                else:
                    parquet_file = symbol_dir / f"{year}.parquet"
                    if parquet_file.exists():
                        parquet_file.unlink()
                
                logger.info(f"Eliminados datos: {symbol}/{timeframe}")

    def get_stats(self) -> Dict[str, any]:
        """
        Obtiene estadísticas del almacenamiento.

        Returns:
            Dict con información de uso
        """
        with self._lock:
            with sqlite3.connect(self.metadata_db) as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(DISTINCT symbol) FROM metadata")
                num_symbols = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT timeframe) FROM metadata")
                num_timeframes = cursor.fetchone()[0]
                
                cursor.execute("SELECT SUM(rows) FROM metadata")
                total_rows = cursor.fetchone()[0] or 0
                
                cursor.execute("SELECT COUNT(*) FROM metadata")
                num_partitions = cursor.fetchone()[0]
                
                # Tamaño en disco
                total_size = 0
                for parquet_file in self.ohlcv_path.rglob("*.parquet"):
                    total_size += parquet_file.stat().st_size
                
                return {
                    'num_symbols': num_symbols,
                    'num_timeframes': num_timeframes,
                    'total_rows': total_rows,
                    'num_partitions': num_partitions,
                    'disk_size_mb': round(total_size / (1024 * 1024), 2)
                }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"DataStore({stats['num_symbols']} symbols, "
            f"{stats['total_rows']} rows, "
            f"{stats['disk_size_mb']}MB)"
        )
