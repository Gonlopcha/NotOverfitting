from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, 
    QLabel, QFormLayout, QGroupBox, QComboBox,
    QDoubleSpinBox, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from src.core.event_bus import subscribe, emit
from src.core.logger import get_logger

logger = get_logger(__name__)

class BacktestPanel(QWidget):
    sig_progress = Signal(dict)
    sig_completed = Signal(dict)
    sig_error = Signal(dict)
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_subscriptions()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. Selección de Estrategia
        strat_group = QGroupBox("1. Configuración de Estrategia")
        strat_layout = QFormLayout()
        
        self.strategy_combo = QComboBox()
        # En el futuro se llenará desde el Registry
        self.strategy_combo.addItems(["RandomForestClassifier (Default)", "LogisticRegression"])
        strat_layout.addRow("Modelo Predictivo:", self.strategy_combo)
        
        strat_group.setLayout(strat_layout)
        layout.addWidget(strat_group)
        
        # 2. Gestión de Riesgo (Portfolio)
        risk_group = QGroupBox("2. Gestión de Riesgo (Anti-Overfitting)")
        risk_layout = QFormLayout()
        
        self.initial_capital = QDoubleSpinBox()
        self.initial_capital.setRange(100.0, 1000000.0)
        self.initial_capital.setValue(10000.0)
        self.initial_capital.setSingleStep(1000.0)
        
        self.max_drawdown = QDoubleSpinBox()
        self.max_drawdown.setRange(0.01, 1.0)
        self.max_drawdown.setValue(0.20)
        self.max_drawdown.setSingleStep(0.01)
        
        self.kelly_fraction = QDoubleSpinBox()
        self.kelly_fraction.setRange(0.1, 1.0)
        self.kelly_fraction.setValue(0.5)
        self.kelly_fraction.setSingleStep(0.1)
        
        risk_layout.addRow("Capital Inicial ($):", self.initial_capital)
        risk_layout.addRow("Max Drawdown Permitido:", self.max_drawdown)
        risk_layout.addRow("Fracción de Kelly:", self.kelly_fraction)
        
        risk_group.setLayout(risk_layout)
        layout.addWidget(risk_group)
        
        # Botón de ejecución
        self.btn_run_backtest = QPushButton("Ejecutar Simulación (Modelo Nuevo)")
        self.btn_run_backtest.clicked.connect(self.on_run_clicked)
        layout.addWidget(self.btn_run_backtest)
        
        self.btn_run_saved = QPushButton("Cargar Modelo Guardado (.joblib) y Simular")
        self.btn_run_saved.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        self.btn_run_saved.clicked.connect(self.on_run_saved_clicked)
        layout.addWidget(self.btn_run_saved)
        
        # Consola
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        layout.addWidget(QLabel("Eventos de Backtesting:"))
        layout.addWidget(self.console)
        
    def init_subscriptions(self):
        subscribe("backtest.progress", self.on_progress)
        subscribe("backtest.completed", self.on_completed)
        subscribe("backtest.error", self.on_error)
        
        self.sig_progress.connect(self._gui_progress)
        self.sig_completed.connect(self._gui_completed)
        self.sig_error.connect(self._gui_error)

    def append_log(self, text: str):
        self.console.append(text)
        
    def on_run_clicked(self):
        self.btn_run_backtest.setEnabled(False)
        self.btn_run_saved.setEnabled(False)
        self.append_log("Iniciando backtest out-of-sample...")
        
        emit("backtest.run.request",
             strategy=self.strategy_combo.currentText(),
             initial_capital=self.initial_capital.value(),
             max_drawdown=self.max_drawdown.value(),
             kelly_fraction=self.kelly_fraction.value(),
             use_saved_model=False)

    def on_run_saved_clicked(self):
        self.btn_run_backtest.setEnabled(False)
        self.btn_run_saved.setEnabled(False)
        self.append_log("Cargando modelo .joblib y ejecutando backtest...")
        
        emit("backtest.run.request",
             strategy="SavedModel",
             initial_capital=self.initial_capital.value(),
             max_drawdown=self.max_drawdown.value(),
             kelly_fraction=self.kelly_fraction.value(),
             use_saved_model=True)
             
    def on_progress(self, **kwargs):
        self.sig_progress.emit(kwargs)
        
    def on_completed(self, **kwargs):
        self.sig_completed.emit(kwargs)
        
    def on_error(self, **kwargs):
        self.sig_error.emit(kwargs)

    def _gui_progress(self, kwargs):
        progress = kwargs.get('progress', 0)
        self.append_log(f"Progreso: {progress:.1f}%")
        
    def _gui_completed(self, kwargs):
        self.append_log("✅ Backtesting completado. Revisa la pestaña de Resultados.")
        self.btn_run_backtest.setEnabled(True)
        self.btn_run_saved.setEnabled(True)
        
    def _gui_error(self, kwargs):
        error = kwargs.get('error', 'Unknown')
        self.append_log(f"❌ Error en Backtest: {error}")
        self.btn_run_backtest.setEnabled(True)
        self.btn_run_saved.setEnabled(True)
