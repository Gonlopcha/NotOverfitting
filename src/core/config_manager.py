"""
Gestor de configuración centralizado.
Lee el archivo config/default.yaml y permite acceso seguro.
"""
import yaml
from pathlib import Path
from typing import Any, Dict
from src.core.exceptions import ConfigurationError

class ConfigManager:
    """
    Singleton para gestionar la configuración del sistema.
    """
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self, config_path: str = "config/default.yaml") -> None:
        """Carga la configuración desde el archivo YAML."""
        path = Path(config_path)
        if not path.exists():
            raise ConfigurationError(f"El archivo de configuración {config_path} no existe.")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        except Exception as e:
            raise ConfigurationError(f"Error parseando el archivo YAML {config_path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor de la configuración usando dot notation (ej: 'mt5.timeout').
        """
        keys = key.split('.')
        value = self._config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

# Instancia global para fácil importación
config = ConfigManager()
