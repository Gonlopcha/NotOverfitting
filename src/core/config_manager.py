"""
Gestor de configuración centralizado.
Lee el archivo config/default.yaml, permite merge con otros diccionarios/YAMLs, 
y proporciona acceso seguro y tipado.
"""
import yaml
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.core.exceptions import ConfigurationError

class ConfigManager:
    """
    Singleton para gestionar la configuración del sistema.
    Thread-safe.
    """
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ConfigManager, cls).__new__(cls)
                cls._instance._config = {}
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        with self._lock:
            if not self._initialized:
                self._load_config()
                self._initialized = True

    def _load_config(self, config_path: str = "config/default.yaml") -> None:
        """Carga la configuración desde el archivo YAML."""
        path = Path(config_path)
        if not path.exists():
            raise ConfigurationError(f"El archivo de configuración {config_path} no existe.")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
                self.merge(config_data)
        except Exception as e:
            raise ConfigurationError(f"Error parseando el archivo YAML {config_path}: {e}")

    def merge(self, new_config: Dict[str, Any]) -> None:
        """
        Fusiona un nuevo diccionario de configuración con el existente.
        """
        def _deep_merge(d: dict, u: dict) -> dict:
            for k, v in u.items():
                if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                    d[k] = _deep_merge(d.get(k, {}), v)
                else:
                    d[k] = v
            return d

        with self._lock:
            self._config = _deep_merge(self._config, new_config)

    def set(self, key: str, value: Any) -> None:
        """
        Establece un valor de configuración usando dot notation.
        """
        with self._lock:
            keys = key.split('.')
            d = self._config
            for k in keys[:-1]:
                if k not in d or not isinstance(d[k], dict):
                    d[k] = {}
                d = d[k]
            d[keys[-1]] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor de la configuración usando dot notation (ej: 'mt5.timeout').
        """
        with self._lock:
            keys = key.split('.')
            value = self._config
            try:
                for k in keys:
                    value = value[k]
                return value
            except (KeyError, TypeError):
                return default

    def get_str(self, key: str, default: str = "") -> str:
        val = self.get(key, default)
        return str(val) if val is not None else default

    def get_int(self, key: str, default: int = 0) -> int:
        val = self.get(key, default)
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self.get(key, default)
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ('true', 'yes', '1', 't')
        return bool(val) if val is not None else default

    def get_list(self, key: str, default: List[Any] = None) -> List[Any]:
        val = self.get(key, default)
        return val if isinstance(val, list) else (default or [])

    def get_dict(self, key: str, default: Dict[str, Any] = None) -> Dict[str, Any]:
        val = self.get(key, default)
        return val if isinstance(val, dict) else (default or {})

# Instancia global para fácil importación
config = ConfigManager()
