"""
데이터 처리 모듈
엑셀 파일 읽기/쓰기, 설정 저장/로드 등을 담당합니다.
"""

import os
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

from .models import Account, CafeInfo, WorkResult, AppState


class DataHandler:
    """데이터 처리 클래스"""
    
    def __init__(self, config_dir: str):
        """
        데이터 핸들러 초기화
        
        Args:
            config_dir: 설정 파일 디렉토리
        """
        self.config_dir = config_dir
        os.makedirs(config_dir, exist_ok=True)
    
    def load_accounts_from_excel(self, file_path: str) -> List[Account]:
        """
        엑셀 파일에서 계정 목록을 로드합니다.
        
        Args:
            file_path: 엑셀 파일 경로
            
        Returns:
            계정 목록
        """
        try:
            df = pd.read_excel(file_path, header=None)
            accounts = []
            
            for idx, row in df.iterrows():
                account_id = str(row[0]).strip()
                password = str(row[1]).strip()
                accounts.append(Account(id=account_id, pw=password))
                
            return accounts
        except Exception as e:
            raise Exception(f"계정 파일 읽기 실패: {str(e)}")
    
    def load_cafes_from_excel(self, file_path: str) -> List[CafeInfo]:
        """
        엑셀 파일에서 카페 목록을 로드합니다.
        
        Args:
            file_path: 엑셀 파일 경로
            
        Returns:
            카페 목록
        """
        try:
            df = pd.read_excel(file_path, header=None)
            cafes = []
            
            for idx, row in df.iterrows():
                cafe_url = str(row[0]).strip() if pd.notna(row[0]) else ""
                work_board_id = str(row[1]).strip() if pd.notna(row[1]) else ""
                target_board_id = str(row[2]).strip() if pd.notna(row[2]) else ""
                
                # 카페 ID 추출
                cafe_id = self._extract_cafe_id(cafe_url)
                
                cafes.append(CafeInfo(
                    url=cafe_url,
                    cafe_id=cafe_id,
                    work_board_id=work_board_id,
                    target_board_id=target_board_id
                ))
                
            return cafes
        except Exception as e:
            raise Exception(f"카페 설정 파일 읽기 실패: {str(e)}")
    
    def _extract_cafe_id(self, raw_id: str) -> str:
        """카페 ID 추출"""
        if not raw_id:
            return ""
            
        if "cafe.naver.com/" in raw_id:
            import re
            match = re.search(r'cafe\.naver\.com/([^/?]+)', raw_id)
            if match:
                return match.group(1)
        
        return raw_id.strip()
    
    def export_results_to_excel(self, app_state: AppState, file_path: str) -> None:
        """
        작업 결과를 엑셀 파일로 내보냅니다.
        
        Args:
            app_state: 애플리케이션 상태
            file_path: 저장할 엑셀 파일 경로
        """
        try:
            # 안전한 pandas 방식으로 저장 (수식 오류 방지)
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                
                # 1. 작업 결과 시트
                if app_state.work_results:
                    data = [result.to_dict() for result in app_state.work_results]
                    df_results = pd.DataFrame(data)
                    # 수식 방지: 모든 데이터를 문자열로 변환
                    df_results = df_results.astype(str)
                    df_results.to_excel(writer, sheet_name="작업결과", index=False)
                
                # 2. 계정 목록 시트
                if app_state.accounts:
                    accounts_data = [{'계정ID': acc.id, '상태': '로드됨'} for acc in app_state.accounts]
                    df_accounts = pd.DataFrame(accounts_data)
                    df_accounts.to_excel(writer, sheet_name="계정목록", index=False)
                
                # 3. 카페 목록 시트
                if app_state.cafes:
                    cafes_data = [{'카페ID': cafe.cafe_id, '카페URL': cafe.url, '작업게시판': str(cafe.work_board_id), '목표게시판': str(cafe.target_board_id)} for cafe in app_state.cafes]
                    df_cafes = pd.DataFrame(cafes_data)
                    df_cafes.to_excel(writer, sheet_name="카페목록", index=False)
                
                # 4. 통계 시트 (수식 없이 순수 데이터만)
                stats = app_state.get_work_statistics()
                stats_data = []
                stats_data.append(['항목', '값'])
                stats_data.append(['총 계정 수', str(stats['total_accounts'])])
                stats_data.append(['총 카페 수', str(stats['total_cafes'])])
                stats_data.append(['총 작업 수', str(stats['total_works'])])
                
                if stats['elapsed_time']:
                    stats_data.append(['작업 시간', str(stats['elapsed_time']).split('.')[0]])
                
                # 결과별 통계 (퍼센트 계산을 미리 해서 문자열로 저장)
                if stats['result_counts']:
                    stats_data.append(['', ''])
                    stats_data.append(['결과', '개수', '비율'])
                    for status, count in stats['result_counts'].items():
                        percentage = (count / stats['total_works'] * 100) if stats['total_works'] > 0 else 0
                        stats_data.append([str(status), str(count), f"{percentage:.1f}%"])
                
                df_stats = pd.DataFrame(stats_data)
                df_stats.to_excel(writer, sheet_name="통계", index=False, header=False)
            
        except Exception as e:
            raise Exception(f"엑셀 파일 생성 실패: {str(e)}")
    
    # 새로운 안전한 pandas 방식으로 엑셀 저장 (수식 오류 방지)
    
    def save_settings(self, app_state: AppState) -> None:
        """애플리케이션 설정 저장"""
        try:
            settings = {
                'accounts': [{'id': acc.id, 'pw': acc.pw} for acc in app_state.accounts],
                'cafes': [
                    {
                        'url': cafe.url,
                        'cafe_id': cafe.cafe_id,
                        'work_board_id': cafe.work_board_id,
                        'target_board_id': cafe.target_board_id
                    } for cafe in app_state.cafes
                ],
                'last_saved': datetime.now().isoformat()
            }
            
            settings_file = os.path.join(self.config_dir, 'app_settings.json')
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            raise Exception(f"설정 저장 실패: {str(e)}")
    
    def load_settings(self) -> Optional[Dict[str, Any]]:
        """애플리케이션 설정 로드"""
        try:
            settings_file = os.path.join(self.config_dir, 'app_settings.json')
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            raise Exception(f"설정 로드 실패: {str(e)}")
    
    def load_proxy_file(self, file_path: str) -> List[str]:
        """프록시 파일 로드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 빈 줄과 주석 제거
            proxy_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    proxy_lines.append(line)
            
            return proxy_lines
        except Exception as e:
            raise Exception(f"프록시 파일 로드 실패: {str(e)}")
    
    def load_integrated_excel(self, file_path: str) -> Dict[str, Dict]:
        """
        통합 엑셀 파일에서 시트별 계정+카페 데이터를 로드합니다.
        
        Args:
            file_path: 통합 엑셀 파일 경로
            
        Returns:
            시트별 데이터 딕셔너리 {sheet_name: {accounts: [...], cafes: [...], conditions_cache: {}}}
        """
        try:
            # 모든 시트 이름 가져오기
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            integrated_data = {}
            
            for sheet_name in sheet_names:
                # 시트별 데이터 로드 (1행 무시)
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=None, skiprows=1)
                
                accounts = []
                cafes = []
                
                for idx, row in df.iterrows():
                    # A,B열: 계정 정보
                    if pd.notna(row[0]) and pd.notna(row[1]):
                        account_id = str(row[0]).strip()
                        password = str(row[1]).strip()
                        if account_id and password:
                            accounts.append(Account(id=account_id, pw=password))
                    
                    # D,E,F열: 카페 정보 (C열은 건너뛰기)
                    if len(row) > 5 and pd.notna(row[3]) and pd.notna(row[4]) and pd.notna(row[5]):
                        cafe_url = str(row[3]).strip()
                        # 게시판 ID는 float에서 int로 변환 후 문자열로 (.0 제거)
                        work_board_id = str(int(float(row[4]))).strip()
                        target_board_id = str(int(float(row[5]))).strip()
                        
                        if cafe_url and work_board_id and target_board_id:
                            cafe_id = self._extract_cafe_id(cafe_url)
                            cafes.append(CafeInfo(
                                url=cafe_url,
                                cafe_id=cafe_id,
                                work_board_id=work_board_id,
                                target_board_id=target_board_id
                            ))
                
                # 중복 제거
                accounts = list({acc.id: acc for acc in accounts}.values())
                cafes = list({cafe.cafe_id: cafe for cafe in cafes}.values())
                
                integrated_data[sheet_name] = {
                    "accounts": accounts,
                    "cafes": cafes,
                    "conditions_cache": {}  # 등급조건 캐시
                }
                
            return integrated_data
            
        except Exception as e:
            raise Exception(f"통합 엑셀 파일 읽기 실패: {str(e)}")
