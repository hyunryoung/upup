#!/usr/bin/env python3
"""
하드웨어 ID 생성 및 인증 모듈
PC의 하드웨어 정보를 기반으로 고유 ID를 생성하고 인증하는 기능을 제공합니다.
"""

import os
import sys
import platform
import uuid
import hashlib
import subprocess
import json
from typing import Optional, Dict


class HardwareAuthenticator:
    """하드웨어 인증 클래스"""
    
    def __init__(self):
        # 실행 파일 또는 스크립트의 위치를 기준으로 경로 설정
        if getattr(sys, 'frozen', False):
            # exe로 실행할 때
            base_path = os.path.dirname(sys.executable)
        else:
            # 스크립트로 실행할 때
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        self.cache_file = os.path.join(base_path, 'hardware_id.cache')
    
    def get_hardware_id(self) -> str:
        """하드웨어 ID 생성 또는 캐시에서 로드"""
        # 캐시된 ID가 있으면 반환
        cached_id = self._load_cached_id()
        if cached_id:
            return cached_id
        
        # 새로운 하드웨어 ID 생성
        hardware_id = self._generate_hardware_id()
        
        # 캐시에 저장
        self._save_cached_id(hardware_id)
        
        return hardware_id
    
    def _generate_hardware_id(self) -> str:
        """하드웨어 정보를 기반으로 고유 ID 생성"""
        try:
            # 시스템 정보 수집
            system_info = platform.system() + platform.version()
            machine_id = str(uuid.getnode())  # MAC 주소 기반
            
            # Windows의 경우 추가 정보 수집
            if platform.system() == 'Windows':
                try:
                    # CPU 정보
                    cpu_info = subprocess.check_output('wmic cpu get processorid').decode()
                    cpu_id = cpu_info.split('\n')[1].strip()
                except:
                    cpu_id = platform.processor()
                
                try:
                    # BIOS 정보
                    bios_info = subprocess.check_output('wmic bios get serialnumber').decode()
                    bios_id = bios_info.split('\n')[1].strip()
                except:
                    bios_id = str(uuid.uuid4())
            else:
                cpu_id = platform.processor()
                bios_id = str(uuid.uuid4())
            
            # 하드웨어 정보 조합
            hardware_str = f"{system_info}{machine_id}{cpu_id}{bios_id}"
            
            # SHA-256 해시 생성
            hardware_hash = hashlib.sha256(hardware_str.encode()).hexdigest()
            
            # 16자리로 축약 (앞 16자리 사용)
            return hardware_hash[:16].upper()
            
        except Exception as e:
            print(f"하드웨어 ID 생성 중 오류 발생: {e}")
            return None
    
    def _load_cached_id(self) -> Optional[str]:
        """캐시된 하드웨어 ID 로드"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    return data.get('hardware_id')
        except:
            pass
        return None
    
    def _save_cached_id(self, hardware_id: str):
        """하드웨어 ID를 캐시에 저장"""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump({'hardware_id': hardware_id}, f)
        except:
            pass
    
    def validate_hardware_id(self, hardware_id: str) -> bool:
        """하드웨어 ID 유효성 검사"""
        if not hardware_id:
            return False
        
        # 16자리 영문/숫자 확인
        if len(hardware_id) != 16:
            return False
        
        if not hardware_id.isalnum():
            return False
        
        return True
