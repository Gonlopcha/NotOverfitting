"""
EventBus: Sistema Pub/Sub desacoplado para comunicación entre módulos.

Permite que diferentes componentes del sistema se comuniquen sin acoplamiento directo.
Los módulos pueden emitir eventos (emit) y otros pueden suscribirse a ellos (subscribe).
"""

import threading
from typing import Callable, Dict, List, Any
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Event:
    """Representa un evento en el sistema."""
    name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "unknown"

    def __repr__(self) -> str:
        return f"Event(name={self.name}, timestamp={self.timestamp.isoformat()}, source={self.source})"


class EventBus:
    """
    Sistema Pub/Sub centralizado para desacoplamiento de módulos.
    
    Thread-safe: usa locks para operaciones concurrentes.
    Historial: mantiene los últimos N eventos para debugging.
    """
    
    def __init__(self, history_size: int = 100):
        """
        Inicializa el EventBus.
        
        Args:
            history_size: Número máximo de eventos a mantener en el historial.
        """
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._history: List[Event] = []
        self._history_size = history_size

    def subscribe(self, event_name: str, callback: Callable, source: str = "unknown") -> None:
        """
        Suscribe un callback a un tipo de evento.
        
        Args:
            event_name: Nombre del evento (ej: 'data.downloaded')
            callback: Función a ejecutar cuando ocurra el evento
            source: Identificador opcional del suscriptor para debugging
            
        Example:
            >>> bus = EventBus()
            >>> def on_data_downloaded(payload):
            ...     print(f"Data ready: {payload}")
            >>> bus.subscribe('data.downloaded', on_data_downloaded)
        """
        with self._lock:
            if callback not in self._subscribers[event_name]:
                self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> bool:
        """
        Desuscribe un callback de un tipo de evento.
        
        Args:
            event_name: Nombre del evento
            callback: Función a remover
            
        Returns:
            True si el callback fue removido, False si no estaba suscrito
        """
        with self._lock:
            if event_name in self._subscribers and callback in self._subscribers[event_name]:
                self._subscribers[event_name].remove(callback)
                return True
            return False

    def emit(self, event_name: str, source: str = "unknown", **payload) -> None:
        """
        Emite un evento a todos los suscriptores.
        
        Args:
            event_name: Nombre del evento a emitir
            source: Identificador del emisor
            **payload: Datos arbitrarios del evento (se pasan como kwargs)
            
        Example:
            >>> bus.emit('data.downloaded', source='DataManager', symbol='EURUSD', rows=1000)
        """
        event = Event(name=event_name, payload=payload, source=source)
        
        with self._lock:
            # Agregar al historial
            self._history.append(event)
            if len(self._history) > self._history_size:
                self._history.pop(0)
            
            # Obtener lista de callbacks (copia para evitar problemas si se modifica durante iteración)
            callbacks = list(self._subscribers.get(event_name, []))
        
        # Ejecutar callbacks fuera del lock para evitar deadlocks
        for callback in callbacks:
            try:
                callback(**payload)
            except Exception as e:
                # Los callbacks no deben romper el flujo del sistema
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error en callback para evento '{event_name}': {e}", exc_info=True)

    def get_history(self, event_name: str = None, limit: int = None) -> List[Event]:
        """
        Obtiene el historial de eventos.
        
        Args:
            event_name: Si se proporciona, filtra por nombre de evento
            limit: Número máximo de eventos a retornar
            
        Returns:
            Lista de eventos (más recientes al final)
        """
        with self._lock:
            if event_name:
                events = [e for e in self._history if e.name == event_name]
            else:
                events = list(self._history)
            
            if limit:
                events = events[-limit:]
            
            return events

    def clear_history(self) -> None:
        """Limpia el historial de eventos."""
        with self._lock:
            self._history.clear()

    def get_subscribers(self, event_name: str = None) -> Dict[str, int]:
        """
        Obtiene información de suscriptores.
        
        Args:
            event_name: Si se proporciona, retorna el count para ese evento
            
        Returns:
            Dict con nombre de evento -> número de suscriptores
        """
        with self._lock:
            if event_name:
                return {event_name: len(self._subscribers.get(event_name, []))}
            return {name: len(callbacks) for name, callbacks in self._subscribers.items()}

    def clear_all_subscribers(self) -> None:
        """Limpia todos los suscriptores (útil para tests)."""
        with self._lock:
            self._subscribers.clear()


# Instancia global del EventBus
_event_bus: EventBus = EventBus()


def get_event_bus() -> EventBus:
    """Obtiene la instancia global del EventBus."""
    return _event_bus


# Para facilitar imports: from src.core.event_bus import emit, subscribe
def subscribe(event_name: str, callback: Callable, source: str = "unknown") -> None:
    """Función de conveniencia para suscribirse al bus global."""
    _event_bus.subscribe(event_name, callback, source)


def emit(event_name: str, source: str = "unknown", **payload) -> None:
    """Función de conveniencia para emitir al bus global."""
    _event_bus.emit(event_name, source, **payload)
