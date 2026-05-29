from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from src.gui.widgets.data_panel import DataPanel
from src.gui.widgets.pipeline_panel import PipelinePanel

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NotOverfitting - Scientific Trading Suite")
        self.resize(1024, 768)
        
        # Main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # Header
        self.header = QLabel("Módulo de Modelado y Backtest Cuantitativo")
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        self.layout.addWidget(self.header)
        
        # Tabs
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # Initialize panels
        self.init_tabs()

    def init_tabs(self):
        # Data Panel
        self.data_tab = DataPanel()
        self.tabs.addTab(self.data_tab, "Data & MT5")
        
        # Pipeline Panel
        self.pipeline_tab = PipelinePanel()
        self.tabs.addTab(self.pipeline_tab, "Pipeline & PCA")
        
        # Strategy & Backtest Panel
        self.backtest_tab = QWidget()
        self.tabs.addTab(self.backtest_tab, "Backtest & Model")
        
        # Results Panel
        self.results_tab = QWidget()
        self.tabs.addTab(self.results_tab, "Results & Metrics")
