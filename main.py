#!/usr/bin/env python3
"""
네이버 카페 자동 등업 프로그램 (리팩토링 버전)
메인 실행 파일

사용법:
    python main.py

요구사항:
    - Python 3.7+
    - PyQt5
    - Selenium
    - pandas
    - openpyxl
    - requests
    - webdriver-manager
"""

import sys
import os
import logging
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.ui.main_window import MainWindow
from src.core.config import config
from src.ui.license_dialog import LicenseDialog
from src.core.updater import Updater


def setup_application():
    """애플리케이션 기본 설정"""
    # Qt 애플리케이션 생성
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 기본 폰트 설정
    font = QFont()
    font.setFamily(config.ui.font_family)
    font.setPointSize(config.ui.font_size)
    app.setFont(font)
    
    # 애플리케이션 정보 설정
    app.setApplicationName("네이버 카페 자동 등업 프로그램")
    app.setApplicationVersion("2025-09-12")
    app.setOrganizationName("CafeLevelUp")
    
    return app


def check_dependencies():
    """필수 의존성 확인"""
    missing_modules = []
    
    try:
        import PyQt5
    except ImportError:
        missing_modules.append("PyQt5")
    
    try:
        import selenium
    except ImportError:
        missing_modules.append("selenium")
    
    try:
        import pandas
    except ImportError:
        missing_modules.append("pandas")
    
    try:
        import openpyxl
    except ImportError:
        missing_modules.append("openpyxl")
    
    try:
        import requests
    except ImportError:
        missing_modules.append("requests")
    
    try:
        import webdriver_manager
    except ImportError:
        missing_modules.append("webdriver-manager")
    
    if missing_modules:
        error_msg = f"다음 모듈들이 설치되지 않았습니다:\n{', '.join(missing_modules)}\n\n"
        error_msg += "다음 명령어로 설치해주세요:\n"
        error_msg += f"pip install {' '.join(missing_modules)}"
        
        print(error_msg)
        
        # GUI가 가능하면 메시지박스로 표시
        try:
            app = QApplication([])
            QMessageBox.critical(None, "의존성 오류", error_msg)
        except:
            pass
        
        return False
    
    return True


def setup_logging():
    """로깅 시스템 설정"""
    try:
        # 로그 디렉토리 생성
        os.makedirs(config.logs_dir, exist_ok=True)
        
        # 로깅 설정
        logging.basicConfig(
            level=getattr(logging, config.logging.log_level),
            format=config.logging.log_format,
            handlers=[
                logging.FileHandler(config.get_log_file_path(), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        logger = logging.getLogger(__name__)
        logger.info("=" * 50)
        logger.info("네이버 카페 자동 등업 프로그램 시작")
        logger.info(f"버전: 2025-05-05 (리팩토링 버전)")
        logger.info(f"Python 버전: {sys.version}")
        logger.info(f"작업 디렉토리: {os.getcwd()}")
        logger.info("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"로깅 설정 실패: {str(e)}")
        return False


def main():
    """메인 함수"""
    try:
        # 의존성 확인
        if not check_dependencies():
            return 1
        
        # 로깅 설정
        if not setup_logging():
            return 1
        
        # 애플리케이션 설정
        app = setup_application()
        
        # 라이선스 체크
        from src.security.client_auth import ClientAuthenticator
        auth = ClientAuthenticator()
        success, message = auth.check_license()
        if not success:
            QMessageBox.critical(None, "라이선스 오류", message)
            return 1
            
        # 업데이트 체크
        updater = Updater(app.applicationVersion(), "cafe-levelup/cafe-levelup-app")
        updater.check_for_updates()
        
        # 메인 윈도우 생성 및 표시
        try:
            window = MainWindow()
            window.show()
            
            # 시작 메시지
            logger = logging.getLogger(__name__)
            logger.info("메인 윈도우 표시 완료")
            
            # 애플리케이션 실행
            return app.exec_()
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"메인 윈도우 생성/표시 실패: {str(e)}")
            
            QMessageBox.critical(
                None, 
                "시작 오류", 
                f"프로그램을 시작할 수 없습니다:\n{str(e)}\n\n"
                f"로그 파일을 확인해주세요: {config.get_log_file_path()}"
            )
            return 1
            
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
        return 0
        
    except Exception as e:
        print(f"예상치 못한 오류가 발생했습니다: {str(e)}")
        
        # 로그 파일에 기록 시도
        try:
            logger = logging.getLogger(__name__)
            logger.error(f"예상치 못한 오류: {str(e)}", exc_info=True)
        except:
            pass
        
        return 1


if __name__ == '__main__':
    # 고해상도 디스플레이 지원
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # 프로그램 실행
    exit_code = main()
    sys.exit(exit_code)
