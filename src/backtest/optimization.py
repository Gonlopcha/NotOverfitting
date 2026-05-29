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
from src.pipeline.features.triple_barrier import apply_triple_barrier

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
                # Las características base deben calcularse *antes* del split o en el pipeline
                # Como Triple Barrera necesita ATR, vamos a dejar que el pipeline genere las features en train
                
                # Pipeline: fit en train, transform en test
                pipeline = PipelineOrchestrator.create_default(
                    features=['atr_14', 'rsi_14', 'bollinger_bands', 'ema_distances', 'log_returns', 'rolling_volatility_20', 'momentum_ma_ratio_50', 'relative_volume_20'],
                    use_pca=True, 
                    pca_variance=pca_variance
                )
                
                X_train_proc = pipeline.fit_transform(train_data.copy())
                X_test_proc = pipeline.transform(test_data.copy())
                
                # Target preparation (Triple Barrier) en la data procesada (porque el pipeline calculó ATR)
                # Notar: El pipeline generó 'atr_14'
                train_target = apply_triple_barrier(X_train_proc, pt_factor=2.0, sl_factor=1.0, horizon=24, atr_col='atr_14')
                test_target = apply_triple_barrier(X_test_proc, pt_factor=2.0, sl_factor=1.0, horizon=24, atr_col='atr_14')
                
                # Remover NaNs causados por la Triple Barrera al final de las ventanas
                valid_train = train_target.notna()
                valid_test = test_target.notna()
                
                X_train_proc = X_train_proc[valid_train]
                train_target = train_target[valid_train]
                
                X_test_proc = X_test_proc[valid_test]
                test_target = test_target[valid_test]
                
                # El Target actual es -1, 0, 1. Lo convertimos de vuelta a pd.Series
                train_target = pd.Series(train_target)
                test_target = pd.Series(test_target)
                
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
                signals.index = X_test_proc.index
                
                # Backtest (usamos los precios raw de test_data alineados con valid_test)
                # OJO: X_test_proc tiene el mismo índice que test_data[valid_test]
                backtest_data = test_data.loc[X_test_proc.index]
                
                from src.core.config_manager import ConfigManager
                config = ConfigManager()
                init_cap = config.get("backtest.initial_capital", 10000.0)
                # Fetch drawdown limit from config, defaulting to 0.20
                dd_limit = config.get("backtest.max_drawdown", 0.50) # Increased default to avoid early kills during opt
                
                portfolio = Portfolio(initial_capital=init_cap, max_drawdown_limit=dd_limit, kelly_fraction=0.5)
                engine = BacktestEngine(portfolio)
                engine.run(backtest_data, signals, symbol="SYMBOL_OPT")
                
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
