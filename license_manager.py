#!/usr/bin/env python3
"""
라이선스 관리자 프로그램
PC 하드웨어 ID를 등록/관리하는 관리자용 도구입니다.
"""

import sys
import os
import json
from datetime import datetime
from typing import Optional, Dict, List
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QDialogButtonBox, QFormLayout, QComboBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon

from src.security.hardware_auth import HardwareAuthenticator
from src.security.license_db import LicenseDB


class AddPCDialog(QDialog):
    """PC 추가 다이얼로그"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🖥️ PC 추가")
        self.setFixedWidth(500)
        self._init_ui()
    
    def _init_ui(self):
        """UI 초기화"""
        layout = QFormLayout()
        
        # 하드웨어 ID 입력
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("예: A1B2C3D4E5F67890")
        layout.addRow("하드웨어 ID:", self.id_input)
        
        # 사용자 이름 입력
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("예: 홍길동")
        layout.addRow("사용자 이름:", self.name_input)
        
        # 메모 입력
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("추가 정보를 입력하세요")
        self.notes_input.setFixedHeight(100)
        layout.addRow("메모:", self.notes_input)
        
        # 버튼
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)
        
        self.setLayout(layout)
    
    def get_values(self) -> tuple:
        """입력값 반환"""
        return (
            self.id_input.text().strip(),
            self.name_input.text().strip(),
            self.notes_input.toPlainText().strip()
        )


class LicenseManager(QMainWindow):
    """라이선스 관리자 메인 윈도우"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔐 라이선스 관리자")
        self.setMinimumSize(800, 600)
        
        # 라이선스 DB 초기화
        self.license_db = LicenseDB()
        self.hardware_auth = HardwareAuthenticator()
        
        self._init_ui()
        self._load_pcs()
    
    def _init_ui(self):
        """UI 초기화"""
        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # 제목
        title_label = QLabel("🔐 라이선스 관리자")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 현재 PC 정보
        current_pc_layout = QHBoxLayout()
        
        current_id_label = QLabel(f"현재 PC의 하드웨어 ID: {self.hardware_auth.get_hardware_id()}")
        current_id_label.setStyleSheet("color: #666;")
        current_pc_layout.addWidget(current_id_label)
        
        copy_button = QPushButton("📋 복사")
        copy_button.clicked.connect(lambda: self._copy_to_clipboard(self.hardware_auth.get_hardware_id()))
        current_pc_layout.addWidget(copy_button)
        
        layout.addLayout(current_pc_layout)
        
        # 버튼 그룹
        button_layout = QHBoxLayout()
        
        add_button = QPushButton("➕ PC 추가")
        add_button.clicked.connect(self._add_pc)
        button_layout.addWidget(add_button)
        
        remove_button = QPushButton("➖ PC 제거")
        remove_button.clicked.connect(self._remove_pc)
        button_layout.addWidget(remove_button)
        
        refresh_button = QPushButton("🔄 새로고침")
        refresh_button.clicked.connect(self._load_pcs)
        button_layout.addWidget(refresh_button)
        
        layout.addLayout(button_layout)
        
        # PC 목록 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "하드웨어 ID", "사용자", "상태", "등록일", "메모"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.table)
        
        # 상태바
        self.statusBar().showMessage("준비")
    
    def _load_pcs(self):
        """등록된 PC 목록 로드"""
        try:
            pcs = self.license_db.get_all_pcs()
            
            self.table.setRowCount(len(pcs))
            for i, pc in enumerate(pcs):
                self.table.setItem(i, 0, QTableWidgetItem(pc['hardware_id']))
                self.table.setItem(i, 1, QTableWidgetItem(pc.get('user_name', '')))
                self.table.setItem(i, 2, QTableWidgetItem(pc.get('status', 'active')))
                
                added_date = datetime.fromisoformat(pc['added_date']).strftime('%Y-%m-%d %H:%M')
                self.table.setItem(i, 3, QTableWidgetItem(added_date))
                
                self.table.setItem(i, 4, QTableWidgetItem(pc.get('notes', '')))
            
            self.statusBar().showMessage(f"총 {len(pcs)}개의 PC가 등록되어 있습니다.")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"PC 목록 로드 실패:\n{str(e)}")
    
    def _add_pc(self):
        """새 PC 추가"""
        dialog = AddPCDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            hardware_id, user_name, notes = dialog.get_values()
            
            if not hardware_id:
                QMessageBox.warning(self, "입력 오류", "하드웨어 ID를 입력하세요.")
                return
            
            if not self.hardware_auth.validate_hardware_id(hardware_id):
                QMessageBox.warning(self, "입력 오류", "올바른 하드웨어 ID를 입력하세요. (16자리 영문/숫자)")
                return
            
            try:
                if self.license_db.add_pc(hardware_id, user_name, notes):
                    self.statusBar().showMessage(f"PC 추가됨: {hardware_id}")
                    self._load_pcs()
                else:
                    QMessageBox.warning(self, "추가 실패", "이미 등록된 PC입니다.")
            
            except Exception as e:
                QMessageBox.critical(self, "오류", f"PC 추가 실패:\n{str(e)}")
    
    def _remove_pc(self):
        """선택된 PC 제거"""
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "선택 오류", "제거할 PC를 선택하세요.")
            return
        
        hardware_id = self.table.item(current_row, 0).text()
        user_name = self.table.item(current_row, 1).text()
        
        reply = QMessageBox.question(
            self,
            "PC 제거 확인",
            f"다음 PC를 제거하시겠습니까?\n\n"
            f"하드웨어 ID: {hardware_id}\n"
            f"사용자: {user_name}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if self.license_db.remove_pc(hardware_id):
                    self.statusBar().showMessage(f"PC 제거됨: {hardware_id}")
                    self._load_pcs()
                else:
                    QMessageBox.warning(self, "제거 실패", "PC를 제거할 수 없습니다.")
            
            except Exception as e:
                QMessageBox.critical(self, "오류", f"PC 제거 실패:\n{str(e)}")
    
    def _copy_to_clipboard(self, text: str):
        """클립보드에 텍스트 복사"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        
        self.statusBar().showMessage("클립보드에 복사됨", 2000)


def main():
    """메인 함수"""
    # PyQt 앱 생성
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 폰트 설정
    font = QFont()
    font.setFamily('Malgun Gothic')
    font.setPointSize(10)
    app.setFont(font)
    
    try:
        # 메인 윈도우 생성 및 표시
        window = LicenseManager()
        window.show()
        
        return app.exec_()
        
    except Exception as e:
        QMessageBox.critical(None, "시작 오류", f"프로그램을 시작할 수 없습니다:\n{str(e)}")
        return 1


if __name__ == '__main__':
    # 고해상도 디스플레이 지원
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    sys.exit(main())
