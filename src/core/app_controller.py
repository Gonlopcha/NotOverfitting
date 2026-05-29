"""
Controlador Principal de la Aplicación.
Conecta los eventos de la GUI (Frontend) con la lógica de negocio (Backend).
"""
import threading
import numpy as np
import pandas as pd
from src.core.event_bus import subscribe, emit
from src.core.logger import get_logger
from src.core.mt5_connector import MT5Connector
from src.data.data_manager import DataManager
from src.pipeline.orchestrator import PipelineOrchestrator
from src.strategy.model_manager import ModelManager
from src.strategy.signal_generator import SignalGenerator
from src.backtest.portfolio import Portfolio
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import calculate_all_metrics

logger = get_logger(__name__)

class AppController:
    def __init__(self):
        self.mt5 = MT5Connector()
        self.data_manager = DataManager()
        self.pipeline: PipelineOrchestrator = None
        self.current_data: pd.DataFrame = None
        self.processed_data: pd.DataFrame = None
        
        self.init_subscriptions()
        
    def init_subscriptions(self):
        # GUI -> Backend
        subscribe("mt5.connect.request", self.handle_mt5_connect)
        subscribe("data.download.request", self.handle_data_download)
        subscribe("pipeline.run.request", self.handle_pipeline_run)
        subscribe("backtest.run.request", self.handle_backtest_run)
        
    def handle_mt5_connect(self, event):
        login = event.data.get("login")
        password = event.data.get("password")
        server = event.data.get("server")
        
        def _connect():
            try:
                # Si los campos están vacíos, MT5Connector intentará cargar del yaml.
                login_int = int(login) if login else 0
                if self.mt5.connect(login=login_int, password=password, server=server):
                    emit("mt5.connected")
                else:
                    emit("mt5.error", error="Credenciales inválidas o servidor inalcanzable.")
            except Exception as e:
                emit("mt5.error", error=str(e))
                
        threading.Thread(target=_connect, daemon=True).start()
        
    def handle_data_download(self, event):
        symbol = event.data.get("symbol")
        tf = event.data.get("tf")
        d_from = event.data.get("date_from")
        d_to = event.data.get("date_to")
        
        def _download():
            try:
                self.current_data = self.data_manager.download(symbol, tf, d_from, d_to)
                if self.current_data is None or self.current_data.empty:
                    emit("data.download.error", error="No se obtuvieron datos.")
                else:
                    emit("data.download.completed", symbol=symbol, rows=len(self.current_data))
            except Exception as e:
                emit("data.download.error", error=str(e))
                
        threading.Thread(target=_download, daemon=True).start()
        
    def handle_pipeline_run(self, event):
        if self.current_data is None:
            emit("pipeline.run.error", error="No hay datos cargados. Descarga datos primero.")
            return
            
        outlier_std = event.data.get("outlier_std", 3.0)
        features = event.data.get("features", [])
        use_pca = event.data.get("use_pca", True)
        pca_variance = event.data.get("pca_variance", 0.95)
        
        def _run():
            try:
                # Instanciamos temporalmente para no complicar el constructor del Orchestrator
                self.pipeline = PipelineOrchestrator.create_default(use_pca=use_pca, pca_variance=pca_variance)
                
                # Ejecutamos el fit_transform
                self.processed_data = self.pipeline.fit_transform(self.current_data.copy())
                emit("pipeline.run.completed")
            except Exception as e:
                logger.exception("Error en pipeline")
                emit("pipeline.run.error", error=str(e))
                
        threading.Thread(target=_run, daemon=True).start()
        
    def handle_backtest_run(self, event):
        if self.processed_data is None:
            emit("backtest.error", error="Debes ejecutar el Pipeline antes de hacer backtesting.")
            return
            
        initial_capital = event.data.get("initial_capital", 10000.0)
        max_drawdown = event.data.get("max_drawdown", 0.20)
        kelly_fraction = event.data.get("kelly_fraction", 0.5)
        
        def _run():
            try:
                # 1. Separar features y label
                # Objetivo simple: predecir si el cierre de mañana será mayor al de hoy
                df = self.processed_data.copy()
                df['target'] = np.where(df['close'].shift(-1) > df['close'], 1, 0)
                df.dropna(inplace=True)
                
                # Split 80% train, 20% test cronológico
                split_idx = int(len(df) * 0.8)
                train_df = df.iloc[:split_idx]
                test_df = df.iloc[split_idx:]
                
                # Excluir columnas base para no hacer trampa, quedarnos con 'pca_' o features calculadas
                drop_cols = ['target', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']
                feature_cols = [c for c in df.columns if c not in drop_cols and not c.startswith('time')]
                
                if not feature_cols:
                    emit("backtest.error", error="No se encontraron features (ej. pca_0) tras el pipeline.")
                    return
                
                X_train = train_df[feature_cols]
                y_train = train_df['target']
                X_test = test_df[feature_cols]
                y_test = test_df['target']
                
                # 2. Entrenar Modelo y calcular MDA
                model_manager = ModelManager()
                model_manager.train(X_train, y_train)
                
                mda_df = model_manager.calculate_mda(X_test, y_test)
                mda_log = mda_df.to_string()
                
                # 3. Generar señales predictivas
                probs = model_manager.predict_proba(X_test)
                # Umbrales asimétricos: > 0.55 compra, < 0.45 venta (asumiendo binario)
                signal_gen = SignalGenerator(buy_threshold=0.55, enable_short=True, sell_threshold=0.45)
                signals = signal_gen.generate(probs)
                
                # Asegurar alineación de índices
                # Las señales devueltas por SignalGenerator pierden el índice, se lo reasignamos
                signals.index = X_test.index
                
                # 4. Ejecutar Backtest Event-Driven
                portfolio = Portfolio(initial_capital, max_drawdown, kelly_fraction)
                engine = BacktestEngine(portfolio)
                engine.run(test_df, signals, symbol="SYMBOL_LIVE")
                
                # 5. Calcular Métricas
                trades = portfolio.get_summary()
                metrics = calculate_all_metrics(pd.Series(portfolio.equity_curve), trades, num_trials=1)
                
                emit("backtest.completed", metrics=metrics, mda_log=mda_log)
                
            except Exception as e:
                logger.exception("Error en backtest")
                emit("backtest.error", error=str(e))
                
        threading.Thread(target=_run, daemon=True).start()
