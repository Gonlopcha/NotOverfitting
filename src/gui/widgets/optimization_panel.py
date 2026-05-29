from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QHBoxLayout, 
    QLabel, QSpinBox, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal
from src.core.event_bus import subscribe, emit
from src.core.logger import get_logger

logger = get_logger(__name__)

class OptimizationPanel(QWidget):
    sig_started = Signal(dict)
    sig_trial_completed = Signal(dict)
    sig_finished = Signal(dict)
    sig_error = Signal(dict)

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_subscriptions()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Configuraciones
        config_group = QGroupBox("Configuración de Optimización (Optuna)")
        config_layout = QFormLayout()

        self.spin_trials = QSpinBox()
        self.spin_trials.setRange(5, 500)
        self.spin_trials.setValue(20)
        
        self.spin_splits = QSpinBox()
        self.spin_splits.setRange(2, 10)
        self.spin_splits.setValue(3)

        config_layout.addRow("Número de Trials (Iteraciones):", self.spin_trials)
        config_layout.addRow("Número de Folds (Walk-Forward):", self.spin_splits)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Botón
        btn_layout = QHBoxLayout()
        self.btn_run_opt = QPushButton("🚀 Ejecutar Optimización Bayesiana")
        self.btn_run_opt.clicked.connect(self.run_optimization)
        btn_layout.addWidget(self.btn_run_opt)
        layout.addLayout(btn_layout)

        # Consola
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(150)
        layout.addWidget(QLabel("Progreso en Vivo:"))
        layout.addWidget(self.console)

        # Tabla de mejores trials
        layout.addWidget(QLabel("Registro de Trials:"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Trial", "Sharpe Promedio", "Parámetros", "Estado"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.table)

    def init_subscriptions(self):
        subscribe("optimization.started", self.on_started)
        subscribe("optimization.trial.completed", self.on_trial_completed)
        subscribe("optimization.finished", self.on_finished)
        subscribe("optimization.error", self.on_error)
        
        self.sig_started.connect(self._gui_started)
        self.sig_trial_completed.connect(self._gui_trial_completed)
        self.sig_finished.connect(self._gui_finished)
        self.sig_error.connect(self._gui_error)

    def append_log(self, text: str):
        self.console.append(text)

    def run_optimization(self):
        self.btn_run_opt.setEnabled(False)
        self.append_log("Iniciando optimización (Optuna)...")
        self.table.setRowCount(0)
        
        emit("optimization.run.request", 
             n_trials=self.spin_trials.value(), 
             n_splits=self.spin_splits.value())

    def on_started(self, **kwargs):
        self.sig_started.emit(kwargs)

    def on_trial_completed(self, **kwargs):
        self.sig_trial_completed.emit(kwargs)

    def on_finished(self, **kwargs):
        self.sig_finished.emit(kwargs)

    def on_error(self, **kwargs):
        self.sig_error.emit(kwargs)

    def _gui_started(self, kwargs):
        total = kwargs.get('total_trials', 0)
        self.append_log(f"Optuna inicializado. Se ejecutarán {total} iteraciones.")

    def _gui_trial_completed(self, kwargs):
        trial_num = kwargs.get('trial_num', 0)
        params = kwargs.get('params', {})
        score = kwargs.get('score', 0.0)
        
        self.append_log(f"Trial {trial_num} completado | Sharpe: {score:.4f}")
        
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(trial_num)))
        self.table.setItem(row, 1, QTableWidgetItem(f"{score:.4f}"))
        
        # Formatear params
        param_str = ", ".join([f"{k}: {v:.2f}" if isinstance(v, float) else f"{k}: {v}" for k, v in params.items()])
        self.table.setItem(row, 2, QTableWidgetItem(param_str))
        self.table.setItem(row, 3, QTableWidgetItem("Completado"))
        
    def _gui_finished(self, kwargs):
        best_value = kwargs.get('best_value', 0.0)
        self.append_log(f"✅ Optimización Finalizada. Mejor Sharpe: {best_value:.4f}")
        self.btn_run_opt.setEnabled(True)

    def _gui_error(self, kwargs):
        err = kwargs.get('error', 'Unknown')
        self.append_log(f"❌ Error en Optimización: {err}")
        self.btn_run_opt.setEnabled(True)
