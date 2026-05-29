import optuna
import numpy as np
import pandas as pd
from typing import Dict, Any

from src.core.logger import get_logger
from src.core.event_bus import emit
from src.pipeline.orchestrator import PipelineOrchestrator
from src.strategy.model_manager import ModelManager
from src.strategy.signal_generator import SignalGenerator
from src.backtest.walk_forward import WalkForwardValidator
from src.backtest.portfolio import Portfolio
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import calculate_all_metrics

logger = get_logger(__name__)

class OptunaOptimizer:
    """
    Optimizador de hiperparámetros usando Optuna y Walk-Forward Validation.
    Busca maximizar el Ratio de Sharpe (o PnL) sin sobreajustar el modelo.
    """
    
    def __init__(self, data: pd.DataFrame, n_trials: int = 20, n_splits: int = 3):
        self.data = data
        self.n_trials = n_trials
        self.n_splits = n_splits
        self.study = None
        
    def _objective(self, trial: optuna.Trial) -> float:
        # 1. Definir el espacio de búsqueda (Hiperparámetros)
        pca_variance = trial.suggest_float("pca_variance", 0.80, 0.99)
        rf_max_depth = trial.suggest_int("rf_max_depth", 3, 10)
        rf_n_estimators = trial.suggest_int("rf_n_estimators", 50, 200)
        buy_threshold = trial.suggest_float("buy_threshold", 0.51, 0.60)
        sell_threshold = trial.suggest_float("sell_threshold", 0.40, 0.49)
        
        # 2. Inicializar Walk-Forward Validator
        wf = WalkForwardValidator(n_splits=self.n_splits, train_size=0.7)
        folds = wf.split(self.data)
        
        sharpe_ratios = []
        
        # 3. Evaluar en cada ventana de tiempo
        for i, (train_data, test_data) in enumerate(folds):
            try:
                # Target preparation (next candle up/down)
                train_target = np.where(train_data['close'].shift(-1) > train_data['close'], 1, 0)
                test_target = np.where(test_data['close'].shift(-1) > test_data['close'], 1, 0)
                
                # Para evitar NaNs en el último registro por el shift
                train_data = train_data.iloc[:-1].copy()
                train_target = train_target[:-1]
                test_data = test_data.iloc[:-1].copy()
                test_target = test_target[:-1]
                
                # Pipeline: fit en train, transform en test
                pipeline = PipelineOrchestrator.create_default(use_pca=True, pca_variance=pca_variance)
                
                # Pipeline espera un DF. Guardamos columnas originales para el backtest.
                X_train_proc = pipeline.fit_transform(train_data.copy())
                X_test_proc = pipeline.transform(test_data.copy())
                
                # Filtrar solo las features (pca_*)
                drop_cols = ['open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume', 'time']
                feature_cols = [c for c in X_train_proc.columns if c not in drop_cols]
                
                if not feature_cols:
                    return -999.0 # Castigo por mala configuración
                
                # Entrenamiento
                model_manager = ModelManager(n_estimators=rf_n_estimators, max_depth=rf_max_depth)
                model_manager.train(X_train_proc[feature_cols], pd.Series(train_target))
                
                # Predicción
                probs = model_manager.predict_proba(X_test_proc[feature_cols])
                signal_gen = SignalGenerator(buy_threshold=buy_threshold, enable_short=True, sell_threshold=sell_threshold)
                signals = signal_gen.generate(probs)
                signals.index = test_data.index
                
                # Backtest (usamos los precios raw de test_data)
                portfolio = Portfolio(initial_capital=10000, max_drawdown=0.20, kelly_fraction=0.5)
                engine = BacktestEngine(portfolio)
                engine.run(test_data, signals, symbol="SYMBOL_OPT")
                
                trades = portfolio.get_summary()
                metrics = calculate_all_metrics(pd.Series(portfolio.equity_curve), trades, num_trials=1)
                
                sharpe = float(metrics.get("Sharpe Ratio", 0.0))
                sharpe_ratios.append(sharpe)
                
            except Exception as e:
                logger.warning(f"Trial falló en el fold {i}: {e}")
                return -999.0
                
        # 4. El objetivo es maximizar el promedio del Sharpe Ratio de todos los folds
        avg_sharpe = np.mean(sharpe_ratios)
        
        # Emitir progreso a la GUI
        emit("optimization.trial.completed", trial_num=trial.number, params=trial.params, score=avg_sharpe)
        
        return avg_sharpe
        
    def optimize(self) -> Dict[str, Any]:
        """
        Ejecuta la optimización y retorna los mejores parámetros.
        """
        self.study = optuna.create_study(direction="maximize", study_name="WalkForward_Optimization")
        
        emit("optimization.started", total_trials=self.n_trials)
        self.study.optimize(self._objective, n_trials=self.n_trials)
        emit("optimization.finished", best_params=self.study.best_params, best_value=self.study.best_value)
        
        logger.info(f"Mejor Sharpe: {self.study.best_value}")
        logger.info(f"Mejores Parámetros: {self.study.best_params}")
        
        return self.study.best_params
