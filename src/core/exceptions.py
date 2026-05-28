"""
Excepciones personalizadas para el sistema NotOverfitting.
"""

class NotOverfittingException(Exception):
    """Clase base para todas las excepciones del sistema."""
    pass

class ConfigurationError(NotOverfittingException):
    """Error al cargar o validar la configuración."""
    pass

class DataDownloadError(NotOverfittingException):
    """Error al descargar datos de MetaTrader 5 o cualquier otra fuente."""
    pass

class PipelineError(NotOverfittingException):
    """Error durante la ejecución del pipeline de features."""
    pass

class ModelTrainingError(NotOverfittingException):
    """Error durante el entrenamiento del modelo."""
    pass

class MT5ConnectionError(NotOverfittingException):
    """Error al conectar con MetaTrader 5."""
    pass
