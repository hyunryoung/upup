from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit,
                             QPushButton, QMessageBox, QApplication)
from PyQt5.QtCore import Qt
from ..core.license_manager import LicenseManager

class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.license_manager = LicenseManager()
        self.setup_ui()
        
    def setup_ui(self):
        """UI 구성"""
        self.setWindowTitle("라이선스 등록")
        self.setFixedSize(500, 250)
        
        layout = QVBoxLayout()
        
        # 하드웨어 ID 표시
        hw_id = self.license_manager.get_hardware_id()
        layout.addWidget(QLabel("하드웨어 ID:"))
        hw_id_label = QLabel(hw_id)
        hw_id_label.setStyleSheet("background-color: #f0f0f0; padding: 10px;")
        hw_id_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(hw_id_label)
        
        # 안내 메시지
        info_label = QLabel("위 하드웨어 ID를 관리자에게 전달하여 라이선스 키를 발급받으세요.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # 라이선스 키 입력
        layout.addWidget(QLabel("라이선스 키:"))
        self.license_input = QLineEdit()
        layout.addWidget(self.license_input)
        
        # 등록 버튼
        register_button = QPushButton("등록")
        register_button.clicked.connect(self.register_license)
        layout.addWidget(register_button)
        
        self.setLayout(layout)
        
    def register_license(self):
        """라이선스 등록"""
        license_key = self.license_input.text().strip()
        if not license_key:
            QMessageBox.warning(self, "경고", "라이선스 키를 입력해주세요.")
            return
            
        success, message = self.license_manager.verify_license(license_key)
        if success:
            QMessageBox.information(self, "성공", message)
            self.accept()
        else:
            QMessageBox.critical(self, "오류", message)
    
    @staticmethod
    def check_license():
        """라이선스 상태 확인"""
        license_manager = LicenseManager()
        success, message = license_manager.check_license()
        
        if not success:
            dialog = LicenseDialog()
            if dialog.exec_() != QDialog.Accepted:
                return False
        return True
