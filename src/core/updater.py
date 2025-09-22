import os
import sys
import json
import requests
import logging
import tempfile
import subprocess
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal

class Updater(QObject):
    update_available = pyqtSignal(str)  # 새 버전 정보를 전달하는 시그널
    update_progress = pyqtSignal(int)   # 업데이트 진행률을 전달하는 시그널
    update_completed = pyqtSignal()     # 업데이트 완료를 알리는 시그널
    update_error = pyqtSignal(str)      # 업데이트 오류를 전달하는 시그널

    def __init__(self, current_version, github_repo):
        super().__init__()
        self.current_version = current_version
        self.github_repo = github_repo
        self.logger = logging.getLogger(__name__)
        
    def check_for_updates(self):
        """GitHub에서 최신 버전 확인"""
        try:
            # GitHub API를 통해 최신 릴리즈 정보 가져오기
            api_url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
            response = requests.get(api_url)
            response.raise_for_status()
            
            release_info = response.json()
            latest_version = release_info['tag_name']
            
            if latest_version > self.current_version:
                self.logger.info(f"새로운 버전 발견: v{self.current_version} → v{latest_version}")
                self.update_available.emit(latest_version)
                return True, release_info
            
            return False, None
            
        except Exception as e:
            self.logger.error(f"업데이트 확인 중 오류 발생: {e}")
            self.update_error.emit(str(e))
            return False, None

    def download_update(self, release_info):
        """업데이트 파일 다운로드"""
        try:
            # exe 파일 찾기
            exe_asset = None
            for asset in release_info['assets']:
                if asset['name'].endswith('.exe'):
                    exe_asset = asset
                    break
            
            if not exe_asset:
                raise Exception("업데이트 파일을 찾을 수 없습니다.")
            
            # 임시 디렉토리에 다운로드
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, exe_asset['name'])
            
            response = requests.get(exe_asset['browser_download_url'], stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            with open(temp_file, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    downloaded = 0
                    for data in response.iter_content(chunk_size=4096):
                        downloaded += len(data)
                        f.write(data)
                        progress = int((downloaded / total_size) * 100)
                        self.update_progress.emit(progress)
            
            return temp_file
            
        except Exception as e:
            self.logger.error(f"업데이트 다운로드 중 오류 발생: {e}")
            self.update_error.emit(str(e))
            return None

    def install_update(self, update_file):
        """업데이트 설치"""
        try:
            # 현재 실행 파일의 경로
            current_exe = sys.executable
            
            # 업데이트 배치 스크립트 생성
            batch_file = os.path.join(tempfile.gettempdir(), 'update.bat')
            with open(batch_file, 'w') as f:
                f.write('@echo off\n')
                f.write('timeout /t 2 /nobreak > nul\n')  # 현재 프로세스가 종료되기를 기다림
                f.write(f'move /y "{update_file}" "{current_exe}"\n')
                f.write(f'start "" "{current_exe}"\n')
                f.write('del "%~f0"\n')  # 배치 파일 자체 삭제
            
            # 배치 파일 실행
            subprocess.Popen(['cmd', '/c', batch_file], 
                           creationflags=subprocess.CREATE_NO_WINDOW,
                           close_fds=True)
            
            self.update_completed.emit()
            return True
            
        except Exception as e:
            self.logger.error(f"업데이트 설치 중 오류 발생: {e}")
            self.update_error.emit(str(e))
            return False

    def perform_update(self):
        """업데이트 프로세스 실행"""
        success, release_info = self.check_for_updates()
        if not success:
            return
            
        # 사용자에게 업데이트 여부 확인
        reply = QMessageBox.question(
            None,
            "업데이트 확인",
            f"새로운 버전이 있습니다!\n\n"
            f"현재 버전: v{self.current_version}\n"
            f"새 버전: v{release_info['tag_name']}\n\n"
            f"지금 업데이트하시겠습니까?\n\n"
            f"변경사항:\n{release_info['body']}",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        # 업데이트 파일 다운로드
        update_file = self.download_update(release_info)
        if not update_file:
            return
            
        # 현재 프로그램 종료 후 업데이트 설치
        reply = QMessageBox.information(
            None,
            "업데이트 준비 완료",
            "업데이트가 다운로드되었습니다.\n"
            "프로그램을 종료하고 업데이트를 설치하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.install_update(update_file)
            sys.exit(0)  # 프로그램 종료
