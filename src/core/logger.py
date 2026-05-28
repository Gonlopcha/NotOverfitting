"""
Sistema de logging centralizado.
Carga la configuración desde config/logging.yaml
"""
import logging
import logging.config
import yaml
from pathlib import Path

def setup_logger(default_path='config/logging.yaml', default_level=logging.INFO):
    """
    Configura el sistema de logging basado en un archivo YAML.
    """
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

    return logging.getLogger("NotOverfitting")

# Instancia global por defecto
logger = setup_logger()


def get_logger(name: str = None) -> logging.Logger:
    """
    Obtiene un logger específico.
    
    Args:
        name: Nombre del logger (normalmente __name__ del módulo)
        
    Returns:
        Logger configurado
    """
    if name is None:
        return logger
    return logging.getLogger(name)
