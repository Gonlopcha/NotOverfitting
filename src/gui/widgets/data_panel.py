from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QLineEdit, QFormLayout, QGroupBox, QComboBox,
    QDateEdit, QTextEdit
)
from PySide6.QtCore import Qt, QDate, Signal
from src.core.event_bus import subscribe, emit
from src.core.logger import get_logger

logger = get_logger(__name__)

class DataPanel(QWidget):
    sig_mt5_connected = Signal(dict)
    sig_mt5_error = Signal(dict)
    sig_download_completed = Signal(dict)
    sig_download_error = Signal(dict)
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_subscriptions()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Grupo de Conexión MT5
        mt5_group = QGroupBox("Conexión MetaTrader 5")
        mt5_layout = QFormLayout()
        
        self.login_input = QLineEdit()
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.server_input = QLineEdit()
        
        mt5_layout.addRow("Login (Cuenta):", self.login_input)
        mt5_layout.addRow("Contraseña:", self.pass_input)
        mt5_layout.addRow("Servidor:", self.server_input)
        
        self.btn_connect = QPushButton("Conectar a MT5")
        self.btn_connect.clicked.connect(self.on_connect_clicked)
        mt5_layout.addRow(self.btn_connect)
        
        mt5_group.setLayout(mt5_layout)
        layout.addWidget(mt5_group)
        
        # Grupo de Descarga de Datos
        dl_group = QGroupBox("Descarga de Datos Históricos")
        dl_layout = QFormLayout()
        
        self.symbol_input = QLineEdit("EURUSD")
        
        self.tf_combo = QComboBox()
        self.tf_combo.addItems(["M1", "M5", "M15", "H1", "H4", "D1"])
        self.tf_combo.setCurrentText("H1")
        
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addYears(-1))
        
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        
        dl_layout.addRow("Símbolo:", self.symbol_input)
        dl_layout.addRow("Timeframe:", self.tf_combo)
        dl_layout.addRow("Desde:", self.date_from)
        dl_layout.addRow("Hasta:", self.date_to)
        
        self.btn_download = QPushButton("Descargar / Validar OHLCV")
        self.btn_download.clicked.connect(self.on_download_clicked)
        dl_layout.addRow(self.btn_download)
        
        dl_group.setLayout(dl_layout)
        layout.addWidget(dl_group)
        
        # Consola de Eventos
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        layout.addWidget(QLabel("Eventos de Data:"))
        layout.addWidget(self.console)
        
    def init_subscriptions(self):
        subscribe("data.download.completed", self.on_download_completed)
        subscribe("data.download.error", self.on_download_error)
        subscribe("mt5.connected", self.on_mt5_connected)
        subscribe("mt5.error", self.on_mt5_error)
        
        # Conectar Signals al GUI
        self.sig_mt5_connected.connect(self._gui_mt5_connected)
        self.sig_mt5_error.connect(self._gui_mt5_error)
        self.sig_download_completed.connect(self._gui_download_completed)
        self.sig_download_error.connect(self._gui_download_error)

    def append_log(self, text: str):
        self.console.append(text)
        
    def on_connect_clicked(self):
        self.btn_connect.setEnabled(False)
        self.append_log("Intentando conectar a MT5...")
        # Aquí emitimos el evento para que la capa lógica lo atienda
        emit("mt5.connect.request", 
             login=self.login_input.text(),
             password=self.pass_input.text(),
             server=self.server_input.text())
             
    def on_download_clicked(self):
        self.btn_download.setEnabled(False)
        sym = self.symbol_input.text()
        tf = self.tf_combo.currentText()
        self.append_log(f"Iniciando descarga de {sym} en {tf}...")
        
        # Convert QDate to Python Date
        d_from = self.date_from.date().toPython()
        d_to = self.date_to.date().toPython()
        
        # Emitimos al EventBus
        emit("data.download.request", symbol=sym, tf=tf, date_from=d_from, date_to=d_to)
        
    # --- Event Handlers (Vienen del EventBus en hilos secundarios) ---
    def on_mt5_connected(self, **kwargs):
        self.sig_mt5_connected.emit(kwargs)
        
    def on_mt5_error(self, **kwargs):
        self.sig_mt5_error.emit(kwargs)
        
    def on_download_completed(self, **kwargs):
        self.sig_download_completed.emit(kwargs)
        
    def on_download_error(self, **kwargs):
        self.sig_download_error.emit(kwargs)

    # --- Actualizaciones de GUI (En el hilo principal) ---
    def _gui_mt5_connected(self, kwargs):
        self.append_log("✅ Conectado a MetaTrader 5 exitosamente.")
        self.btn_connect.setEnabled(True)
        
    def _gui_mt5_error(self, kwargs):
        self.append_log(f"❌ Error MT5: {kwargs.get('error')}")
        self.btn_connect.setEnabled(True)
        
    def _gui_download_completed(self, kwargs):
        sym = kwargs.get('symbol')
        rows = kwargs.get('rows', 0)
        self.append_log(f"✅ Descarga completada: {sym} ({rows} velas) guardadas en Parquet.")
        self.btn_download.setEnabled(True)
        
    def _gui_download_error(self, kwargs):
        error = kwargs.get('error', 'Unknown')
        self.append_log(f"❌ Error en descarga: {error}")
        self.btn_download.setEnabled(True)
