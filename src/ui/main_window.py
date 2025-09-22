"""
메인 윈도우 UI 클래스
PyQt5 기반의 메인 사용자 인터페이스를 담당합니다.
"""

import sys
import logging
from datetime import datetime
from typing import List, Optional, Dict
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from ..core.config import config, MAIN_WINDOW_STYLE
from ..data.models import AppState, Account, CafeInfo, WorkStatus
from ..data.data_handler import DataHandler
from ..core.proxy_manager import ProxyManager
from .components import AccountTableWidget, CafeTableWidget, ProxyWidget, LogWidget
from .dialogs import AboutDialog, SettingsDialog


class MainWindow(QMainWindow):
    """메인 윈도우 클래스"""
    
    # 시그널 정의
    log_signal = pyqtSignal(str)
    status_update_signal = pyqtSignal(str, str)
    account_result_signal = pyqtSignal(str, str)
    ip_status_signal = pyqtSignal(str)
    levelup_counts_signal = pyqtSignal(int, int, int)
    button_state_signal = pyqtSignal(str, bool, str)
    
    def __init__(self):
        super().__init__()
        
        # 애플리케이션 상태
        self.app_state = AppState()
        
        # 데이터 핸들러
        self.data_handler = DataHandler(config.config_dir)
        
        # 프록시 매니저
        self.proxy_manager: Optional[ProxyManager] = None
        
        # 로깅 설정
        self._setup_logging()
        
        # 로거 초기화 (먼저!)
        self.logger = logging.getLogger(__name__)
        
        # UI 초기화
        self._init_ui()
        
        # 시그널 연결
        self._connect_signals()
        
        # 설정 로드
        self._load_settings()
        
        self.logger.info("메인 윈도우 초기화 완료")
    
    def _setup_logging(self):
        """로깅 설정"""
        logging.basicConfig(
            level=getattr(logging, config.logging.log_level),
            format=config.logging.log_format,
            handlers=[
                logging.FileHandler(config.get_log_file_path(), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def _init_ui(self):
        """UI 초기화"""
        self.setWindowTitle(config.ui.window_title)
        self.setGeometry(100, 100, config.ui.window_width, config.ui.window_height)
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 탭 위젯 생성
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 탭 생성
        self._create_main_tab()
        self._create_content_tab()
        self._create_integrated_tab()  # 통합 엑셀 탭 추가
        
        # 스타일 적용
        self.setStyleSheet(MAIN_WINDOW_STYLE)
        
        # 메뉴바 생성
        self._create_menu_bar()
        
        # 상태바 생성
        self._create_status_bar()
    
    def _create_main_tab(self):
        """메인 작업 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 상단 레이아웃 (계정 + 카페)
        top_layout = QHBoxLayout()
        
        # 계정 그룹
        account_group = QGroupBox("네이버 계정 세팅")
        account_layout = QVBoxLayout()
        
        # 계정 테이블
        self.account_table = AccountTableWidget()
        account_layout.addWidget(self.account_table)
        
        # 계정 버튼들
        account_btn_layout = QHBoxLayout()
        self.load_accounts_btn = QPushButton("계정 세팅 파일 불러오기")
        self.remove_account_btn = QPushButton("❌ 선택 계정 삭제")
        self.clear_accounts_btn = QPushButton("🗑️ 모든 계정 삭제")
        
        account_btn_layout.addWidget(self.load_accounts_btn)
        account_btn_layout.addWidget(self.remove_account_btn)
        account_btn_layout.addWidget(self.clear_accounts_btn)
        account_layout.addLayout(account_btn_layout)
        
        account_group.setLayout(account_layout)
        top_layout.addWidget(account_group)
        
        # 카페 그룹
        cafe_group = QGroupBox("작업 카페 세팅")
        cafe_layout = QVBoxLayout()
        
        # 카페 테이블
        self.cafe_table = CafeTableWidget()
        cafe_layout.addWidget(self.cafe_table)
        
        # 현재 상태 표시
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("작업 카페 Url:"))
        self.cafe_url_label = QLabel("카페를 선택해주세요")
        self.cafe_url_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(self.cafe_url_label)
        
        status_layout.addWidget(QLabel("내 글수:"))
        self.post_count_label = QLabel("0")
        status_layout.addWidget(self.post_count_label)
        
        status_layout.addWidget(QLabel("내 댓글수:"))
        self.comment_count_label = QLabel("0")
        status_layout.addWidget(self.comment_count_label)
        
        status_layout.addWidget(QLabel("내 방문수:"))
        self.visit_count_label = QLabel("0")
        status_layout.addWidget(self.visit_count_label)
        
        status_layout.addStretch()
        cafe_layout.addLayout(status_layout)
        
        # 카페 버튼들
        cafe_btn_layout = QHBoxLayout()
        self.load_cafe_btn = QPushButton("카페 세팅 파일 불러오기")
        self.check_conditions_btn = QPushButton("등급조건 확인하기")
        self.check_all_conditions_btn = QPushButton("🔍 모든 카페 등급조건 확인")
        self.save_settings_btn = QPushButton("세팅 내역 저장")
        
        cafe_btn_layout.addWidget(self.load_cafe_btn)
        cafe_btn_layout.addWidget(self.check_conditions_btn)
        cafe_btn_layout.addWidget(self.check_all_conditions_btn)
        cafe_btn_layout.addWidget(self.save_settings_btn)
        cafe_layout.addLayout(cafe_btn_layout)
        
        # 카페 관리 버튼들
        cafe_mgmt_layout = QHBoxLayout()
        self.remove_cafe_btn = QPushButton("❌ 선택 카페 삭제")
        self.clear_cafes_btn = QPushButton("🗑️ 모든 카페 삭제")
        
        cafe_mgmt_layout.addWidget(self.remove_cafe_btn)
        cafe_mgmt_layout.addWidget(self.clear_cafes_btn)
        cafe_mgmt_layout.addStretch()
        cafe_layout.addLayout(cafe_mgmt_layout)
        
        cafe_group.setLayout(cafe_layout)
        top_layout.addWidget(cafe_group)
        
        layout.addLayout(top_layout)
        
        # 중간 레이아웃 (설정 + 프록시 + 로그)
        middle_layout = QHBoxLayout()
        
        # 작업 설정
        settings_group = QGroupBox("작업 세팅")
        settings_layout = QFormLayout()
        
        self.ip_combo = QComboBox()
        self.ip_combo.addItems(["변경 안함", "변경함"])
        settings_layout.addRow("IP 변경 방법:", self.ip_combo)
        
        self.post_delay_min = QSpinBox()
        self.post_delay_min.setRange(1, 99999)
        self.post_delay_min.setValue(config.automation.post_delay_min)
        settings_layout.addRow("게시글 작성 딜레이:", self.post_delay_min)
        
        self.comment_delay_min = QSpinBox()
        self.comment_delay_min.setRange(1, 99999)
        self.comment_delay_min.setValue(config.automation.comment_delay_min)
        settings_layout.addRow("댓글 작성 딜레이:", self.comment_delay_min)
        
        self.post_count = QSpinBox()
        self.post_count.setRange(1, 99)
        self.post_count.setValue(config.automation.post_count_threshold)
        settings_layout.addRow("작성 실패 최수 기준:", self.post_count)
        
        self.reply_page = QSpinBox()
        self.reply_page.setRange(1, 99)
        self.reply_page.setValue(config.automation.reply_start_page)
        settings_layout.addRow("답색 시작 페이지:", self.reply_page)
        
        self.concurrent_workers = QSpinBox()
        self.concurrent_workers.setRange(1, 5)
        self.concurrent_workers.setValue(1)
        settings_layout.addRow("동시 작업 수:", self.concurrent_workers)
        
        self.headless_checkbox = QCheckBox("헤드리스 모드 (브라우저 창 숨김)")
        settings_layout.addRow(self.headless_checkbox)
        
        self.verbose_gui_log = QCheckBox("상세 로그를 GUI에 표시 (성능 저하 가능)")
        self.verbose_gui_log.setChecked(True)  # 기본값 활성화
        settings_layout.addRow(self.verbose_gui_log)
        
        self.comment_random_check = QCheckBox("댓글에 랜덤 숫자 첨부하기")
        settings_layout.addRow(self.comment_random_check)
        
        self.post_random_check = QCheckBox("게시글에 랜덤 숫자 첨부하기")
        settings_layout.addRow(self.post_random_check)
        
        settings_group.setLayout(settings_layout)
        middle_layout.addWidget(settings_group)
        
        # 프록시 위젯
        self.proxy_widget = ProxyWidget()
        middle_layout.addWidget(self.proxy_widget)
        
        # 로그 위젯
        self.log_widget = LogWidget()
        middle_layout.addWidget(self.log_widget)
        
        layout.addLayout(middle_layout)
        
        # 하단 버튼들
        bottom_layout = QHBoxLayout()
        
        self.check_condition_check = QCheckBox("방문 횟수 부족시, 작업 넘기기")
        bottom_layout.addWidget(self.check_condition_check)
        
        self.levelup_check = QCheckBox("작업 완료후, 작업 댓글 삭제하기")
        bottom_layout.addWidget(self.levelup_check)
        
        self.delete_check = QCheckBox("작업 완료후, 작업 게시글 삭제하기")
        bottom_layout.addWidget(self.delete_check)
        
        bottom_layout.addStretch()
        
        self.start_btn = QPushButton("작업 시작")
        self.start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px; padding: 10px 20px; }")
        bottom_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("작업 중단")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; font-size: 14px; padding: 10px 20px; }")
        bottom_layout.addWidget(self.stop_btn)
        
        self.export_excel_btn = QPushButton("📊 엑셀로 결과 내보내기")
        self.export_excel_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; }")
        bottom_layout.addWidget(self.export_excel_btn)
        
        layout.addLayout(bottom_layout)
        
        self.tab_widget.addTab(tab, "작업 카페 세팅")
    
    def _create_content_tab(self):
        """댓글+게시글 세팅 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 댓글 그룹
        comment_group = QGroupBox("댓글+게시글 세팅")
        comment_layout = QVBoxLayout()
        
        self.comment_text = QTextEdit()
        self.comment_text.setPlaceholderText("안녕하세요 ㅎㅎ")
        comment_layout.addWidget(self.comment_text)
        
        comment_limit_layout = QHBoxLayout()
        comment_limit_layout.addWidget(QLabel("댓글 작성 제한수:"))
        self.comment_limit = QSpinBox()
        self.comment_limit.setRange(1, 9999)
        self.comment_limit.setValue(config.automation.comment_limit_default)
        comment_limit_layout.addWidget(self.comment_limit)
        comment_limit_layout.addStretch()
        
        comment_layout.addLayout(comment_limit_layout)
        comment_group.setLayout(comment_layout)
        layout.addWidget(comment_group)
        
        # 게시글 그룹
        post_group = QGroupBox("게시글 내용 세팅란")
        post_layout = QVBoxLayout()
        
        post_layout.addWidget(QLabel("제목:"))
        self.post_title = QLineEdit()
        self.post_title.setPlaceholderText("안녕하세요")
        post_layout.addWidget(self.post_title)
        post_layout.addWidget(QLabel("※ 제목 원본 기준 여러개 세팅 가능합니다."))
        
        post_layout.addWidget(QLabel("본문:"))
        self.post_text = QTextEdit()
        self.post_text.setPlaceholderText("잘부탁드립니다")
        post_layout.addWidget(self.post_text)
        
        post_limit_layout = QHBoxLayout()
        post_limit_layout.addWidget(QLabel("게시글 작성 제한수:"))
        self.post_limit = QSpinBox()
        self.post_limit.setRange(1, 9999)
        self.post_limit.setValue(config.automation.post_limit_default)
        post_limit_layout.addWidget(self.post_limit)
        post_limit_layout.addStretch()
        
        post_layout.addLayout(post_limit_layout)
        post_group.setLayout(post_layout)
        layout.addWidget(post_group)
        
        # 로그 위젯 (복사본)
        log_group = QGroupBox("작업 로그")
        log_layout = QVBoxLayout()
        
        # 작업 정보
        work_info_layout = QHBoxLayout()
        work_info_layout.addWidget(QLabel("- 현재 IP:"))
        self.current_ip_label2 = QLabel("미확인")
        self.current_ip_label2.setStyleSheet("color: red;")
        work_info_layout.addWidget(self.current_ip_label2)
        work_info_layout.addStretch()
        
        work_info_layout.addWidget(QLabel("- 작업 상태:"))
        self.search_status_label2 = QLabel("대기중")
        self.search_status_label2.setStyleSheet("color: red;")
        work_info_layout.addWidget(self.search_status_label2)
        
        log_layout.addLayout(work_info_layout)
        
        # 로그 텍스트
        self.log_text2 = QTextEdit()
        self.log_text2.setReadOnly(True)
        log_layout.addWidget(self.log_text2)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        self.tab_widget.addTab(tab, "댓글+게시글 세팅")
    
    def _create_menu_bar(self):
        """메뉴바 생성"""
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu('파일')
        
        # 설정 불러오기
        load_settings_action = QAction('설정 불러오기', self)
        load_settings_action.triggered.connect(self._load_settings)
        file_menu.addAction(load_settings_action)
        
        # 설정 저장
        save_settings_action = QAction('설정 저장', self)
        save_settings_action.triggered.connect(self._save_settings)
        file_menu.addAction(save_settings_action)
        
        file_menu.addSeparator()
        
        # 종료
        exit_action = QAction('종료', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 도구 메뉴
        tools_menu = menubar.addMenu('도구')
        
        # 설정
        settings_action = QAction('환경설정', self)
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu('도움말')
        
        # 버전 정보
        version_action = QAction('버전 정보', self)
        version_action.triggered.connect(self._show_version)
        help_menu.addAction(version_action)
        
        help_menu.addSeparator()
        
        # 정보
        about_action = QAction('정보', self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _create_status_bar(self):
        """상태바 생성"""
        self.status_bar = self.statusBar()
        
        # 현재 IP 표시
        self.current_ip_status = QLabel("현재 IP: 미확인")
        self.status_bar.addWidget(self.current_ip_status)
        
        # 작업 상태 표시
        self.work_status = QLabel("작업 상태: 대기중")
        self.status_bar.addPermanentWidget(self.work_status)
    
    def _connect_signals(self):
        """시그널 연결"""
        # 로그 시그널
        self.log_signal.connect(self._append_log)
        
        # 상태 업데이트 시그널
        self.status_update_signal.connect(self._update_status_label)
        
        # 계정 결과 시그널
        self.account_result_signal.connect(self._update_account_result)
        
        # IP 상태 시그널
        self.ip_status_signal.connect(self._update_ip_status)
        
        # 등급 카운트 시그널
        self.levelup_counts_signal.connect(self._update_levelup_counts)
        
        # 버튼 상태 시그널
        self.button_state_signal.connect(self._update_button_state)
        
        # 버튼 연결
        self._connect_button_signals()
    
    def _connect_button_signals(self):
        """버튼 시그널 연결"""
        # 계정 관련
        self.load_accounts_btn.clicked.connect(self._load_accounts)
        self.remove_account_btn.clicked.connect(self._remove_selected_account)
        self.clear_accounts_btn.clicked.connect(self._clear_all_accounts)
        
        # 카페 관련
        self.load_cafe_btn.clicked.connect(self._load_cafes)
        self.remove_cafe_btn.clicked.connect(self._remove_selected_cafe)
        self.clear_cafes_btn.clicked.connect(self._clear_all_cafes)
        self.check_conditions_btn.clicked.connect(self._check_conditions)
        self.check_all_conditions_btn.clicked.connect(self._check_all_conditions)
        
        # 작업 관련
        self.start_btn.clicked.connect(self._start_work)
        self.stop_btn.clicked.connect(self._stop_work)
        
        # 기타
        self.save_settings_btn.clicked.connect(self._save_settings)
        self.export_excel_btn.clicked.connect(self._export_results)
    
    def _append_log(self, message: str):
        """로그 메시지 추가 (성능 최적화)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        
        # GUI 로그 병목 해결: 중요한 로그만 GUI에 표시
        show_in_gui = (
            self.verbose_gui_log.isChecked() or  # 상세 로그 옵션이 켜져있거나
            any(keyword in message for keyword in [  # 중요한 키워드가 포함된 경우만
                "✅", "❌", "🎉", "🚀", "📊", "🔍", "⚠️", "💬", "📝", 
                "시작", "완료", "실패", "성공", "오류", "등급조건", "로그인"
            ])
        )
        
        if show_in_gui:
            self.log_widget.append_log(log_entry)
            if hasattr(self, 'log_text2'):
                self.log_text2.append(log_entry)
        
        # 파일 로그는 항상 기록
        self.logger.info(message)
    
    def _update_status_label(self, label_name: str, text: str):
        """상태 라벨 업데이트"""
        if label_name == "search_status":
            self.log_widget.update_status(text)
            if hasattr(self, 'search_status_label2'):
                self.search_status_label2.setText(text)
            self.work_status.setText(f"작업 상태: {text}")
        elif label_name == "current_ip":
            self.log_widget.update_ip(text)
            if hasattr(self, 'current_ip_label2'):
                self.current_ip_label2.setText(text)
            self.current_ip_status.setText(f"현재 IP: {text}")
    
    def _update_account_result(self, account_id: str, result: str):
        """계정 결과 업데이트"""
        self.account_table.update_result(account_id, result)
        
        # 작업 결과 기록
        # TODO: 작업 결과를 app_state에 기록
    
    def _update_ip_status(self, ip_text: str):
        """IP 상태 업데이트"""
        self._update_status_label("current_ip", ip_text)
    
    def _update_levelup_counts(self, posts: int, comments: int, visits: int):
        """등급 현황 카운트 업데이트"""
        self.post_count_label.setText(str(posts))
        self.comment_count_label.setText(str(comments))
        self.visit_count_label.setText(str(visits))
        
        # 앱 상태 업데이트
        self.app_state.current_posts_count = posts
        self.app_state.current_comments_count = comments
        self.app_state.current_visits_count = visits
    
    def _update_button_state(self, button_name: str, enabled: bool, text: str):
        """버튼 상태 업데이트"""
        if button_name == "check_conditions":
            self.check_conditions_btn.setEnabled(enabled)
            if text:
                self.check_conditions_btn.setText(text)
        elif button_name == "check_all_conditions":
            self.check_all_conditions_btn.setEnabled(enabled)
            if text:
                self.check_all_conditions_btn.setText(text)
    
    # 슬롯 메서드들
    def _load_accounts(self):
        """계정 파일 로드"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "계정 파일 선택", 
                "", 
                "Excel files (*.xlsx *.xls);;All files (*.*)"
            )
            
            if not file_path:
                return
            
            accounts = self.data_handler.load_accounts_from_excel(file_path)
            self.app_state.accounts = accounts
            self.account_table.set_accounts(accounts)
            
            self.log_signal.emit(f"계정 {len(accounts)}개 로드 완료")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"계정 파일 읽기 실패:\n{str(e)}")
    
    def _remove_selected_account(self):
        """선택된 계정 삭제"""
        selected_row = self.account_table.get_selected_row()
        if selected_row == -1:
            QMessageBox.warning(self, "경고", "삭제할 계정을 선택해주세요.")
            return
        
        if selected_row >= len(self.app_state.accounts):
            QMessageBox.warning(self, "경고", "잘못된 계정 선택입니다.")
            return
        
        account = self.app_state.accounts[selected_row]
        reply = QMessageBox.question(
            self, "확인", 
            f"계정 '{account.id}'를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.app_state.accounts[selected_row]
            self.account_table.set_accounts(self.app_state.accounts)
            self.log_signal.emit(f"❌ 계정 삭제됨: {account.id}")
    
    def _clear_all_accounts(self):
        """모든 계정 삭제"""
        if not self.app_state.accounts:
            QMessageBox.information(self, "알림", "삭제할 계정이 없습니다.")
            return
        
        reply = QMessageBox.question(
            self, "확인", 
            f"총 {len(self.app_state.accounts)}개의 계정을 모두 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.app_state.accounts.clear()
            self.account_table.set_accounts(self.app_state.accounts)
            self.log_signal.emit("🗑️ 모든 계정이 삭제되었습니다.")
    
    def _load_cafes(self):
        """카페 파일 로드"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "카페 설정 파일 선택", 
                "", 
                "Excel files (*.xlsx *.xls);;All files (*.*)"
            )
            
            if not file_path:
                return
            
            cafes = self.data_handler.load_cafes_from_excel(file_path)
            self.app_state.cafes = cafes
            self.cafe_table.set_cafes(cafes)
            
            self.log_signal.emit(f"카페 설정 {len(cafes)}개 로드 완료")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"카페 설정 파일 읽기 실패:\n{str(e)}")
    
    def _remove_selected_cafe(self):
        """선택된 카페 삭제"""
        selected_row = self.cafe_table.get_selected_row()
        if selected_row == -1:
            QMessageBox.warning(self, "경고", "삭제할 카페를 선택해주세요.")
            return
        
        if selected_row >= len(self.app_state.cafes):
            QMessageBox.warning(self, "경고", "잘못된 카페 선택입니다.")
            return
        
        cafe = self.app_state.cafes[selected_row]
        reply = QMessageBox.question(
            self, "확인", 
            f"카페 '{cafe.cafe_id}'를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.app_state.cafes[selected_row]
            self.cafe_table.set_cafes(self.app_state.cafes)
            self.cafe_url_label.setText("카페를 선택해주세요")
            self.log_signal.emit(f"❌ 카페 삭제됨: {cafe.cafe_id}")
    
    def _clear_all_cafes(self):
        """모든 카페 삭제"""
        if not self.app_state.cafes:
            QMessageBox.information(self, "알림", "삭제할 카페가 없습니다.")
            return
        
        reply = QMessageBox.question(
            self, "확인", 
            f"총 {len(self.app_state.cafes)}개의 카페를 모두 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.app_state.cafes.clear()
            self.cafe_table.set_cafes(self.app_state.cafes)
            self.cafe_url_label.setText("카페를 선택해주세요")
            self.log_signal.emit("🗑️ 모든 카페가 삭제되었습니다.")
    
    def _check_conditions(self):
        """등급조건 확인"""
        try:
            if not self.app_state.cafes:
                QMessageBox.warning(self, "경고", "카페 설정을 먼저 불러와주세요.")
                return
                
            if not self.app_state.accounts:
                QMessageBox.warning(self, "경고", "계정 정보를 먼저 불러와주세요.")
                return
                
            current_row = self.cafe_table.get_selected_row()
            if current_row == -1:
                QMessageBox.warning(self, "경고", "카페 테이블에서 작업할 카페를 선택해주세요.")
                return
                
            if current_row >= len(self.app_state.cafes):
                QMessageBox.warning(self, "경고", "잘못된 카페가 선택되었습니다.")
                return
            
            # 선택된 카페 정보 확인
            cafe_info = self.app_state.cafes[current_row]
            if not cafe_info.target_board_id:
                QMessageBox.warning(self, "경고", "엑셀 파일에서 목표 게시판 ID(C열)를 확인해주세요.")
                return
            
            self.log_signal.emit("등업 조건 확인을 시작합니다...")
            self.log_signal.emit(f"🎯 대상 카페: {cafe_info.cafe_id}")
            self.log_signal.emit(f"👤 사용 계정: {self.app_state.accounts[0].id}")
            
            # 버튼 비활성화
            self.button_state_signal.emit("check_conditions", False, "조건 확인 중...")
            
            # 워커 스레드 시작
            from ..workers.levelup_worker import LevelupConditionWorker
            
            self.condition_worker = LevelupConditionWorker(cafe_info, self.app_state.accounts[0])
            self.condition_worker.log_signal.connect(self._append_log)
            self.condition_worker.result_signal.connect(self._on_levelup_conditions_result)
            self.condition_worker.button_signal.connect(self._update_button_state)
            self.condition_worker.account_signal.connect(self._update_account_result)
            self.condition_worker.start()
            
        except Exception as e:
            self.log_signal.emit(f"❌ 등급조건 확인 준비 중 오류: {str(e)}")
            QMessageBox.critical(self, "오류", f"등급조건 확인 준비 중 오류가 발생했습니다:\n{str(e)}")
            self.button_state_signal.emit("check_conditions", True, "등급조건 확인하기")
    
    def _check_all_conditions(self):
        """모든 카페 등급조건 확인"""
        try:
            if not self.app_state.cafes:
                QMessageBox.warning(self, "경고", "카페 설정을 먼저 불러와주세요.")
                return
                
            if not self.app_state.accounts:
                QMessageBox.warning(self, "경고", "계정 정보를 먼저 불러와주세요.")
                return
            
            self.log_signal.emit(f"🔍 모든 카페({len(self.app_state.cafes)}개) 등급조건 확인을 시작합니다...")
            
            # 버튼 비활성화
            self.button_state_signal.emit("check_all_conditions", False, "전체 조건 확인 중...")
            
            # 워커 스레드 시작
            from ..workers.levelup_worker import AllLevelupConditionWorker
            
            self.all_condition_worker = AllLevelupConditionWorker(self.app_state.cafes, self.app_state.accounts[0])
            self.all_condition_worker.log_signal.connect(self._append_log)
            self.all_condition_worker.table_signal.connect(self._on_cafe_conditions_result)
            self.all_condition_worker.button_signal.connect(self._update_button_state)
            self.all_condition_worker.account_signal.connect(self._update_account_result)
            self.all_condition_worker.start()
            
        except Exception as e:
            self.log_signal.emit(f"❌ 전체 등급조건 확인 준비 중 오류: {str(e)}")
            QMessageBox.critical(self, "오류", f"전체 등급조건 확인 중 오류가 발생했습니다:\n{str(e)}")
            self.button_state_signal.emit("check_all_conditions", True, "🔍 모든 카페 등급조건 확인")
    
    def _start_work(self):
        """작업 시작"""
        if not self.app_state.accounts:
            QMessageBox.warning(self, "경고", "계정을 먼저 불러와주세요.")
            return
        
        if not self.app_state.cafes:
            QMessageBox.warning(self, "경고", "카페 설정을 먼저 불러와주세요.")
            return
        
        self.app_state.is_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_update_signal.emit("search_status", "작업중")
        
        # 작업 시작 시간 기록
        from datetime import datetime
        self.app_state.work_start_time = datetime.now()
        self.app_state.work_results = []
        
        # 프록시 매니저 초기화
        proxy_list = self.proxy_widget.get_proxy_list()
        if proxy_list:
            from ..core.proxy_manager import ProxyManager
            self.proxy_manager = ProxyManager(proxy_list)
            self.log_signal.emit(f"🌐 프록시 매니저 초기화 완료: {len(proxy_list)}개 프록시")
        else:
            self.proxy_manager = None
            self.log_signal.emit("🌐 프록시 없이 직접 연결로 실행")
        
        self.log_signal.emit("=" * 50)
        self.log_signal.emit("🚀 모든 계정으로 모든 카페 작업을 시작합니다...")
        self.log_signal.emit(f"📊 처리 예정: {len(self.app_state.accounts)}개 계정 × {len(self.app_state.cafes)}개 카페")
        
        # 작업 큐 생성
        self._create_work_queue()
        
        # 첫 번째 작업 시작
        self._start_next_work()
    
    def _stop_work(self):
        """작업 중단"""
        self.app_state.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_update_signal.emit("search_status", "중지됨")
        
        # 기존 단일 워커 중지
        if hasattr(self, 'current_levelup_worker') and self.current_levelup_worker:
            if self.current_levelup_worker.isRunning():
                self.current_levelup_worker.terminate()
        
        # 병렬 시트 워커들 중지
        if hasattr(self, 'sheet_workers') and self.sheet_workers:
            self.log_signal.emit("⏹️ 모든 시트 작업 중지 중...")
            
            for sheet_name, worker in self.sheet_workers.items():
                try:
                    self._log_to_sheet(sheet_name, "⏹️ 작업 중지 요청됨")
                    if worker.isRunning():
                        worker.terminate()
                        worker.wait(2000)  # 2초 대기
                except Exception as e:
                    self._log_to_sheet(sheet_name, f"❌ 중지 처리 실패: {str(e)}")
            
            self.sheet_workers.clear()
            self.completed_sheets.clear()
            
            # 통합 엑셀 버튼 상태 복원
            self.start_all_work_btn.setEnabled(True)
            self.stop_work_btn.setEnabled(False)
            
            self.log_signal.emit("✅ 모든 시트 작업이 중지되었습니다.")
        else:
            self.log_signal.emit("❌ 작업을 중지했습니다.")
    
    def _save_settings(self):
        """설정 저장"""
        try:
            self.data_handler.save_settings(self.app_state)
            self.log_signal.emit("✅ 설정이 저장되었습니다.")
            QMessageBox.information(self, "완료", "설정이 성공적으로 저장되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"설정 저장 실패:\n{str(e)}")
    
    def _load_settings(self):
        """설정 로드"""
        try:
            settings = self.data_handler.load_settings()
            if settings:
                # 계정 로드
                if 'accounts' in settings:
                    accounts = [Account(id=acc['id'], pw=acc['pw']) for acc in settings['accounts']]
                    self.app_state.accounts = accounts
                    self.account_table.set_accounts(accounts)
                
                # 카페 로드
                if 'cafes' in settings:
                    cafes = [CafeInfo(**cafe_data) for cafe_data in settings['cafes']]
                    self.app_state.cafes = cafes
                    self.cafe_table.set_cafes(cafes)
                
                self.log_signal.emit("✅ 설정이 로드되었습니다.")
            else:
                self.log_signal.emit("ℹ️ 저장된 설정이 없습니다.")
        except Exception as e:
            self.log_signal.emit(f"❌ 설정 로드 실패: {str(e)}")
    
    def _export_results(self):
        """결과 엑셀로 내보내기"""
        try:
            if not self.app_state.work_results and not self.app_state.accounts:
                QMessageBox.warning(self, "경고", "내보낼 데이터가 없습니다.")
                return
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "엑셀 파일 저장",
                f"카페등업결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "Excel files (*.xlsx);;All files (*.*)"
            )
            
            if not file_path:
                return
            
            self.data_handler.export_results_to_excel(self.app_state, file_path)
            
            self.log_signal.emit(f"✅ 엑셀 파일 저장 완료: {file_path}")
            QMessageBox.information(self, "완료", f"엑셀 파일이 성공적으로 저장되었습니다!\n\n저장 위치: {file_path}")
            
        except Exception as e:
            self.log_signal.emit(f"❌ 엑셀 파일 생성 실패: {str(e)}")
            QMessageBox.critical(self, "오류", f"엑셀 파일 생성 중 오류가 발생했습니다:\n{str(e)}")
    
    def _open_settings(self):
        """환경설정 다이얼로그 열기"""
        dialog = SettingsDialog(self)
        dialog.exec_()
    
    def _show_version(self):
        """버전 정보 다이얼로그 표시"""
        current_version = QApplication.instance().applicationVersion()
        msg = QMessageBox(self)
        msg.setWindowTitle("버전 정보")
        msg.setIcon(QMessageBox.Information)
        msg.setText(f"현재 버전: v{current_version}")
        msg.setInformativeText("업데이트가 있을 경우 자동으로 알림이 표시됩니다.")
        msg.exec_()
    
    def _show_about(self):
        """정보 다이얼로그 표시"""
        dialog = AboutDialog(self)
        dialog.exec_()
    
    def _create_work_queue(self):
        """작업 큐 생성"""
        from ..data.models import WorkTask
        
        self.app_state.current_work_queue = []
        for account_idx, account in enumerate(self.app_state.accounts):
            for cafe_idx, cafe_info in enumerate(self.app_state.cafes):
                # 이미 확인된 등급조건 가져오기
                conditions = self.app_state.cafe_conditions.get(cafe_info.cafe_id)
                
                # 실패한 카페(등업게시판 등)는 작업 큐에서 제외
                if conditions is None:
                    self.log_signal.emit(f"🚫 {cafe_info.cafe_id} 카페는 자동화 불가능하여 작업 큐에서 제외됩니다.")
                    continue
                
                # 이미 달성된 카페는 작업 큐에서 제외
                if conditions.already_achieved:
                    self.log_signal.emit(f"🎉 {cafe_info.cafe_id} 카페는 이미 달성되어 작업 큐에서 제외됩니다.")
                    continue
                
                task = WorkTask(
                    account_idx=account_idx,
                    account=account,
                    cafe_idx=cafe_idx,
                    cafe_info=cafe_info,
                    conditions=conditions  # 미리 확인된 조건 사용
                )
                self.app_state.current_work_queue.append(task)
        
        self.app_state.current_work_index = 0
        
        self.log_signal.emit(f"📋 작업 큐 생성 완료: {len(self.app_state.current_work_queue)}개 작업 (자동화 가능한 카페만)")
    
    def _start_next_work(self):
        """다음 작업 시작"""
        if not self.app_state.is_running:
            return
        
        if self.app_state.current_work_index >= len(self.app_state.current_work_queue):
            # 모든 작업 완료
            self.log_signal.emit(f"🔚 작업 완료: 인덱스 {self.app_state.current_work_index}, 큐 크기 {len(self.app_state.current_work_queue)}")
            self._work_completed()
            return
        
        # 현재 작업 정보
        current_task = self.app_state.current_work_queue[self.app_state.current_work_index]
        
        self.log_signal.emit("=" * 50)
        self.log_signal.emit(f"📋 진행상황: {self.app_state.current_work_index + 1}/{len(self.app_state.current_work_queue)}")
        self.log_signal.emit(f"👤 계정: {current_task.account.id}")
        self.log_signal.emit(f"☕ 카페: {current_task.cafe_info.cafe_id}")
        
        # 작업 설정 준비
        work_settings = {
            'comment_text': self.comment_text.toPlainText().strip() or "안녕하세요",
            'post_title': self.post_title.text().strip() or "안녕하세요",
            'post_content': self.post_text.toPlainText().strip() or "잘부탁드립니다",
            'add_random_numbers': self.comment_random_check.isChecked() or self.post_random_check.isChecked(),
            'delete_after_work': self.levelup_check.isChecked() or self.delete_check.isChecked(),
            'skip_if_visit_insufficient': self.check_condition_check.isChecked(),
            'headless_mode': self.headless_checkbox.isChecked(),
            'post_delay': self.post_delay_min.value(),
            'comment_delay': self.comment_delay_min.value(),
            'reply_start_page': self.reply_page.value()
        }
        
        # 브라우저 재사용 여부 판단 (디버깅 강화)
        reuse_browser = False
        
        # 계정 변경 감지 및 처리
        account_changed = self.app_state.current_browser_account != current_task.account.id
        
        if account_changed and hasattr(self, 'shared_driver') and self.shared_driver:
            self.log_signal.emit(f"🔄 계정 변경 감지: {self.app_state.current_browser_account} → {current_task.account.id}")
            self.log_signal.emit("🔚 기존 계정 브라우저 완전 종료 (보안)")
            
            # 기존 브라우저 완전 종료
            try:
                self.shared_driver.quit()
                self.log_signal.emit("✅ 기존 브라우저 종료 완료")
            except:
                self.log_signal.emit("✅ 기존 브라우저 종료 완료 (이미 종료됨)")
            
            self.shared_driver = None
            self.current_levelup_worker = None
            
            # 새 계정용 프록시 할당 필요 (프록시 매니저에서 다음 프록시)
            if self.proxy_manager:
                self.log_signal.emit("🔄 새 계정용 프록시 할당 중...")
        
        # 각 재사용 조건 개별 확인
        condition1 = hasattr(self, 'current_levelup_worker')
        condition2 = bool(getattr(self, 'current_levelup_worker', None))
        condition3 = self.app_state.current_browser_account == current_task.account.id
        condition4 = self.app_state.browser_reuse_mode
        
        self.log_signal.emit(f"🔍 재사용 조건1 (worker 존재): {condition1}")
        self.log_signal.emit(f"🔍 재사용 조건2 (worker 활성): {condition2}")
        self.log_signal.emit(f"🔍 재사용 조건3 (같은 계정): {condition3} (현재:{self.app_state.current_browser_account}, 작업:{current_task.account.id})")
        self.log_signal.emit(f"🔍 재사용 조건4 (재사용 모드): {condition4}")
        
        if condition1 and condition2 and condition3 and condition4 and not account_changed:
            reuse_browser = True
            self.log_signal.emit(f"✅ 모든 조건 만족 → 브라우저 재사용: {current_task.account.id}")
        else:
            if account_changed:
                self.log_signal.emit(f"🔄 계정 변경으로 새 브라우저 생성: {current_task.account.id}")
            else:
                self.log_signal.emit(f"❌ 조건 불만족 → 새 브라우저 생성: {current_task.account.id}")
        
        # 계정 정보는 항상 업데이트
        self.app_state.current_browser_account = current_task.account.id
        
        # 미래 예측: 다음 작업도 같은 계정인지 확인
        next_idx = self.app_state.current_work_index + 1
        same_account_remains = False
        if next_idx < len(self.app_state.current_work_queue):
            next_task = self.app_state.current_work_queue[next_idx]
            same_account_remains = (next_task.account.id == current_task.account.id)
            self.log_signal.emit(f"🔮 다음 작업 예측: {next_task.account.id} (같은 계정: {same_account_remains})")
        else:
            self.log_signal.emit("🔮 다음 작업 없음 - 마지막 작업")
        
        # LevelupWorker 시작
        from ..workers.levelup_worker import LevelupWorker
        
        self.current_levelup_worker = LevelupWorker(
            current_task.cafe_info,
            current_task.account,
            current_task.conditions,
            self.proxy_manager,
            work_settings,
            reuse_browser=reuse_browser,
            existing_driver=getattr(self, 'shared_driver', None) if reuse_browser else None
        )
        
        # ★★ 핵심: 같은 계정 작업이 남아있으면 드라이버 유지 ★★
        self.current_levelup_worker.keep_open_after_finish = same_account_remains or reuse_browser
        self.log_signal.emit(f"🔧 드라이버 유지 설정: {self.current_levelup_worker.keep_open_after_finish} (같은계정남음:{same_account_remains}, 재사용:{reuse_browser})")
        
        self.current_levelup_worker.log_signal.connect(self._append_log)
        self.current_levelup_worker.status_signal.connect(self._update_status_label)
        self.current_levelup_worker.account_signal.connect(self._update_account_result)
        self.current_levelup_worker.progress_signal.connect(self._update_levelup_counts)
        self.current_levelup_worker.finished_signal.connect(self._on_work_finished)
        self.current_levelup_worker.start()
        
        # 브라우저 재사용을 위해 드라이버 저장
        if not reuse_browser:
            def save_driver():
                if hasattr(self.current_levelup_worker, 'driver') and self.current_levelup_worker.driver:
                    self.shared_driver = self.current_levelup_worker.driver
            # 드라이버 생성 후 저장하기 위해 타이머 사용
            QTimer.singleShot(5000, save_driver)
    
    def _on_work_finished(self, success: bool, message: str):
        """작업 완료 처리"""
        current_task = self.app_state.current_work_queue[self.app_state.current_work_index]
        
        # 작업 결과 기록
        from ..data.models import WorkResult
        from datetime import datetime
        
        result = WorkResult(
            account_id=current_task.account.id,
            account_password=current_task.account.pw,
            cafe_name=current_task.cafe_info.cafe_id,
            cafe_url=current_task.cafe_info.url,
            work_result=message,
            work_datetime=datetime.now(),
            posts_count=self.app_state.current_posts_count,
            comments_count=self.app_state.current_comments_count,
            visits_count=self.app_state.current_visits_count,
            used_proxy=self.app_state.current_proxy or "사용안함"
        )
        
        self.app_state.add_work_result(result)
        
        # 워커가 쓴 드라이버를 shared_driver에 동기화 (닫히지 않은 상태)
        try:
            if hasattr(self.current_levelup_worker, 'driver') and self.current_levelup_worker.driver:
                if not hasattr(self, 'shared_driver') or self.shared_driver != self.current_levelup_worker.driver:
                    self.shared_driver = self.current_levelup_worker.driver
                    self.log_signal.emit("🔄 shared_driver 동기화 완료")
        except Exception as e:
            self.log_signal.emit(f"⚠️ shared_driver 동기화 경고: {e}")
        
        # 다음 작업으로 이동
        self.app_state.current_work_index += 1
        self.log_signal.emit(f"📈 작업 인덱스 증가: {self.app_state.current_work_index}/{len(self.app_state.current_work_queue)}")
        
        # 잠시 대기 후 다음 작업 시작
        QTimer.singleShot(2000, self._start_next_work)
    
    def _work_completed(self):
        """모든 작업 완료"""
        self.app_state.is_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_update_signal.emit("search_status", "대기중")
        
        self.log_signal.emit("🎉 모든 계정의 모든 카페 작업이 완료되었습니다!")
        
        # 마지막에 브라우저 강제 종료 (보호 무시)
        if hasattr(self, 'shared_driver') and self.shared_driver:
            try:
                # 보호 플래그 제거 후 강제 종료
                if hasattr(self.shared_driver, '_protected_from_close'):
                    delattr(self.shared_driver, '_protected_from_close')
                if hasattr(self.shared_driver, '_reuse_mode'):
                    delattr(self.shared_driver, '_reuse_mode')
                
                self.shared_driver.quit()  # 직접 종료 (보호 우회)
                self.shared_driver = None
                self.log_signal.emit("🔚 모든 작업 완료 - 브라우저 최종 종료")
            except Exception as e:
                self.log_signal.emit(f"⚠️ 브라우저 종료 중 오류: {str(e)}")
                self.log_signal.emit("🔚 모든 작업 완료 - 브라우저 최종 종료")
        
        # 브라우저 상태 초기화
        self.app_state.current_browser_account = None
        
        # 통계 정보 출력
        stats = self.app_state.get_work_statistics()
        self.log_signal.emit(f"📊 최종 통계: 총 {stats['total_works']}개 작업 완료")
        
        if stats['elapsed_time']:
            self.log_signal.emit(f"⏱️ 총 소요 시간: {str(stats['elapsed_time']).split('.')[0]}")
    
    def _on_levelup_conditions_result(self, conditions_dict: dict, cafe_name: str):
        """등급조건 확인 결과 처리"""
        try:
            if conditions_dict.get('already_achieved', False):
                self.log_signal.emit(f"[{cafe_name}] 🎉 이미 등급이 달성되어 있습니다!")
                
                # 달성 표시
                self.levelup_counts_signal.emit(999, 999, 999)
                
                # 테이블 업데이트
                current_row = self.cafe_table.get_selected_row()
                if current_row >= 0:
                    self.cafe_table.update_conditions(cafe_name, "✅ 달성", "✅ 달성", "✅ 달성")
            else:
                # 일반적인 등급조건 처리
                self.levelup_counts_signal.emit(
                    conditions_dict['current_posts'],
                    conditions_dict['current_comments'], 
                    conditions_dict['current_visits']
                )
                
                # 테이블 업데이트
                current_row = self.cafe_table.get_selected_row()
                if current_row >= 0:
                    self.cafe_table.update_conditions(
                        cafe_name,
                        f"{conditions_dict['posts_required']}개",
                        f"{conditions_dict['comments_required']}개",
                        f"{conditions_dict['visits_required']}회"
                    )
                
                # 부족한 조건 계산 및 표시
                posts_needed = max(0, conditions_dict['posts_required'] - conditions_dict['current_posts'])
                comments_needed = max(0, conditions_dict['comments_required'] - conditions_dict['current_comments'])
                visits_needed = max(0, conditions_dict['visits_required'] - conditions_dict['current_visits'])
                
                if posts_needed > 0 or comments_needed > 0 or visits_needed > 0:
                    self.log_signal.emit("🚀 부족한 조건:")
                    if posts_needed > 0:
                        self.log_signal.emit(f"• 게시글 {posts_needed}개 더 필요")
                    if comments_needed > 0:
                        self.log_signal.emit(f"• 댓글 {comments_needed}개 더 필요")
                    if visits_needed > 0:
                        self.log_signal.emit(f"• 방문 {visits_needed}회 더 필요")
                else:
                    self.log_signal.emit("🎉 등업 조건을 모두 만족했습니다!")
            
        except Exception as e:
            self.log_signal.emit(f"❌ 등급조건 결과 처리 오류: {str(e)}")
    
    def _on_cafe_conditions_result(self, cafe_id: str, conditions_dict: dict):
        """카페별 등급조건 결과 처리"""
        try:
            # 조건 결과를 앱 상태에 저장 (나중에 작업 시 재사용)
            from ..data.models import LevelupConditions
            
            if conditions_dict.get('failure_reason'):
                # 실패한 경우 - 실패 사유 표시
                failure_reason = conditions_dict.get('failure_reason', '알 수 없는 오류')
                
                # 글쓰기 조건 카페 특별 처리
                if 'writing_conditions_required' in failure_reason or '글쓰기 조건' in failure_reason:
                    self.cafe_table.update_conditions(cafe_id, "❌ 글쓰기조건", "❌ 글쓰기조건", "❌ 글쓰기조건")
                    self.log_signal.emit(f"🚫 {cafe_id} 카페는 글쓰기 조건이 있어 자동화 불가능합니다.")
                else:
                    self.cafe_table.update_conditions(cafe_id, f"❌ {failure_reason}", f"❌ {failure_reason}", f"❌ {failure_reason}")
                
                # 실패한 카페는 조건을 None으로 저장
                self.app_state.cafe_conditions[cafe_id] = None
                
            elif conditions_dict.get('already_achieved', False):
                # 이미 달성한 경우
                self.cafe_table.update_conditions(cafe_id, "✅ 달성", "✅ 달성", "✅ 달성")
                
                # 달성된 카페는 더미 조건 객체 생성
                conditions = LevelupConditions(
                    posts_required=0,
                    comments_required=0,
                    visits_required=0,
                    current_posts=999,
                    current_comments=999,
                    current_visits=999,
                    already_achieved=True,
                    target_level_name="달성됨"
                )
                self.app_state.cafe_conditions[cafe_id] = conditions
                
            else:
                # 정상적인 조건 표시
                self.cafe_table.update_conditions(
                    cafe_id,
                    f"{conditions_dict['posts_required']}개",
                    f"{conditions_dict['comments_required']}개", 
                    f"{conditions_dict['visits_required']}회"
                )
                
                # 미달성 카페는 실제 조건 객체 생성
                conditions = LevelupConditions(
                    posts_required=conditions_dict['posts_required'],
                    comments_required=conditions_dict['comments_required'],
                    visits_required=conditions_dict['visits_required'],
                    current_posts=conditions_dict['current_posts'],
                    current_comments=conditions_dict['current_comments'],
                    current_visits=conditions_dict['current_visits'],
                    already_achieved=False,
                    target_level_name=conditions_dict.get('target_level_name', '미달성')
                )
                self.app_state.cafe_conditions[cafe_id] = conditions
            
        except Exception as e:
            self.log_signal.emit(f"❌ 카페 조건 결과 처리 오류: {str(e)}")
    
    def closeEvent(self, event):
        """창 닫기 이벤트"""
        if self.app_state.is_running:
            reply = QMessageBox.question(
                self, '확인', 
                '작업이 진행 중입니다. 정말 종료하시겠습니까?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self._stop_work()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
    
    def _create_integrated_tab(self):
        """통합 엑셀 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 파일 선택 영역
        file_group = QGroupBox("📁 통합 엑셀 파일")
        file_layout = QHBoxLayout(file_group)
        
        self.integrated_file_path = QLineEdit()
        self.integrated_file_path.setPlaceholderText("통합 엑셀 파일을 선택하세요... (A:ID, B:PW, D:카페URL, E:작업게시판, F:목표게시판)")
        file_layout.addWidget(self.integrated_file_path)
        
        select_file_btn = QPushButton("📂 파일 선택")
        select_file_btn.clicked.connect(self._select_integrated_excel)
        file_layout.addWidget(select_file_btn)
        
        load_file_btn = QPushButton("📊 불러오기")
        load_file_btn.clicked.connect(self._load_integrated_excel)
        file_layout.addWidget(load_file_btn)
        
        layout.addWidget(file_group)
        
        # 시트별 탭 위젯
        self.sheet_tab_widget = QTabWidget()
        layout.addWidget(self.sheet_tab_widget)
        
        # 전체 제어 버튼 영역
        control_group = QGroupBox("🎮 전체 작업 제어")
        control_layout = QHBoxLayout(control_group)
        
        self.check_all_conditions_btn = QPushButton("🔍 모든 시트 등급조건 확인")
        self.check_all_conditions_btn.clicked.connect(self._check_all_sheet_conditions)
        self.check_all_conditions_btn.setEnabled(False)
        control_layout.addWidget(self.check_all_conditions_btn)
        
        self.start_all_work_btn = QPushButton("🚀 모든 시트 작업 시작")
        self.start_all_work_btn.clicked.connect(self._start_all_sheet_work)
        self.start_all_work_btn.setEnabled(False)
        control_layout.addWidget(self.start_all_work_btn)
        
        self.stop_work_btn = QPushButton("⏹️ 작업 중지")
        self.stop_work_btn.clicked.connect(self._stop_work)
        self.stop_work_btn.setEnabled(False)
        control_layout.addWidget(self.stop_work_btn)
        
        # 동시 실행 개수 설정
        concurrent_layout = QHBoxLayout()
        concurrent_layout.addWidget(QLabel("동시 실행 시트:"))
        
        self.concurrent_sheets_spin = QSpinBox()
        self.concurrent_sheets_spin.setRange(1, 5)
        self.concurrent_sheets_spin.setValue(2)  # 기본값 2개
        self.concurrent_sheets_spin.setSuffix("개")
        concurrent_layout.addWidget(self.concurrent_sheets_spin)
        
        concurrent_layout.addWidget(QLabel("(권장: 2개)"))
        concurrent_layout.addStretch()
        
        control_layout.addLayout(concurrent_layout)
        
        layout.addWidget(control_group)
        
        # 시트별 로그 탭 위젯 생성
        log_group = QGroupBox("📋 시트별 로그")
        log_layout = QVBoxLayout(log_group)
        
        self.sheet_log_tabs = QTabWidget()
        
        # 전체 요약 탭 (기본)
        self.summary_log = QTextEdit()
        self.summary_log.setMaximumHeight(150)
        self.summary_log.setReadOnly(True)
        self.sheet_log_tabs.addTab(self.summary_log, "📊 전체 요약")
        
        log_layout.addWidget(self.sheet_log_tabs)
        layout.addWidget(log_group)
        
        # 진행 상황 표시
        progress_group = QGroupBox("📊 진행 상황")
        progress_layout = QVBoxLayout(progress_group)
        
        self.current_sheet_label = QLabel("현재 시트: -")
        self.current_account_label = QLabel("현재 계정: -") 
        self.current_cafe_label = QLabel("현재 카페: -")
        self.integrated_progress_bar = QProgressBar()
        
        progress_layout.addWidget(self.current_sheet_label)
        progress_layout.addWidget(self.current_account_label)
        progress_layout.addWidget(self.current_cafe_label)
        progress_layout.addWidget(self.integrated_progress_bar)
        
        layout.addWidget(progress_group)
        
        # 탭에 추가
        self.tab_widget.addTab(tab, "📊 통합 엑셀")
        
        # 통합 데이터 저장
        self.integrated_data = {}
        self.sheet_tables = {}
    
    def _select_integrated_excel(self):
        """통합 엑셀 파일 선택"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "통합 엑셀 파일 선택", 
            "", 
            "Excel files (*.xlsx *.xls);;All files (*.*)"
        )
        if file_path:
            self.integrated_file_path.setText(file_path)
    
    def _load_integrated_excel(self):
        """통합 엑셀 파일 로드"""
        file_path = self.integrated_file_path.text().strip()
        if not file_path:
            QMessageBox.warning(self, "경고", "엑셀 파일을 선택해주세요.")
            return
        
        try:
            # 통합 데이터 로드
            self.integrated_data = self.data_handler.load_integrated_excel(file_path)
            
            # 기존 시트 탭들 제거
            self.sheet_tab_widget.clear()
            self.sheet_tables.clear()
            
            # 시트별 탭 생성
            for sheet_name, sheet_data in self.integrated_data.items():
                self._create_sheet_tab(sheet_name, sheet_data)
                self._create_sheet_log_tab(sheet_name)  # 시트별 로그 탭 생성
            
            # 버튼 활성화
            self.check_all_conditions_btn.setEnabled(True)
            
            # 로그 출력
            total_sheets = len(self.integrated_data)
            total_accounts = sum(len(data['accounts']) for data in self.integrated_data.values())
            total_cafes = sum(len(data['cafes']) for data in self.integrated_data.values())
            
            self.log_signal.emit(f"📊 통합 엑셀 로드 완료: {total_sheets}개 시트, {total_accounts}개 계정, {total_cafes}개 카페")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"엑셀 파일 로드 실패:\n{str(e)}")
            self.log_signal.emit(f"❌ 통합 엑셀 로드 실패: {str(e)}")
    
    def _create_sheet_tab(self, sheet_name: str, sheet_data: Dict):
        """시트별 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 시트 정보 표시
        info_label = QLabel(f"📋 {sheet_name}: {len(sheet_data['accounts'])}개 계정 × {len(sheet_data['cafes'])}개 카페")
        info_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #2c3e50; padding: 5px;")
        layout.addWidget(info_label)
        
        # 테이블 생성
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(["계정ID", "패스워드", "카페URL", "작업게시판", "목표게시판", "등급조건", "상태"])
        
        # 등급조건 컬럼만 편집 가능하게 설정
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # 기본적으로 편집 불가
        
        # 계정×카페 매트릭스로 행 생성
        rows = []
        for account in sheet_data['accounts']:
            for cafe in sheet_data['cafes']:
                rows.append([
                    account.id,
                    "●" * len(account.pw),  # 패스워드 마스킹
                    cafe.cafe_id,
                    cafe.work_board_id,
                    cafe.target_board_id,
                    "🔍 미확인",  # 등급조건 초기값
                    "⏳ 대기"    # 상태
                ])
        
        table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            for col_idx, cell_data in enumerate(row_data):
                item = QTableWidgetItem(str(cell_data))
                if col_idx in [5, 6]:  # 등급조건, 상태 컬럼
                    item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row_idx, col_idx, item)
        
        # 테이블 스타일링
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        # 더블클릭으로 등급조건 편집 기능
        table.cellDoubleClicked.connect(lambda row, col: self._on_cell_double_clicked(table, row, col, sheet_name))
        
        layout.addWidget(table)
        
        # 시트별 제어 버튼
        sheet_control_layout = QHBoxLayout()
        
        check_sheet_btn = QPushButton(f"🔍 {sheet_name} 등급조건 확인")
        check_sheet_btn.clicked.connect(lambda: self._check_sheet_conditions(sheet_name))
        sheet_control_layout.addWidget(check_sheet_btn)
        
        start_sheet_btn = QPushButton(f"🚀 {sheet_name} 작업 시작")
        start_sheet_btn.clicked.connect(lambda: self._start_sheet_work(sheet_name))
        start_sheet_btn.setEnabled(False)
        sheet_control_layout.addWidget(start_sheet_btn)
        
        layout.addLayout(sheet_control_layout)
        
        # 탭에 추가
        self.sheet_tab_widget.addTab(tab, sheet_name)
        
        # 시트별 테이블 참조 저장
        self.sheet_tables[sheet_name] = table
    
    def _check_all_sheet_conditions(self):
        """모든 시트의 등급조건 확인 (시트별 순차 실행)"""
        self.log_signal.emit("🔍 모든 시트 등급조건 확인을 시작합니다...")
        
        # 버튼 비활성화
        self.check_all_conditions_btn.setEnabled(False)
        self.start_all_work_btn.setEnabled(False)
        
        try:
            # 통합 엑셀 데이터 체크
            if not self.integrated_data:
                QMessageBox.warning(self, "경고", "통합 엑셀 파일을 먼저 불러와주세요.")
                self.check_all_conditions_btn.setEnabled(True)
                return
            
            # 시트별 순차 조회를 위한 큐 생성
            self.sheet_condition_queue = list(self.integrated_data.keys())
            self.current_sheet_checking = 0
            self.total_sheets_to_check = len(self.sheet_condition_queue)
            
            self.log_signal.emit(f"📊 조회 대상: {self.total_sheets_to_check}개 시트")
            
            # 첫 번째 시트부터 시작
            self._check_next_sheet_conditions()
            
        except Exception as e:
            self.log_signal.emit(f"❌ 등급조건 확인 시작 실패: {str(e)}")
            self.check_all_conditions_btn.setEnabled(True)
    
    def _check_next_sheet_conditions(self):
        """다음 시트 등급조건 확인"""
        if self.current_sheet_checking >= len(self.sheet_condition_queue):
            # 모든 시트 완료
            self._on_all_sheets_condition_finished()
            return
        
        sheet_name = self.sheet_condition_queue[self.current_sheet_checking]
        sheet_data = self.integrated_data[sheet_name]
        
        self.log_signal.emit(f"🔍 [{self.current_sheet_checking + 1}/{self.total_sheets_to_check}] {sheet_name} 시트 등급조건 확인 시작")
        
        # 시트별 테이블 상태 업데이트
        if sheet_name in self.sheet_tables:
            table = self.sheet_tables[sheet_name]
            for row in range(table.rowCount()):
                table.item(row, 5).setText("🔍 확인중...")  # 등급조건 컬럼
                table.item(row, 6).setText("🔍 조회중")    # 상태 컬럼
        
        try:
            # 시트별 첫 번째 계정과 해당 시트 카페들로 워커 생성
            representative_account = sheet_data['accounts'][0]
            sheet_cafes = sheet_data['cafes']
            
            from ..workers.levelup_worker import AllLevelupConditionWorker
            
            # 시트별 등급조건 확인 워커 생성
            self.current_condition_worker = AllLevelupConditionWorker(
                cafes=sheet_cafes,
                account=representative_account
            )
            
            # 시그널 연결
            self.current_condition_worker.log_signal.connect(self._append_log)
            self.current_condition_worker.table_signal.connect(self._on_sheet_condition_result)
            self.current_condition_worker.button_signal.connect(self._on_sheet_condition_finished)
            
            # 워커 시작
            self.current_condition_worker.start()
            
        except Exception as e:
            self.log_signal.emit(f"❌ {sheet_name} 시트 등급조건 확인 실패: {str(e)}")
            self.current_sheet_checking += 1
            QTimer.singleShot(1000, self._check_next_sheet_conditions)
        
    def _start_all_sheet_work(self):
        """모든 시트 작업 시작 (병렬 처리)"""
        self.log_signal.emit("🚀 모든 시트 병렬 작업을 시작합니다...")
        
        # 프록시 매니저 설정 (통합 엑셀용)
        proxy_list = self.proxy_widget.get_proxy_list()
        if proxy_list:
            from ..core.proxy_manager import ProxyManager
            self.proxy_manager = ProxyManager(proxy_list)
            self.log_signal.emit(f"🌐 프록시 매니저 초기화 완료: {len(proxy_list)}개 프록시")
        else:
            self.proxy_manager = None
            self.log_signal.emit("🌐 프록시 없이 직접 연결로 실행")
        
        # 작업 설정 생성 (기존 GUI 설정 사용)
        work_settings = {
            'comment_text': self.comment_text.toPlainText().strip() or "안녕하세요",
            'post_title': self.post_title.text().strip() or "안녕하세요",
            'post_content': self.post_text.toPlainText().strip() or "잘부탁드립니다",
            'add_random_numbers': self.comment_random_check.isChecked() or self.post_random_check.isChecked(),
            'delete_after_work': self.levelup_check.isChecked() or self.delete_check.isChecked(),
            'skip_if_visit_insufficient': self.check_condition_check.isChecked(),
            'headless_mode': self.headless_checkbox.isChecked(),
            'post_delay': self.post_delay_min.value(),
            'comment_delay': self.comment_delay_min.value(),
            'reply_start_page': self.reply_page.value()
        }
        
        self.log_signal.emit(f"🔧 작업 설정: 답글시작페이지={work_settings['reply_start_page']}, 댓글딜레이={work_settings['comment_delay']}초")
        
        try:
            # 시트별 병렬 워커 생성
            self.sheet_workers = {}
            self.completed_sheets = set()
            self.pending_sheets = []  # 대기 중인 시트들
            self.MAX_CONCURRENT_SHEETS = self.concurrent_sheets_spin.value()  # 사용자 설정값 사용
            
            # 프록시 분배 계산
            total_sheets = len([name for name, data in self.integrated_data.items() if data['conditions_cache']])
            sheet_index = 0
            
            for sheet_name, sheet_data in self.integrated_data.items():
                # 시트별 등급조건 확인 여부 체크
                conditions_cache = sheet_data['conditions_cache']
                if not conditions_cache:
                    self._log_to_sheet(sheet_name, "⚠️ 등급조건이 확인되지 않았습니다. 건너뜁니다.")
                    continue
                
                # 수동 수정된 조건들 필터링
                manual_conditions = {}
                if hasattr(self, 'manual_conditions'):
                    manual_conditions = {k: v for k, v in self.manual_conditions.items() if k.startswith(sheet_name + "_")}
                
                # 시트별 프록시 매니저 생성 (프록시 분배)
                sheet_proxy_manager = None
                if self.proxy_manager:
                    sheet_proxy_manager = self._create_sheet_proxy_manager(sheet_index, total_sheets)
                
                # 시트별 워커 생성
                from ..workers.levelup_worker import SheetLevelupWorker
                worker = SheetLevelupWorker(
                    sheet_name=sheet_name,
                    accounts=sheet_data['accounts'],
                    cafes=sheet_data['cafes'],
                    conditions_cache=conditions_cache,
                    manual_conditions=manual_conditions,
                    work_settings=work_settings,
                    proxy_manager=sheet_proxy_manager
                )
                
                sheet_index += 1
                
                # 시그널 연결
                worker.log_signal.connect(self._log_to_sheet)
                worker.progress_signal.connect(self._on_sheet_progress)
                worker.result_signal.connect(self._on_sheet_result)
                worker.work_result_signal.connect(self._on_work_result)  # WorkResult 처리
                worker.finished_signal.connect(self._on_sheet_finished)
                
                # 워커를 대기열에 추가 (시작하지 않음)
                self.pending_sheets.append((sheet_name, worker))
                self._log_to_sheet(sheet_name, f"📋 작업 대기열에 추가됨")
            
            # 제한된 개수만큼 시트 시작
            if self.pending_sheets:
                self.log_signal.emit(f"🔥 {len(self.pending_sheets)}개 시트 중 최대 {self.MAX_CONCURRENT_SHEETS}개씩 병렬 작업!")
                self._start_next_batch_sheets()
            else:
                self.log_signal.emit("⚠️ 작업 가능한 시트가 없습니다.")
                return
                
        except Exception as e:
            self.log_signal.emit(f"❌ 병렬 작업 시작 실패: {str(e)}")
            QMessageBox.critical(self, "오류", f"작업 시작 실패:\n{str(e)}")
    
    def _start_next_batch_sheets(self):
        """다음 배치 시트들 시작"""
        # 현재 실행 중인 시트 개수 확인
        running_count = len([w for w in self.sheet_workers.values() if w.isRunning()])
        available_slots = self.MAX_CONCURRENT_SHEETS - running_count
        
        # 사용 가능한 슬롯만큼 시트 시작
        sheets_to_start = min(available_slots, len(self.pending_sheets))
        
        for _ in range(sheets_to_start):
            if self.pending_sheets:
                sheet_name, worker = self.pending_sheets.pop(0)
                self.sheet_workers[sheet_name] = worker
                worker.start()
                self._log_to_sheet(sheet_name, "🚀 작업 시작!")
        
        # 상태 로그
        running_sheets = [name for name, w in self.sheet_workers.items() if w.isRunning()]
        pending_count = len(self.pending_sheets)
        
        self.log_signal.emit(f"📊 현재 상태: 실행중 {len(running_sheets)}개, 대기중 {pending_count}개")
        if running_sheets:
            self.log_signal.emit(f"🔥 실행중 시트: {', '.join(running_sheets)}")
    
    def _on_sheet_progress(self, sheet_name: str, current: int, total: int):
        """시트별 진행률 업데이트"""
        progress_percent = int((current / total) * 100) if total > 0 else 0
        self._log_to_sheet(sheet_name, f"📊 진행률: {current}/{total} ({progress_percent}%)")
    
    def _on_sheet_result(self, sheet_name: str, account_id: str, cafe_id: str, result: str):
        """시트별 작업 결과 처리"""
        status_emoji = "✅" if result == "성공" else "❌"
        self._log_to_sheet(sheet_name, f"{status_emoji} {account_id} - {cafe_id}: {result}")
    
    def _on_work_result(self, work_result):
        """WorkResult 객체를 앱 상태에 추가"""
        try:
            self.app_state.add_work_result(work_result)
            self.log_signal.emit(f"📊 작업 결과 저장: {work_result.account_id} - {work_result.cafe_name} (프록시: {work_result.used_proxy})")
        except Exception as e:
            self.log_signal.emit(f"❌ 작업 결과 저장 실패: {str(e)}")
    
    def _on_sheet_finished(self, sheet_name: str):
        """시트 작업 완료 처리"""
        self.completed_sheets.add(sheet_name)
        self._log_to_sheet(sheet_name, "🎉 시트 작업 완료!")
        
        # 워커 정리
        if sheet_name in self.sheet_workers:
            worker = self.sheet_workers[sheet_name]
            try:
                worker.quit()
                worker.wait(3000)  # 3초 대기
            except:
                pass
            del self.sheet_workers[sheet_name]
        
        # 대기 중인 시트가 있으면 다음 시트 시작
        if self.pending_sheets:
            self.log_signal.emit(f"🔄 {sheet_name} 완료 → 다음 시트 시작")
            self._start_next_batch_sheets()
        
        # 모든 시트 완료 확인 (실행중 + 대기중 모두 고려)
        total_sheets = len(self.completed_sheets) + len(self.sheet_workers) + len(self.pending_sheets)
        if len(self.completed_sheets) == total_sheets - len(self.pending_sheets) - len([w for w in self.sheet_workers.values() if w.isRunning()]):
            if not self.pending_sheets and not any(w.isRunning() for w in self.sheet_workers.values()):
                self.log_signal.emit("🎉 모든 시트 병렬 작업 완료!")
                self._finalize_all_sheet_work()
    
    def _finalize_all_sheet_work(self):
        """모든 시트 작업 완료 후 정리"""
        try:
            # 모든 워커 정리
            for worker in self.sheet_workers.values():
                try:
                    worker.quit()
                    worker.wait(1000)
                except:
                    pass
            
            self.sheet_workers.clear()
            
            # 버튼 상태 복원
            self.start_all_work_btn.setEnabled(True)
            self.stop_work_btn.setEnabled(False)
            
            # 완료 통계
            total_completed = len(self.completed_sheets)
            self.log_signal.emit(f"📊 최종 결과: {total_completed}개 시트 작업 완료")
            
        except Exception as e:
            self.log_signal.emit(f"❌ 작업 완료 처리 중 오류: {str(e)}")
    
    def _check_sheet_conditions(self, sheet_name: str):
        """특정 시트의 등급조건 확인"""
        self._log_to_sheet(sheet_name, f"🔍 등급조건 확인을 시작합니다...")
        # TODO: 구현 예정
        
    def _start_sheet_work(self, sheet_name: str):
        """특정 시트 작업 시작"""
        self._log_to_sheet(sheet_name, f"🚀 작업을 시작합니다...")
        # TODO: 구현 예정
    
    def _on_sheet_condition_result(self, cafe_id: str, conditions: Dict):
        """시트별 등급조건 확인 결과 처리"""
        try:
            current_sheet_name = self.sheet_condition_queue[self.current_sheet_checking]
            
            # 등급조건 캐시에 저장 (dict 형태로)
            self.integrated_data[current_sheet_name]['conditions_cache'][cafe_id] = conditions
            
            # 등급조건 텍스트 생성
            if conditions.get('failure_reason'):
                condition_text = "❌ 글쓰기조건"
                status_text = "❌ 실패"
                bg_color = QColor(255, 200, 200)
            else:
                # 조건 텍스트 생성
                posts = conditions.get('posts_required', 0)
                comments = conditions.get('comments_required', 0)
                visits = conditions.get('visits_required', 0)
                
                condition_parts = []
                if posts > 0:
                    condition_parts.append(f"게시글{posts}")
                if comments > 0:
                    condition_parts.append(f"댓글{comments}")
                if visits > 0:
                    condition_parts.append(f"방문{visits}")
                
                condition_text = "+".join(condition_parts) if condition_parts else "조건없음"
                status_text = "✅ 준비"
                bg_color = QColor(200, 255, 200)
            
            # 해당 시트 테이블 업데이트
            if current_sheet_name in self.sheet_tables:
                table = self.sheet_tables[current_sheet_name]
                
                for row in range(table.rowCount()):
                    cafe_item = table.item(row, 2)  # 카페URL 컬럼
                    if cafe_item and cafe_item.text() == cafe_id:
                        # 등급조건 컬럼 업데이트
                        condition_item = table.item(row, 5)
                        condition_item.setText(condition_text)
                        condition_item.setBackground(bg_color)
                        
                        # 상태 컬럼 업데이트
                        status_item = table.item(row, 6)
                        status_item.setText(status_text)
                        status_item.setBackground(bg_color)
            
            self.log_signal.emit(f"✅ {cafe_id} 등급조건: {condition_text}")
            
        except Exception as e:
            self.log_signal.emit(f"❌ 등급조건 결과 처리 실패: {str(e)}")
    
    def _on_sheet_condition_finished(self, button_name: str, enabled: bool, text: str):
        """시트별 등급조건 확인 완료 (button_signal 처리)"""
        current_sheet_name = self.sheet_condition_queue[self.current_sheet_checking]
        
        if "완료" in text:
            self.log_signal.emit(f"✅ {current_sheet_name} 시트 등급조건 확인 완료!")
        else:
            self.log_signal.emit(f"❌ {current_sheet_name} 시트 등급조건 확인 상태: {text}")
        
        # 다음 시트로 이동
        self.current_sheet_checking += 1
        QTimer.singleShot(2000, self._check_next_sheet_conditions)
    
    def _on_all_sheets_condition_finished(self):
        """모든 시트 등급조건 확인 완료"""
        self.log_signal.emit("🎉 모든 시트 등급조건 확인 완료!")
        
        # 성공한 카페 수 확인
        total_ready = 0
        total_failed = 0
        
        for sheet_data in self.integrated_data.values():
            for conditions in sheet_data['conditions_cache'].values():
                if conditions.get('failure_reason'):
                    total_failed += 1
                else:
                    total_ready += 1
        
        self.log_signal.emit(f"📊 결과: 작업 가능 {total_ready}개, 실패 {total_failed}개")
        
        # 작업 시작 버튼 활성화
        if total_ready > 0:
            self.start_all_work_btn.setEnabled(True)
        
        # 조회 버튼 재활성화
        self.check_all_conditions_btn.setEnabled(True)
    
    def _on_cell_double_clicked(self, table: QTableWidget, row: int, col: int, sheet_name: str):
        """테이블 셀 더블클릭 이벤트 핸들러"""
        # 등급조건 컬럼(5번)만 편집 가능
        if col != 5:
            return
        
        current_text = table.item(row, col).text()
        
        # 미확인 상태가 아닌 경우에만 편집 가능
        if "미확인" in current_text:
            QMessageBox.information(self, "편집 불가", "등급조건을 먼저 확인한 후 편집할 수 있습니다.")
            return
        
        # 입력 다이얼로그 표시
        new_condition, ok = QInputDialog.getText(
            self, 
            "등급조건 수정", 
            f"새로운 등급조건을 입력하세요:\n\n예시: 게시글2+댓글5, 댓글10, 게시글3\n\n현재 조건: {current_text}",
            text=current_text.replace("🔍 ", "").replace("✅ ", "").replace("❌ ", "").replace("✏️ ", "")
        )
        
        if ok and new_condition.strip():
            # 조건 형식 검증
            if self._validate_condition_format(new_condition.strip()):
                # 테이블 업데이트
                table.setItem(row, col, QTableWidgetItem(f"✏️ {new_condition.strip()}"))
                
                # 수정된 조건을 메모리에 저장
                account_id = table.item(row, 0).text()
                cafe_id = table.item(row, 2).text()
                key = f"{sheet_name}_{account_id}_{cafe_id}"
                
                if not hasattr(self, 'manual_conditions'):
                    self.manual_conditions = {}
                self.manual_conditions[key] = new_condition.strip()
                
                self.log_signal.emit(f"✏️ {sheet_name} - {account_id} - {cafe_id}: 등급조건 수정됨 → {new_condition.strip()}")
            else:
                QMessageBox.warning(self, "형식 오류", "올바른 등급조건 형식이 아닙니다.\n\n올바른 형식:\n- 게시글2+댓글5\n- 댓글10\n- 게시글3")
    
    def _validate_condition_format(self, condition: str) -> bool:
        """등급조건 형식 검증"""
        import re
        
        # 올바른 형식 패턴들
        patterns = [
            r'^게시글\d+$',                    # 게시글3
            r'^댓글\d+$',                     # 댓글10
            r'^게시글\d+\+댓글\d+$',          # 게시글2+댓글5
            r'^댓글\d+\+게시글\d+$',          # 댓글5+게시글2
        ]
        
        for pattern in patterns:
            if re.match(pattern, condition):
                return True
        return False
    
    def _parse_manual_condition(self, condition: str) -> tuple:
        """수동 입력된 조건을 파싱해서 게시글/댓글 수 반환"""
        import re
        
        posts_required = 0
        comments_required = 0
        
        # 게시글 수 추출
        post_match = re.search(r'게시글(\d+)', condition)
        if post_match:
            posts_required = int(post_match.group(1))
        
        # 댓글 수 추출  
        comment_match = re.search(r'댓글(\d+)', condition)
        if comment_match:
            comments_required = int(comment_match.group(1))
        
        return posts_required, comments_required
    
    def _create_sheet_log_tab(self, sheet_name: str):
        """시트별 로그 탭 생성"""
        log_widget = QTextEdit()
        log_widget.setReadOnly(True)
        log_widget.setMaximumHeight(150)
        
        # 시트별 로그 저장을 위한 딕셔너리 초기화
        if not hasattr(self, 'sheet_logs'):
            self.sheet_logs = {}
        
        self.sheet_logs[sheet_name] = log_widget
        
        # 로그 탭에 추가
        tab_title = f"📋 {sheet_name}"
        self.sheet_log_tabs.addTab(log_widget, tab_title)
        
        # 초기 로그 메시지
        log_widget.append(f"🔄 {sheet_name} 시트 로그 시작...")
    
    def _log_to_sheet(self, sheet_name: str, message: str):
        """특정 시트에 로그 메시지 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # 시트별 로그에 추가
        if hasattr(self, 'sheet_logs') and sheet_name in self.sheet_logs:
            self.sheet_logs[sheet_name].append(formatted_message)
        
        # 전체 요약 로그에도 추가 (시트 태그와 함께)
        self.summary_log.append(f"[{sheet_name}] {formatted_message}")
        
        # 기존 메인 로그에도 추가 (호환성)
        self.log_signal.emit(f"[{sheet_name}] {message}")
    
    def _create_sheet_proxy_manager(self, sheet_index: int, total_sheets: int):
        """시트별로 프록시를 분배한 ProxyManager 생성"""
        try:
            from ..core.proxy_manager import ProxyManager
            
            # 전체 프록시 리스트 가져오기
            all_proxies = self.proxy_widget.get_proxy_list()
            if not all_proxies:
                return None
            
            # 시트별로 프록시 분배
            proxies_per_sheet = len(all_proxies) // total_sheets
            start_idx = sheet_index * proxies_per_sheet
            
            # 마지막 시트는 남은 프록시 모두 할당
            if sheet_index == total_sheets - 1:
                end_idx = len(all_proxies)
            else:
                end_idx = start_idx + proxies_per_sheet
            
            # 시트별 프록시 리스트
            sheet_proxies = all_proxies[start_idx:end_idx]
            
            if sheet_proxies:
                sheet_proxy_manager = ProxyManager(sheet_proxies)
                self.log_signal.emit(f"🌐 시트{sheet_index + 1} 프록시 할당: {len(sheet_proxies)}개 ({start_idx}-{end_idx-1})")
                return sheet_proxy_manager
            else:
                self.log_signal.emit(f"⚠️ 시트{sheet_index + 1} 프록시 부족 - 직접 연결 사용")
                return None
                
        except Exception as e:
            self.log_signal.emit(f"❌ 시트{sheet_index + 1} 프록시 매니저 생성 실패: {str(e)}")
            return None
