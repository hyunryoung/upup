"""
UI 컴포넌트 모듈
재사용 가능한 UI 컴포넌트들을 정의합니다.
"""

from typing import List, Optional
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from ..data.models import Account, CafeInfo


class AccountTableWidget(QWidget):
    """계정 테이블 위젯"""
    
    def __init__(self):
        super().__init__()
        self._init_ui()
        self.accounts: List[Account] = []
    
    def _init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "PW", "결과"])
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 60)
        self.table.setMaximumHeight(150)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.table)
    
    def set_accounts(self, accounts: List[Account]):
        """계정 목록 설정"""
        self.accounts = accounts
        self.table.setRowCount(len(accounts))
        
        for idx, account in enumerate(accounts):
            self.table.setItem(idx, 0, QTableWidgetItem(account.id))
            self.table.setItem(idx, 1, QTableWidgetItem(account.pw))
            self.table.setItem(idx, 2, QTableWidgetItem(account.status.value))
    
    def update_result(self, account_id: str, result: str):
        """계정 결과 업데이트"""
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0) and self.table.item(row, 0).text() == account_id:
                self.table.setItem(row, 2, QTableWidgetItem(result))
                break
    
    def get_selected_row(self) -> int:
        """선택된 행 번호 반환"""
        return self.table.currentRow()


class CafeTableWidget(QWidget):
    """카페 테이블 위젯"""
    
    def __init__(self):
        super().__init__()
        self._init_ui()
        self.cafes: List[CafeInfo] = []
    
    def _init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Url", "작업 게시판", "목표 게시판", "게시글 조건", "댓글 조건", "방문 조건"
        ])
        self.table.setMaximumHeight(150)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.table)
    
    def set_cafes(self, cafes: List[CafeInfo]):
        """카페 목록 설정"""
        self.cafes = cafes
        self.table.setRowCount(len(cafes))
        
        for idx, cafe in enumerate(cafes):
            self.table.setItem(idx, 0, QTableWidgetItem(cafe.cafe_id))
            self.table.setItem(idx, 1, QTableWidgetItem(cafe.work_board_id))
            self.table.setItem(idx, 2, QTableWidgetItem(cafe.target_board_id))
            self.table.setItem(idx, 3, QTableWidgetItem("확인중"))
            self.table.setItem(idx, 4, QTableWidgetItem("확인중"))
            self.table.setItem(idx, 5, QTableWidgetItem("확인중"))
    
    def update_conditions(self, cafe_id: str, posts: str, comments: str, visits: str):
        """카페 조건 업데이트"""
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0) and self.table.item(row, 0).text() == cafe_id:
                self.table.setItem(row, 3, QTableWidgetItem(posts))
                self.table.setItem(row, 4, QTableWidgetItem(comments))
                self.table.setItem(row, 5, QTableWidgetItem(visits))
                break
    
    def get_selected_row(self) -> int:
        """선택된 행 번호 반환"""
        return self.table.currentRow()


class ProxyWidget(QGroupBox):
    """프록시 관리 위젯"""
    
    def __init__(self):
        super().__init__("프록시 관리 (계정별 IP 변경)")
        self._init_ui()
    
    def _init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 프록시 상태 라벨
        self.status_label = QLabel("📊 프록시 상태: 설정되지 않음")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)
        
        # 프록시 입력 텍스트 영역
        input_layout = QVBoxLayout()
        input_layout.addWidget(QLabel("프록시 서버 목록 (한 줄에 하나씩):"))
        
        self.proxy_text = QTextEdit()
        self.proxy_text.setMaximumHeight(120)
        self.proxy_text.setPlaceholderText(
            "예시:\n192.168.1.100:8080\nproxy.server.com:3128\nuser:pass@proxy.com:8080\n\n# 으로 시작하는 줄은 무시됩니다"
        )
        self.proxy_text.textChanged.connect(self._update_proxy_status)
        input_layout.addWidget(self.proxy_text)
        layout.addLayout(input_layout)
        
        # 프록시 관리 버튼들
        btn_layout = QHBoxLayout()
        
        self.load_proxy_btn = QPushButton("📁 프록시 파일 불러오기")
        self.load_proxy_btn.clicked.connect(self._load_proxy_file)
        btn_layout.addWidget(self.load_proxy_btn)
        
        self.test_proxy_btn = QPushButton("🔍 프록시 테스트")
        self.test_proxy_btn.clicked.connect(self._test_proxies)
        btn_layout.addWidget(self.test_proxy_btn)
        
        self.test_assignment_btn = QPushButton("🎯 할당 테스트")
        self.test_assignment_btn.clicked.connect(self._test_proxy_assignment)
        btn_layout.addWidget(self.test_assignment_btn)
        
        self.clear_proxy_btn = QPushButton("🗑️ 초기화")
        self.clear_proxy_btn.clicked.connect(self._clear_proxies)
        btn_layout.addWidget(self.clear_proxy_btn)
        
        layout.addLayout(btn_layout)
    
    def _update_proxy_status(self):
        """프록시 상태 업데이트"""
        proxy_text = self.proxy_text.toPlainText().strip()
        proxy_lines = [line.strip() for line in proxy_text.split('\n') 
                      if line.strip() and not line.strip().startswith('#')]
        
        if proxy_lines:
            self.status_label.setText(f"📊 프록시 상태: {len(proxy_lines)}개 설정됨")
            self.status_label.setStyleSheet("color: blue;")
        else:
            self.status_label.setText("📊 프록시 상태: 설정되지 않음")
            self.status_label.setStyleSheet("color: gray;")
    
    def get_proxy_list(self) -> List[str]:
        """프록시 목록 반환"""
        proxy_text = self.proxy_text.toPlainText().strip()
        return [line.strip() for line in proxy_text.split('\n') 
                if line.strip() and not line.strip().startswith('#')]
    
    def set_proxy_list(self, proxy_list: List[str]):
        """프록시 목록 설정"""
        self.proxy_text.clear()
        self.proxy_text.setPlainText('\n'.join(proxy_list))
    
    def _load_proxy_file(self):
        """프록시 파일 불러오기"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "프록시 목록 파일 선택",
                "",
                "Text files (*.txt);;All files (*.*)"
            )
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.proxy_text.clear()
                self.proxy_text.setPlainText(content)
                print(f"📋 프록시 파일 불러오기 완료")
        except Exception as e:
            print(f"❌ 프록시 파일 불러오기 실패: {e}")
    
    def _test_proxies(self):
        """프록시 테스트"""
        proxy_list = self.get_proxy_list()
        if not proxy_list:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "경고", "프록시 서버를 입력하세요.")
            return
        
        print(f"🔍 프록시 테스트 시작: {len(proxy_list)}개")
        
        # 실제 테스트는 별도 스레드에서 수행
        from ..ui.dialogs import ProxyTestDialog
        dialog = ProxyTestDialog(proxy_list, self)
        dialog.exec_()
    
    def _test_proxy_assignment(self):
        """프록시 할당 테스트"""
        proxy_list = self.get_proxy_list()
        if not proxy_list:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "경고", "프록시 서버를 입력하세요.")
            return
        
        from ..core.proxy_manager import ProxyManager
        test_proxy_manager = ProxyManager(proxy_list)
        
        print("🎯 프록시 할당 테스트:")
        for i in range(min(10, len(proxy_list) * 2)):
            proxy_info = test_proxy_manager.get_next_proxy()
            if proxy_info:
                proxy_ip = proxy_info['raw_proxy'].split('@')[-1] if '@' in proxy_info['raw_proxy'] else proxy_info['raw_proxy']
                print(f"계정{i+1}: 프록시[{proxy_info['index']}/{proxy_info['total']}] {proxy_ip}")
            else:
                print(f"계정{i+1}: 프록시 없음")
                break
    
    def _clear_proxies(self):
        """프록시 초기화"""
        self.proxy_text.clear()
        self.proxy_text.setPlainText('# 예시 (# 으로 시작하는 줄은 무시됨):\n# 192.168.1.100:8080\n# proxy.server.com:3128\n# user:pass@proxy.com:8080')
        print("🗑️ 프록시 목록이 초기화되었습니다.")


class LogWidget(QGroupBox):
    """로그 표시 위젯"""
    
    def __init__(self):
        super().__init__("작업 로그")
        self._init_ui()
    
    def _init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 작업 정보
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel("- 현재 IP:"))
        self.current_ip_label = QLabel("미확인")
        self.current_ip_label.setStyleSheet("color: red;")
        info_layout.addWidget(self.current_ip_label)
        info_layout.addStretch()
        
        info_layout.addWidget(QLabel("- 작업 상태:"))
        self.status_label = QLabel("대기중")
        self.status_label.setStyleSheet("color: red;")
        info_layout.addWidget(self.status_label)
        
        layout.addLayout(info_layout)
        
        # 로그 텍스트
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
    
    def append_log(self, message: str):
        """로그 메시지 추가"""
        self.log_text.append(message)
        
        # 자동 스크롤
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def update_ip(self, ip_text: str):
        """IP 상태 업데이트"""
        self.current_ip_label.setText(ip_text)
    
    def update_status(self, status_text: str):
        """작업 상태 업데이트"""
        self.status_label.setText(status_text)
    
    def clear_log(self):
        """로그 지우기"""
        self.log_text.clear()


class ProgressDialog(QDialog):
    """진행률 표시 다이얼로그"""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(400, 150)
        self._init_ui()
    
    def _init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 메시지 라벨
        self.message_label = QLabel("작업을 진행하고 있습니다...")
        layout.addWidget(self.message_label)
        
        # 진행률 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 취소 버튼
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)
    
    def update_progress(self, value: int, message: str = ""):
        """진행률 업데이트"""
        self.progress_bar.setValue(value)
        if message:
            self.message_label.setText(message)
        
        # UI 업데이트 강제 실행
        QApplication.processEvents()
    
    def set_indeterminate(self):
        """무한 진행률 모드 설정"""
        self.progress_bar.setRange(0, 0)


class SettingsGroupWidget(QGroupBox):
    """설정 그룹 위젯"""
    
    def __init__(self, title: str):
        super().__init__(title)
        self.form_layout = QFormLayout(self)
        self.widgets = {}
    
    def add_spinbox(self, label: str, key: str, min_val: int = 1, max_val: int = 99999, default_val: int = 1):
        """스핀박스 추가"""
        spinbox = QSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setValue(default_val)
        self.form_layout.addRow(f"{label}:", spinbox)
        self.widgets[key] = spinbox
        return spinbox
    
    def add_checkbox(self, label: str, key: str, default_checked: bool = False):
        """체크박스 추가"""
        checkbox = QCheckBox(label)
        checkbox.setChecked(default_checked)
        self.form_layout.addRow(checkbox)
        self.widgets[key] = checkbox
        return checkbox
    
    def add_combobox(self, label: str, key: str, items: List[str], default_index: int = 0):
        """콤보박스 추가"""
        combobox = QComboBox()
        combobox.addItems(items)
        combobox.setCurrentIndex(default_index)
        self.form_layout.addRow(f"{label}:", combobox)
        self.widgets[key] = combobox
        return combobox
    
    def add_lineedit(self, label: str, key: str, default_text: str = "", placeholder: str = ""):
        """라인 에디트 추가"""
        lineedit = QLineEdit()
        lineedit.setText(default_text)
        if placeholder:
            lineedit.setPlaceholderText(placeholder)
        self.form_layout.addRow(f"{label}:", lineedit)
        self.widgets[key] = lineedit
        return lineedit
    
    def get_value(self, key: str):
        """위젯 값 가져오기"""
        widget = self.widgets.get(key)
        if not widget:
            return None
        
        if isinstance(widget, QSpinBox):
            return widget.value()
        elif isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        elif isinstance(widget, QLineEdit):
            return widget.text()
        
        return None
    
    def set_value(self, key: str, value):
        """위젯 값 설정"""
        widget = self.widgets.get(key)
        if not widget:
            return
        
        if isinstance(widget, QSpinBox):
            widget.setValue(value)
        elif isinstance(widget, QCheckBox):
            widget.setChecked(value)
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(str(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))


class CollapsibleGroupBox(QGroupBox):
    """접을 수 있는 그룹박스"""
    
    def __init__(self, title: str):
        super().__init__(title)
        self.setCheckable(True)
        self.setChecked(True)
        self.toggled.connect(self._on_toggled)
        
        # 내용 위젯
        self.content_widget = QWidget()
        layout = QVBoxLayout(self)
        layout.addWidget(self.content_widget)
    
    def _on_toggled(self, checked: bool):
        """토글 이벤트 처리"""
        self.content_widget.setVisible(checked)
    
    def set_content_layout(self, layout):
        """내용 레이아웃 설정"""
        self.content_widget.setLayout(layout)


class StatusBar(QStatusBar):
    """커스텀 상태바"""
    
    def __init__(self):
        super().__init__()
        self._init_widgets()
    
    def _init_widgets(self):
        """위젯 초기화"""
        # 현재 IP
        self.ip_label = QLabel("현재 IP: 미확인")
        self.addWidget(self.ip_label)
        
        # 구분자
        separator = QLabel("|")
        separator.setStyleSheet("color: gray;")
        self.addWidget(separator)
        
        # 작업 상태
        self.status_label = QLabel("작업 상태: 대기중")
        self.addWidget(self.status_label)
        
        # 진행률 (오른쪽 정렬)
        self.progress_label = QLabel("0/0 완료")
        self.addPermanentWidget(self.progress_label)
    
    def update_ip(self, ip: str):
        """IP 업데이트"""
        self.ip_label.setText(f"현재 IP: {ip}")
    
    def update_status(self, status: str):
        """상태 업데이트"""
        self.status_label.setText(f"작업 상태: {status}")
    
    def update_progress(self, current: int, total: int):
        """진행률 업데이트"""
        self.progress_label.setText(f"{current}/{total} 완료")
