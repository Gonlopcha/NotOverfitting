"""
Sistema de logging centralizado.
Carga la configuración desde config/logging.yaml y envia logs al EventBus.
"""
import logging
import logging.config
import yaml
import threading
from pathlib import Path
from typing import Any, Dict

from src.core.event_bus import emit


class EventBusLogHandler(logging.Handler):
    """
    Handler de logging que emite eventos al EventBus.
    """
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # Evitar emitir eventos si provienen del propio event_bus para evitar ciclos infinitos
            if record.name == "src.core.event_bus" or "event_bus" in record.name:
                return
                
            emit(
                event_name='log.message',
                source='logger',
                level=record.levelname,
                message=msg,
                module=record.name
            )
        except Exception:
            self.handleError(record)


class Logger:
    """
    Singleton Wrapper para el sistema de logging.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Logger, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, default_path: str = 'config/logging.yaml', default_level: int = logging.INFO):
        with self._lock:
            if self._initialized:
                return
            
            self._setup(default_path, default_level)
            self._initialized = True

    def _setup(self, default_path: str, default_level: int) -> None:
        path = Path(default_path)
        if path.exists():
            with open(path, 'rt', encoding='utf-8') as f:
                try:
                    config = yaml.safe_load(f.read())
                    # Asegurar que el directorio de logs existe
                    if 'handlers' in config and 'file' in config['handlers']:
                        log_file = config['handlers']['file'].get('filename')
                        if log_file:
                            log_path = Path(log_file)
                            log_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    logging.config.dictConfig(config)
                except Exception as e:
                    print(f"Error al cargar la configuración de logging desde {path}: {e}")
                    print("Usando configuración básica de fallback.")
                    logging.basicConfig(level=default_level)
        else:
            print(f"Archivo de configuración de logging {path} no encontrado.")
            print("Usando configuración básica de fallback.")
            logging.basicConfig(level=default_level)

        # Configurar EventBusHandler al root logger para capturar todo
        root_logger = logging.getLogger()
        
        # Evitar duplicados si ya está agregado
        has_eventbus_handler = any(isinstance(h, EventBusLogHandler) for h in root_logger.handlers)
        if not has_eventbus_handler:
            eb_handler = EventBusLogHandler()
            eb_handler.setFormatter(logging.Formatter('%(message)s'))
            root_logger.addHandler(eb_handler)

    def get_logger(self, name: str) -> logging.Logger:
        return logging.getLogger(name)


# Instancia global por defecto
_logger_instance = Logger()


def get_logger(name: str = None) -> logging.Logger:
    """
    Obtiene un logger específico.
    
    Args:
        name: Nombre del logger (normalmente __name__ del módulo)
        
    Returns:
        Logger configurado
    """
    if name is None:
        name = "NotOverfitting"
    return _logger_instance.get_logger(name)
