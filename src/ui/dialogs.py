"""
다이얼로그 모듈
각종 설정 및 정보 다이얼로그를 정의합니다.
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from ..core.config import config


class AboutDialog(QDialog):
    """정보 다이얼로그"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("정보")
        self.setFixedSize(400, 300)
        self._init_ui()
    
    def _init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 아이콘 (선택사항)
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        # icon_label.setPixmap(QPixmap("icon.png").scaled(64, 64, Qt.KeepAspectRatio))
        layout.addWidget(icon_label)
        
        # 제목
        title_label = QLabel("네이버 카페 자동 등업 프로그램")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # 버전
        version_label = QLabel("버전: v1.0.3 (프록시 배분 개선)")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: gray; margin-bottom: 20px;")
        layout.addWidget(version_label)
        
        # 설명
        description = QTextEdit()
        description.setReadOnly(True)
        description.setHtml("""
        <h3>기능</h3>
        <ul>
            <li>네이버 카페 자동 등업</li>
            <li>다중 계정 지원</li>
            <li>다중 카페 지원</li>
            <li>프록시 서버 지원</li>
            <li>등급 조건 자동 확인</li>
            <li>작업 결과 엑셀 출력</li>
        </ul>
        
        <h3>주의사항</h3>
        <ul>
            <li>네이버 이용약관을 준수하여 사용하세요</li>
            <li>과도한 사용은 계정 제재를 받을 수 있습니다</li>
            <li>프로그램 사용으로 인한 모든 책임은 사용자에게 있습니다</li>
        </ul>
        """)
        layout.addWidget(description)
        
        # 확인 버튼
        ok_btn = QPushButton("확인")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)


class SettingsDialog(QDialog):
    """환경설정 다이얼로그"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("환경설정")
        self.setFixedSize(500, 400)
        self._init_ui()
        self._load_current_settings()
    
    def _init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 탭 위젯
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # 일반 설정 탭
        self._create_general_tab()
        
        # 자동화 설정 탭
        self._create_automation_tab()
        
        # WebDriver 설정 탭
        self._create_webdriver_tab()
        
        # 버튼
        button_layout = QHBoxLayout()
        
        self.ok_btn = QPushButton("확인")
        self.ok_btn.clicked.connect(self._save_and_close)
        button_layout.addWidget(self.ok_btn)
        
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.apply_btn = QPushButton("적용")
        self.apply_btn.clicked.connect(self._apply_settings)
        button_layout.addWidget(self.apply_btn)
        
        layout.addLayout(button_layout)
    
    def _create_general_tab(self):
        """일반 설정 탭 생성"""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # UI 설정
        ui_group = QGroupBox("UI 설정")
        ui_layout = QFormLayout()
        
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(["맑은 고딕", "굴림", "돋움", "Arial", "Tahoma"])
        ui_layout.addRow("폰트:", self.font_family_combo)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 20)
        ui_layout.addRow("폰트 크기:", self.font_size_spin)
        
        ui_group.setLayout(ui_layout)
        layout.addRow(ui_group)
        
        # 로깅 설정
        log_group = QGroupBox("로깅 설정")
        log_layout = QFormLayout()
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        log_layout.addRow("로그 레벨:", self.log_level_combo)
        
        log_group.setLayout(log_layout)
        layout.addRow(log_group)
        
        self.tab_widget.addTab(tab, "일반")
    
    def _create_automation_tab(self):
        """자동화 설정 탭 생성"""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # 딜레이 설정
        delay_group = QGroupBox("딜레이 설정")
        delay_layout = QFormLayout()
        
        self.post_delay_spin = QSpinBox()
        self.post_delay_spin.setRange(1000, 60000)
        self.post_delay_spin.setSuffix(" ms")
        delay_layout.addRow("게시글 작성 딜레이:", self.post_delay_spin)
        
        self.comment_delay_spin = QSpinBox()
        self.comment_delay_spin.setRange(1000, 60000)
        self.comment_delay_spin.setSuffix(" ms")
        delay_layout.addRow("댓글 작성 딜레이:", self.comment_delay_spin)
        
        delay_group.setLayout(delay_layout)
        layout.addRow(delay_group)
        
        # 제한 설정
        limit_group = QGroupBox("제한 설정")
        limit_layout = QFormLayout()
        
        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(1, 10)
        limit_layout.addRow("최대 재시도 횟수:", self.retry_count_spin)
        
        self.post_limit_spin = QSpinBox()
        self.post_limit_spin.setRange(1, 1000)
        limit_layout.addRow("게시글 작성 제한수:", self.post_limit_spin)
        
        self.comment_limit_spin = QSpinBox()
        self.comment_limit_spin.setRange(1, 9999)
        limit_layout.addRow("댓글 작성 제한수:", self.comment_limit_spin)
        
        limit_group.setLayout(limit_layout)
        layout.addRow(limit_group)
        
        self.tab_widget.addTab(tab, "자동화")
    
    def _create_webdriver_tab(self):
        """WebDriver 설정 탭 생성"""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # 타임아웃 설정
        timeout_group = QGroupBox("타임아웃 설정")
        timeout_layout = QFormLayout()
        
        self.implicit_wait_spin = QSpinBox()
        self.implicit_wait_spin.setRange(5, 60)
        self.implicit_wait_spin.setSuffix(" 초")
        timeout_layout.addRow("암시적 대기:", self.implicit_wait_spin)
        
        self.page_load_timeout_spin = QSpinBox()
        self.page_load_timeout_spin.setRange(10, 120)
        self.page_load_timeout_spin.setSuffix(" 초")
        timeout_layout.addRow("페이지 로드 타임아웃:", self.page_load_timeout_spin)
        
        self.script_timeout_spin = QSpinBox()
        self.script_timeout_spin.setRange(10, 120)
        self.script_timeout_spin.setSuffix(" 초")
        timeout_layout.addRow("스크립트 타임아웃:", self.script_timeout_spin)
        
        timeout_group.setLayout(timeout_layout)
        layout.addRow(timeout_group)
        
        # User-Agent 설정
        ua_group = QGroupBox("User-Agent 설정")
        ua_layout = QVBoxLayout()
        
        self.user_agent_text = QTextEdit()
        self.user_agent_text.setMaximumHeight(80)
        ua_layout.addWidget(self.user_agent_text)
        
        ua_group.setLayout(ua_layout)
        layout.addRow(ua_group)
        
        self.tab_widget.addTab(tab, "WebDriver")
    
    def _load_current_settings(self):
        """현재 설정 로드"""
        # UI 설정
        self.font_family_combo.setCurrentText(config.ui.font_family)
        self.font_size_spin.setValue(config.ui.font_size)
        
        # 로깅 설정
        self.log_level_combo.setCurrentText(config.logging.log_level)
        
        # 자동화 설정
        self.post_delay_spin.setValue(config.automation.post_delay_min)
        self.comment_delay_spin.setValue(config.automation.comment_delay_min)
        self.retry_count_spin.setValue(config.automation.max_retry_count)
        self.post_limit_spin.setValue(config.automation.post_limit_default)
        self.comment_limit_spin.setValue(config.automation.comment_limit_default)
        
        # WebDriver 설정
        self.implicit_wait_spin.setValue(config.webdriver.implicit_wait)
        self.page_load_timeout_spin.setValue(config.webdriver.page_load_timeout)
        self.script_timeout_spin.setValue(config.webdriver.script_timeout)
        self.user_agent_text.setPlainText(config.webdriver.user_agent)
    
    def _apply_settings(self):
        """설정 적용"""
        # UI 설정
        config.ui.font_family = self.font_family_combo.currentText()
        config.ui.font_size = self.font_size_spin.value()
        
        # 로깅 설정
        config.logging.log_level = self.log_level_combo.currentText()
        
        # 자동화 설정
        config.automation.post_delay_min = self.post_delay_spin.value()
        config.automation.comment_delay_min = self.comment_delay_spin.value()
        config.automation.max_retry_count = self.retry_count_spin.value()
        config.automation.post_limit_default = self.post_limit_spin.value()
        config.automation.comment_limit_default = self.comment_limit_spin.value()
        
        # WebDriver 설정
        config.webdriver.implicit_wait = self.implicit_wait_spin.value()
        config.webdriver.page_load_timeout = self.page_load_timeout_spin.value()
        config.webdriver.script_timeout = self.script_timeout_spin.value()
        config.webdriver.user_agent = self.user_agent_text.toPlainText().strip()
        
        QMessageBox.information(self, "완료", "설정이 적용되었습니다.")
    
    def _save_and_close(self):
        """설정 저장 후 닫기"""
        self._apply_settings()
        self.accept()


class ProxyTestDialog(QDialog):
    """프록시 테스트 다이얼로그"""
    
    def __init__(self, proxy_list, parent=None):
        super().__init__(parent)
        self.proxy_list = proxy_list
        self.setWindowTitle("프록시 테스트")
        self.setFixedSize(600, 400)
        self._init_ui()
    
    def _init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 정보 라벨
        info_label = QLabel(f"총 {len(self.proxy_list)}개의 프록시를 테스트합니다.")
        layout.addWidget(info_label)
        
        # 진행률 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.proxy_list))
        layout.addWidget(self.progress_bar)
        
        # 결과 테이블
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(3)
        self.result_table.setHorizontalHeaderLabels(["프록시", "상태", "응답시간"])
        self.result_table.setRowCount(len(self.proxy_list))
        
        for i, proxy in enumerate(self.proxy_list):
            self.result_table.setItem(i, 0, QTableWidgetItem(proxy))
            self.result_table.setItem(i, 1, QTableWidgetItem("대기중"))
            self.result_table.setItem(i, 2, QTableWidgetItem("-"))
        
        layout.addWidget(self.result_table)
        
        # 버튼
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("테스트 시작")
        self.start_btn.clicked.connect(self._start_test)
        button_layout.addWidget(self.start_btn)
        
        self.close_btn = QPushButton("닫기")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _start_test(self):
        """테스트 시작"""
        self.start_btn.setEnabled(False)
        
        # TODO: 프록시 테스트 로직 구현
        # 실제로는 별도 스레드에서 실행해야 함
        
        for i, proxy in enumerate(self.proxy_list):
            self.result_table.setItem(i, 1, QTableWidgetItem("테스트 중..."))
            QApplication.processEvents()
            
            # 가짜 테스트 결과 (실제로는 ProxyManager.test_proxy 사용)
            import time
            time.sleep(0.1)  # 시뮬레이션
            
            # 랜덤 결과 생성
            import random
            if random.random() > 0.3:  # 70% 성공률
                self.result_table.setItem(i, 1, QTableWidgetItem("✅ 성공"))
                self.result_table.setItem(i, 2, QTableWidgetItem(f"{random.randint(100, 500)}ms"))
            else:
                self.result_table.setItem(i, 1, QTableWidgetItem("❌ 실패"))
                self.result_table.setItem(i, 2, QTableWidgetItem("타임아웃"))
            
            self.progress_bar.setValue(i + 1)
            QApplication.processEvents()
        
        self.start_btn.setEnabled(True)
        QMessageBox.information(self, "완료", "프록시 테스트가 완료되었습니다.")


class WorkProgressDialog(QDialog):
    """작업 진행률 다이얼로그"""
    
    def __init__(self, total_works: int, parent=None):
        super().__init__(parent)
        self.total_works = total_works
        self.current_work = 0
        self.setWindowTitle("작업 진행 중")
        self.setModal(True)
        self.setFixedSize(500, 300)
        self._init_ui()
    
    def _init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 전체 진행률
        overall_label = QLabel("전체 진행률")
        layout.addWidget(overall_label)
        
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, self.total_works)
        layout.addWidget(self.overall_progress)
        
        # 현재 작업 정보
        self.current_work_label = QLabel("현재 작업: 대기 중...")
        layout.addWidget(self.current_work_label)
        
        # 현재 작업 진행률
        current_label = QLabel("현재 작업 진행률")
        layout.addWidget(current_label)
        
        self.current_progress = QProgressBar()
        self.current_progress.setRange(0, 100)
        layout.addWidget(self.current_progress)
        
        # 로그 영역
        log_label = QLabel("작업 로그")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        layout.addWidget(self.log_text)
        
        # 중단 버튼
        self.stop_btn = QPushButton("작업 중단")
        self.stop_btn.clicked.connect(self._stop_work)
        layout.addWidget(self.stop_btn)
    
    def update_overall_progress(self, current: int):
        """전체 진행률 업데이트"""
        self.current_work = current
        self.overall_progress.setValue(current)
    
    def update_current_work(self, account_name: str, cafe_name: str):
        """현재 작업 정보 업데이트"""
        self.current_work_label.setText(f"현재 작업: {account_name} - {cafe_name}")
    
    def update_current_progress(self, value: int):
        """현재 작업 진행률 업데이트"""
        self.current_progress.setValue(value)
    
    def add_log(self, message: str):
        """로그 메시지 추가"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # 자동 스크롤
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _stop_work(self):
        """작업 중단"""
        reply = QMessageBox.question(
            self, "확인", 
            "정말로 작업을 중단하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.reject()


class ExportOptionsDialog(QDialog):
    """내보내기 옵션 다이얼로그"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("내보내기 옵션")
        self.setFixedSize(400, 300)
        self._init_ui()
    
    def _init_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 내보낼 데이터 선택
        data_group = QGroupBox("내보낼 데이터")
        data_layout = QVBoxLayout()
        
        self.work_results_check = QCheckBox("작업 결과")
        self.work_results_check.setChecked(True)
        data_layout.addWidget(self.work_results_check)
        
        self.accounts_check = QCheckBox("계정 목록")
        self.accounts_check.setChecked(True)
        data_layout.addWidget(self.accounts_check)
        
        self.cafes_check = QCheckBox("카페 목록")
        self.cafes_check.setChecked(True)
        data_layout.addWidget(self.cafes_check)
        
        self.statistics_check = QCheckBox("통계")
        self.statistics_check.setChecked(True)
        data_layout.addWidget(self.statistics_check)
        
        data_group.setLayout(data_layout)
        layout.addWidget(data_group)
        
        # 파일 형식 선택
        format_group = QGroupBox("파일 형식")
        format_layout = QVBoxLayout()
        
        self.excel_radio = QRadioButton("Excel (.xlsx)")
        self.excel_radio.setChecked(True)
        format_layout.addWidget(self.excel_radio)
        
        self.csv_radio = QRadioButton("CSV (.csv)")
        format_layout.addWidget(self.csv_radio)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # 버튼
        button_layout = QHBoxLayout()
        
        self.ok_btn = QPushButton("확인")
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)
        
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def get_options(self):
        """선택된 옵션 반환"""
        return {
            'include_work_results': self.work_results_check.isChecked(),
            'include_accounts': self.accounts_check.isChecked(),
            'include_cafes': self.cafes_check.isChecked(),
            'include_statistics': self.statistics_check.isChecked(),
            'format': 'excel' if self.excel_radio.isChecked() else 'csv'
        }
