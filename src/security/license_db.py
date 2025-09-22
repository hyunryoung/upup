#!/usr/bin/env python3
"""
라이선스 데이터베이스 관리 모듈
등록된 PC 정보를 JSON 파일로 관리합니다.
"""

import os
import sys
import json
from datetime import datetime
from typing import Optional, Dict, List


class LicenseDB:
    """라이선스 데이터베이스 클래스"""
    
    def __init__(self):
        # 실행 파일 또는 스크립트의 위치를 기준으로 경로 설정
        if getattr(sys, 'frozen', False):
            # exe로 실행할 때
            base_path = os.path.dirname(sys.executable)
        else:
            # 스크립트로 실행할 때
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        self.db_file = os.path.join(base_path, 'license.db')
        self._ensure_db()
    
    def _ensure_db(self):
        """DB 파일이 없으면 생성"""
        if not os.path.exists(self.db_file):
            os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
            self._save_db({'pcs': []})
    
    def _load_db(self) -> Dict:
        """DB 파일 로드"""
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {'pcs': []}
    
    def _save_db(self, data: Dict):
        """DB 파일 저장"""
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_pc(self, hardware_id: str, user_name: str = "", notes: str = "") -> bool:
        """새로운 PC 추가"""
        try:
            db = self._load_db()
            
            # 이미 존재하는지 확인
            if any(pc['hardware_id'] == hardware_id for pc in db['pcs']):
                return False
            
            # 새 PC 정보 추가
            pc_info = {
                'hardware_id': hardware_id,
                'user_name': user_name,
                'notes': notes,
                'status': 'active',
                'added_date': datetime.now().isoformat()
            }
            
            db['pcs'].append(pc_info)
            self._save_db(db)
            
            return True
            
        except Exception as e:
            print(f"PC 추가 중 오류 발생: {e}")
            return False
    
    def remove_pc(self, hardware_id: str) -> bool:
        """PC 제거"""
        try:
            db = self._load_db()
            
            # PC 찾아서 제거
            db['pcs'] = [pc for pc in db['pcs'] if pc['hardware_id'] != hardware_id]
            self._save_db(db)
            
            return True
            
        except Exception as e:
            print(f"PC 제거 중 오류 발생: {e}")
            return False
    
    def get_pc(self, hardware_id: str) -> Optional[Dict]:
        """특정 PC 정보 조회"""
        try:
            db = self._load_db()
            
            # PC 찾기
            for pc in db['pcs']:
                if pc['hardware_id'] == hardware_id:
                    return pc
            
            return None
            
        except Exception as e:
            print(f"PC 조회 중 오류 발생: {e}")
            return None
    
    def get_all_pcs(self) -> List[Dict]:
        """모든 PC 목록 조회"""
        try:
            db = self._load_db()
            return db['pcs']
        except Exception as e:
            print(f"PC 목록 조회 중 오류 발생: {e}")
            return []
    
    def update_pc_status(self, hardware_id: str, status: str) -> bool:
        """PC 상태 업데이트"""
        try:
            db = self._load_db()
            
            # PC 찾아서 상태 업데이트
            for pc in db['pcs']:
                if pc['hardware_id'] == hardware_id:
                    pc['status'] = status
                    self._save_db(db)
                    return True
            
            return False
            
        except Exception as e:
            print(f"PC 상태 업데이트 중 오류 발생: {e}")
            return False
    
    def is_licensed(self, hardware_id: str) -> bool:
        """라이선스 유효성 확인"""
        pc = self.get_pc(hardware_id)
        return pc is not None and pc['status'] == 'active'
