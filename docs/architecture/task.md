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
- `[x]` Tests unitarios de la capa Core
- `[x]` Tests unitarios de la capa Data

---

## Fase 2 — Pipeline (Capa de Ingeniería de Características)
- `[x]` Implementar `src/pipeline/base.py` (Clase base `PipelineStep`)
- `[x]` Implementar `src/pipeline/cleaner.py` (Limpieza e imputación)
- `[x]` Implementar `src/pipeline/feature_generator.py` (Motor de generación usando Registry)
- `[x]` Implementar modulo `src/pipeline/features/` (Técnicas, Estadísticas, etc.)
- `[x]` Implementar `src/pipeline/pca_transformer.py` (Transformador PCA)
- `[x]` Implementar `src/pipeline/orchestrator.py` (Coordinador del pipeline)
- `[x]` Pruebas de reproducibilidad del pipeline

---

## Fase 3 — Estrategia + Backtest (Núcleo Anti-Overfitting)
- `[x]` Implementar `src/strategy/base.py` (Clase base `StrategyBase`)
- `[x]` Implementar `src/strategy/model_manager.py` (Manejo de modelos ML y cálculo MDA)
- `[x]` Implementar `src/strategy/signal_generator.py` (Traducción de predicción a señal)
- `[x]` Implementar `src/backtest/engine.py` (Motor event-driven)
- `[x]` Implementar `src/backtest/portfolio.py` (Gestión de capital y riesgo)
- `[x]` Implementar `src/backtest/metrics.py` (Métricas robustas, Sharpe, MaxDD)
- `[x]` Pruebas unitarias de la fase de modelado y backtesting

---

## Fase 4 — GUI (Frontend con PySide6)
- `[x]` Implementar `src/gui/main_window.py` (Ventana principal con tabs)
- `[x]` Implementar `src/gui/widgets/data_panel.py` (Conexión MT5 y descargas)
- `[x]` Implementar `src/gui/widgets/pipeline_panel.py` (Configuración de variables y PCA)
- `[x]` Implementar `src/gui/widgets/backtest_panel.py` (Ejecución de simulación)
- `[x]` Implementar `src/gui/widgets/results_panel.py` (Métricas y gráficos básicos)
- `[x]` Implementar `src/gui/styles/dark_theme.qss` (Tema científico oscuro)
- `[x]` Integrar `main.py` para levantar la app
- `[x]` Conectar todos los paneles a la capa lógica usando el `EventBus`

## Fase 5 — Optimización + Polish
- `[x]` Implementar `src/backtest/optimization.py` (Integración con Optuna)
- `[x]` Implementar `src/backtest/walk_forward.py` (Validación de ventanas deslizantes)
- `[x]` Crear `src/gui/widgets/optimization_panel.py` (Panel visual de progreso)
- `[x]` Integrar optimización en `src/core/app_controller.py`
- `[x]` Añadir pestaña de Optimización a `main_window.py`
- `[x]` Guardar/Serializar el modelo optimizado (pipeline + hiperparámetros) en `.joblib`

## Fase 5.5 — Data Science & Advanced ML
- `[x]` Implementar `src/pipeline/features/advanced_technical.py` (Nuevos features: ATR, RSI, MACD, etc)
- `[x]` Implementar `src/pipeline/features/triple_barrier.py` (Etiquetado predictivo)
- `[x]` Integrar Triple Barrera como "Target" en `app_controller.py`
- `[x]` Integrar Triple Barrera en `optimization.py`

## Recomendaciones de Arquitectura (Deuda Técnica)
*Tareas identificadas para alinear el código con la arquitectura oficial:*
- `[x]` Crear archivos `__init__.py` en `src/core/` y `src/data/`
- `[x]` Refactorizar `logger.py` a una clase Singleton capaz de emitir eventos `log.message` al `EventBus`
- `[x]` Completar `mt5_connector.py` (añadir `get_symbols`, `send_order`, `get_positions`)
- `[x]` Actualizar `config_manager.py` (merge de YAML, setters, tipado y thread-safety)
