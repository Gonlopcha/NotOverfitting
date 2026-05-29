"""
Registry: Sistema de registro dinámico con decoradores.

Permite auto-descubrimiento y registro de features, estrategias y componentes
sin necesidad de importaciones manuales.
"""

from typing import Callable, Dict, Type, Any, Optional, List
from abc import ABC
import threading
from functools import wraps

from src.core.exceptions import NotOverfittingException


class RegistryError(NotOverfittingException):
    """Error al registrar o acceder a un componente en el registry."""
    pass


class Registry:
    """
    Registro dinámico para features, estrategias y otros componentes.
    
    Thread-safe con locks. Soporta decoradores para registro automático.
    """
    
    def __init__(self, component_type: str):
        """
        Inicializa un registro para un tipo específico de componente.
        
        Args:
            component_type: Nombre descriptivo del tipo (ej: 'feature', 'strategy')
        """
        self.component_type = component_type
        self._components: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def register(self, name: str, component: Any = None, metadata: Optional[Dict[str, Any]] = None) -> Any:
        """
        Registra un componente en el registry. Puede usarse como función o decorador.
        
        Args:
            name: Identificador único del componente
            component: El componente a registrar (clase, función, instancia)
            metadata: Información adicional sobre el componente
            
        Raises:
            RegistryError: Si el nombre ya está registrado
            
        Example:
            >>> registry = Registry('feature')
            >>> def my_feature(df):
            ...     return df['high'] - df['low']
            >>> registry.register('volatility', my_feature, {'description': 'Simple volatility'})
            
            Como decorador:
            >>> @registry.register('volatility')
            >>> def my_feature(df): return df
        """
        if component is None:
            # Uso como decorador
            def decorator(comp: Any):
                self.register(name, comp, metadata)
                return comp
            return decorator

        with self._lock:
            if name in self._components:
                raise RegistryError(
                    f"'{name}' ya está registrado en {self.component_type}. "
                    f"Usa unregister() primero si deseas reemplazarlo."
                )
            
            self._components[name] = {
                'component': component,
                'metadata': metadata or {},
                'type': type(component).__name__,
            }

    def unregister(self, name: str) -> bool:
        """
        Desregistra un componente.
        
        Args:
            name: Identificador del componente a remover
            
        Returns:
            True si fue removido, False si no existía
        """
        with self._lock:
            if name in self._components:
                del self._components[name]
                return True
            return False

    def get(self, name: str) -> Any:
        """
        Obtiene un componente registrado.
        
        Args:
            name: Identificador del componente
            
        Returns:
            El componente registrado
            
        Raises:
            RegistryError: Si el componente no existe
        """
        with self._lock:
            if name not in self._components:
                available = ', '.join(self._components.keys())
                raise RegistryError(
                    f"'{name}' no está registrado en {self.component_type}. "
                    f"Disponibles: {available if available else 'ninguno'}"
                )
            return self._components[name]['component']

    def get_all(self) -> Dict[str, Any]:
        """
        Obtiene todos los componentes registrados.
        
        Returns:
            Dict con nombre -> componente
        """
        with self._lock:
            return {name: info['component'] for name, info in self._components.items()}

    def list_registered(self) -> Dict[str, Dict[str, Any]]:
        """
        Lista información detallada de todos los componentes registrados.
        
        Returns:
            Dict con nombre -> {component, metadata, type}
        """
        with self._lock:
            return {name: info.copy() for name, info in self._components.items()}

    def exists(self, name: str) -> bool:
        """Verifica si un componente existe en el registry."""
        with self._lock:
            return name in self._components

    def clear(self) -> None:
        """Limpia todos los registros (útil para tests)."""
        with self._lock:
            self._components.clear()

    def __len__(self) -> int:
        """Retorna el número de componentes registrados."""
        with self._lock:
            return len(self._components)

    def __repr__(self) -> str:
        with self._lock:
            names = list(self._components.keys())
        return f"Registry({self.component_type}) [n={len(names)}] {names}"


# Registries globales para cada tipo de componente
_feature_registry = Registry('feature')
_strategy_registry = Registry('strategy')
_transformer_registry = Registry('transformer')


def get_feature_registry() -> Registry:
    """Obtiene el registry global de features."""
    return _feature_registry


def get_strategy_registry() -> Registry:
    """Obtiene el registry global de estrategias."""
    return _strategy_registry


def get_transformer_registry() -> Registry:
    """Obtiene el registry global de transformadores."""
    return _transformer_registry


# Decoradores para registro automático

def register_feature(name: str = None, **metadata):
    """
    Decorador para registrar automáticamente una función/clase como feature.
    
    Args:
        name: Nombre del feature (si no se proporciona, usa el nombre de la función)
        **metadata: Información adicional (description, version, tags, etc.)
        
    Example:
        >>> @register_feature(description='RSI indicator')
        ... def rsi_feature(df):
        ...     # cálculo del RSI
        ...     return rsi_values
        
        >>> @register_feature('custom_ma')
        ... def moving_average(df):
        ...     return df['close'].rolling(20).mean()
    """
    def decorator(func_or_class):
        feature_name = name or func_or_class.__name__
        
        # Agregar docstring al metadata si existe
        if func_or_class.__doc__:
            metadata.setdefault('description', func_or_class.__doc__)
        
        _feature_registry.register(feature_name, func_or_class, metadata)
        
        # Retornar el objeto sin modificar (decorador transparente)
        @wraps(func_or_class)
        def wrapper(*args, **kwargs):
            return func_or_class(*args, **kwargs)
        
        # Preservar atributos originales
        wrapper.__name__ = func_or_class.__name__
        wrapper.__doc__ = func_or_class.__doc__
        
        return func_or_class  # Retornar el original, no el wrapper
    
    return decorator


def register_strategy(name: str = None, **metadata):
    """
    Decorador para registrar automáticamente una clase estrategia.
    
    Args:
        name: Nombre de la estrategia (si no se proporciona, usa el nombre de la clase)
        **metadata: Información adicional (description, version, tags, etc.)
        
    Example:
        >>> @register_strategy('ml_strategy_v1', version='1.0')
        ... class MLStrategy(StrategyBase):
        ...     def on_bar(self, bar):
        ...         pass
    """
    def decorator(strategy_class):
        strategy_name = name or strategy_class.__name__
        
        if strategy_class.__doc__:
            metadata.setdefault('description', strategy_class.__doc__)
        
        _strategy_registry.register(strategy_name, strategy_class, metadata)
        return strategy_class
    
    return decorator


def register_transformer(name: str = None, **metadata):
    """
    Decorador para registrar automáticamente una clase transformadora.
    
    Args:
        name: Nombre del transformador (si no se proporciona, usa el nombre de la clase)
        **metadata: Información adicional
    """
    def decorator(transformer_class):
        transformer_name = name or transformer_class.__name__
        
        if transformer_class.__doc__:
            metadata.setdefault('description', transformer_class.__doc__)
        
        _transformer_registry.register(transformer_name, transformer_class, metadata)
        return transformer_class
    
    return decorator


# Funciones de conveniencia para acceso rápido

def get_feature(name: str) -> Callable:
    """Obtiene una función feature registrada."""
    return _feature_registry.get(name)


def get_strategy(name: str) -> Type:
    """Obtiene una clase estrategia registrada."""
    return _strategy_registry.get(name)


def get_transformer(name: str) -> Type:
    """Obtiene una clase transformadora registrada."""
    return _transformer_registry.get(name)


def list_all_features() -> Dict[str, Dict[str, Any]]:
    """Lista todos los features registrados con metadata."""
    return _feature_registry.list_registered()


def list_all_strategies() -> Dict[str, Dict[str, Any]]:
    """Lista todas las estrategias registradas con metadata."""
    return _strategy_registry.list_registered()


def list_all_transformers() -> Dict[str, Dict[str, Any]]:
    """Lista todos los transformadores registrados con metadata."""
    return _transformer_registry.list_registered()
