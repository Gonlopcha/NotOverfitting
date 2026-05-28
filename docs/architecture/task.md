# Bitácora de Desarrollo: NotOverfitting

Esta es nuestra hoja de ruta viva. Iremos marcando las tareas según avancemos:
- `[ ]` Pendiente
- `[/]` En progreso
- `[x]` Completado

---

## Fase 1 — Fundación (Core + Data)

### 1. Estructura y Configuración
- `[x]` Crear estructura de directorios (`src/core`, `src/data`, `config`, etc.)
- `[x]` Crear `config/default.yaml` (configuraciones por defecto)
- `[x]` Crear `config/logging.yaml` (configuración del sistema de logs)
- `[x]` Crear `requirements.txt`

### 2. Capa Core (Infraestructura)
- `[x]` Implementar `src/core/exceptions.py` (Excepciones personalizadas)
- `[x]` Implementar `src/core/logger.py` (Sistema de registro centralizado)
- `[x]` Implementar `src/core/config_manager.py` (Carga y validación de configs)
- `[x]` Implementar `src/core/event_bus.py` (Sistema Pub/Sub para la GUI)
- `[x]` Implementar `src/core/registry.py` (Auto-descubrimiento de features/estrategias)
- `[x]` Implementar `src/core/mt5_connector.py` (Singleton Thread-Safe para MetaTrader5)

### 3. Capa Data (Gestión de Información)
- `[x]` Implementar `src/data/schemas.py` (Validación de datos con Pydantic)
- `[x]` Implementar `src/data/cache_manager.py` (Sistema de caché inteligente)
- `[x]` Implementar `src/data/data_store.py` (Almacenamiento Parquet/SQLite)
- `[x]` Implementar `src/data/data_manager.py` (Orquestador de descargas y validación)

### 4. Pruebas y Validación (Fase 1)
- `[ ]` Tests unitarios de la capa Core
- `[ ]` Tests unitarios de la capa Data

---

## Fase 2 — Pipeline (Próximamente)
- `[ ]` (Las tareas de esta fase se añadirán al terminar la Fase 1)
