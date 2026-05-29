from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
    QLabel, QHeaderView, QTextEdit
)
from PySide6.QtCore import Qt
from src.core.event_bus import subscribe

class ResultsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_subscriptions()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel("Resultados Cuantitativos")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Tabla de métricas
        self.metrics_table = QTableWidget(0, 2)
        self.metrics_table.setHorizontalHeaderLabels(["Métrica", "Valor"])
        self.metrics_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.metrics_table.verticalHeader().setVisible(False)
        self.metrics_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.metrics_table)
        
        # Consola de análisis de MDA y advertencias
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        layout.addWidget(QLabel("Análisis Anti-Overfitting (MDA):"))
        layout.addWidget(self.console)
        
    def init_subscriptions(self):
        subscribe("backtest.completed", self.on_backtest_completed)
        
    def on_backtest_completed(self, event):
        metrics = event.data.get('metrics', {})
        mda_log = event.data.get('mda_log', '')
        
        # Actualizar tabla
        self.metrics_table.setRowCount(0)
        for i, (key, value) in enumerate(metrics.items()):
            self.metrics_table.insertRow(i)
            
            # Formateo de valores
            if isinstance(value, float):
                val_str = f"{value:.4f}"
            else:
                val_str = str(value)
                
            item_key = QTableWidgetItem(key)
            item_val = QTableWidgetItem(val_str)
            item_val.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            self.metrics_table.setItem(i, 0, item_key)
            self.metrics_table.setItem(i, 1, item_val)
            
        # Actualizar consola MDA
        if mda_log:
            self.console.setText(mda_log)
        else:
            self.console.setText("No hay datos de MDA disponibles.")
