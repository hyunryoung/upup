"""
설정 관리 모듈
애플리케이션의 모든 설정과 상수를 관리합니다.
"""

import os
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class WebDriverConfig:
    """웹 드라이버 설정"""
    user_agent: str = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    implicit_wait: int = 10
    page_load_timeout: int = 30
    script_timeout: int = 30


@dataclass
class AutomationConfig:
    """자동화 설정"""
    post_delay_min: int = 10000  # 게시글 작성 딜레이 (ms)
    comment_delay_min: int = 3000  # 댓글 작성 딜레이 (ms)
    post_count_threshold: int = 2  # 작성 실패 최수 기준
    reply_start_page: int = 1  # 답색 시작 페이지
    max_retry_count: int = 3  # 최대 재시도 횟수
    
    # 제한 수
    comment_limit_default: int = 500
    post_limit_default: int = 50


@dataclass
class UIConfig:
    """UI 설정"""
    window_title: str = '네이버 카페 자동 등업 프로그램 [2025-05-05]'
    window_width: int = 1200
    window_height: int = 800
    font_family: str = "맑은 고딕"
    font_size: int = 9


@dataclass
class LoggingConfig:
    """로깅 설정"""
    log_file: str = 'cafe_levelup.log'
    log_format: str = '%(asctime)s - %(levelname)s - %(message)s'
    log_level: str = 'INFO'


class AppConfig:
    """애플리케이션 전체 설정 관리 클래스"""
    
    def __init__(self):
        self.webdriver = WebDriverConfig()
        self.automation = AutomationConfig()
        self.ui = UIConfig()
        self.logging = LoggingConfig()
        
        # 파일 경로
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_dir = os.path.join(self.base_dir, 'config')
        self.logs_dir = os.path.join(self.base_dir, 'logs')
        
        # 디렉토리 생성
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
    
    def get_log_file_path(self) -> str:
        """로그 파일 전체 경로 반환"""
        return os.path.join(self.logs_dir, self.logging.log_file)
    
    def get_config_file_path(self, filename: str) -> str:
        """설정 파일 전체 경로 반환"""
        return os.path.join(self.config_dir, filename)


# CSS 스타일 상수
MAIN_WINDOW_STYLE = """
    QMainWindow {
        background-color: #f0f0f0;
    }
    QGroupBox {
        font-weight: bold;
        border: 2px solid #cccccc;
        border-radius: 5px;
        margin-top: 10px;
        padding-top: 10px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
    }
    QPushButton {
        padding: 5px 15px;
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 3px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #45a049;
    }
    QPushButton:pressed {
        background-color: #357a38;
    }
    QPushButton:disabled {
        background-color: #cccccc;
        color: #666666;
    }
    QPushButton[text*="❌"], QPushButton[text*="🗑️"] {
        background-color: #dc3545;
        color: white;
    }
    QPushButton[text*="❌"]:hover, QPushButton[text*="🗑️"]:hover {
        background-color: #c82333;
    }
    QPushButton[text*="❌"]:pressed, QPushButton[text*="🗑️"]:pressed {
        background-color: #bd2130;
    }
    QLineEdit, QTextEdit {
        border: 1px solid #cccccc;
        border-radius: 3px;
        padding: 5px;
    }
    QTableWidget {
        border: 1px solid #cccccc;
        background-color: white;
    }
"""

# 네이버 카페 관련 상수
NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
NAVER_SEARCH_TEST_URL = "https://search.naver.com/search.naver?query=test"

# 웹 요소 선택자
SELECTORS = {
    'login': {
        'id_input': '#id',
        'pw_input': '#pw', 
        'login_button': '#log\\.login, .btn_login, .btn_global, button[type="submit"]',
        'login_form': '#frmNIDLogin, .login_wrap, .login_form'
    },
    'cafe': {
        'main_iframe': 'iframe[name="cafe_main"]',
        'author_buttons': 'button.nick_btn',
        'pagination': 'div.Pagination',
        'page_buttons': 'button.btn.number'
    },
    'my_activity': {
        'my_activity_button': "//button[contains(text(), '나의활동')]",
        'my_posts_link': "//a[contains(text(), '내가쓴 게시글')]",
        'my_comments_link': "//a[contains(text(), '내가 쓴 댓글')]"
    }
}

# 전역 설정 인스턴스
config = AppConfig()
