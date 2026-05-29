import sys
import os
from PySide6.QtWidgets import QApplication
from src.gui.main_window import MainWindow
from src.core.logger import get_logger
from src.core.app_controller import AppController

def main():
    # Inicializa el logger root a través del singleton si no se ha hecho
    logger = get_logger("main")
    logger.info("Iniciando NotOverfitting (Scientific Trading Suite)")
    
    # Iniciar el controlador que enlaza Backend y Frontend
    controller = AppController()

    app = QApplication(sys.argv)
    
    # Cargar tema oscuro
    try:
        with open("src/gui/styles/dark_theme.qss", "r") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        logger.warning(f"No se pudo cargar el tema oscuro: {e}")

    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
