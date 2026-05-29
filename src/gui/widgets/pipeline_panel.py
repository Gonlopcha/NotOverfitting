from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QLineEdit, QFormLayout, QGroupBox, QCheckBox,
    QDoubleSpinBox, QListWidget, QListWidgetItem, QTextEdit
)
from PySide6.QtCore import Qt
from src.core.event_bus import subscribe, emit
from src.core.registry import get_feature_registry
from src.core.logger import get_logger

logger = get_logger(__name__)

class PipelinePanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_subscriptions()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. Configuración de Limpieza (DataCleaner)
        cleaner_group = QGroupBox("1. Limpieza de Datos (DataCleaner)")
        cleaner_layout = QFormLayout()
        
        self.outlier_std = QDoubleSpinBox()
        self.outlier_std.setRange(1.0, 10.0)
        self.outlier_std.setValue(3.0)
        self.outlier_std.setSingleStep(0.5)
        cleaner_layout.addRow("Límite Outlier (Std Dev):", self.outlier_std)
        
        cleaner_group.setLayout(cleaner_layout)
        layout.addWidget(cleaner_group)
        
        # 2. Selección de Features
        features_group = QGroupBox("2. Ingeniería de Características")
        features_layout = QVBoxLayout()
        
        self.features_list = QListWidget()
        self.populate_features()
        features_layout.addWidget(self.features_list)
        
        features_group.setLayout(features_layout)
        layout.addWidget(features_group)
        
        # 3. Configuración PCA
        pca_group = QGroupBox("3. Reducción Dimensional (PCA)")
        pca_layout = QFormLayout()
        
        self.enable_pca = QCheckBox("Habilitar PCA")
        self.enable_pca.setChecked(True)
        
        self.pca_variance = QDoubleSpinBox()
        self.pca_variance.setRange(0.5, 0.99)
        self.pca_variance.setValue(0.95)
        self.pca_variance.setSingleStep(0.01)
        
        pca_layout.addRow("", self.enable_pca)
        pca_layout.addRow("Varianza Retenida:", self.pca_variance)
        
        pca_group.setLayout(pca_layout)
        layout.addWidget(pca_group)
        
        # Botón de ejecución
        self.btn_run_pipeline = QPushButton("Ejecutar Pipeline")
        self.btn_run_pipeline.clicked.connect(self.on_run_clicked)
        layout.addWidget(self.btn_run_pipeline)
        
        # Consola
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        layout.addWidget(QLabel("Eventos del Pipeline:"))
        layout.addWidget(self.console)
        
    def populate_features(self):
        """Carga las features disponibles desde el registry."""
        registry = get_feature_registry()
        # Intentamos importar para asegurar que se registren
        try:
            import src.pipeline.features.technical
        except ImportError:
            pass
            
        features = registry.get_all()
        for name in features.keys():
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.features_list.addItem(item)
            
    def init_subscriptions(self):
        subscribe("pipeline.run.completed", self.on_pipeline_completed)
        subscribe("pipeline.run.error", self.on_pipeline_error)

    def append_log(self, text: str):
        self.console.append(text)
        
    def on_run_clicked(self):
        self.btn_run_pipeline.setEnabled(False)
        self.append_log("Iniciando procesamiento del Pipeline...")
        
        selected_features = []
        for i in range(self.features_list.count()):
            item = self.features_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_features.append(item.text())
                
        # Emitir evento
        emit("pipeline.run.request",
             outlier_std=self.outlier_std.value(),
             features=selected_features,
             use_pca=self.enable_pca.isChecked(),
             pca_variance=self.pca_variance.value())
             
    def on_pipeline_completed(self, **kwargs):
        self.append_log("✅ Pipeline ejecutado exitosamente. Datos transformados.")
        self.btn_run_pipeline.setEnabled(True)
        
    def on_pipeline_error(self, **kwargs):
        error = kwargs.get('error', 'Unknown')
        self.append_log(f"❌ Error en Pipeline: {error}")
        self.btn_run_pipeline.setEnabled(True)
