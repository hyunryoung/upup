#!/usr/bin/env python3
"""
클라이언트용 인증 모듈
프로그램 실행 시 하드웨어 ID를 확인하고 라이선스를 검증합니다.
"""

import os
from typing import Tuple
from .hardware_auth import HardwareAuthenticator
from .license_db import LicenseDB


class ClientAuthenticator:
    """클라이언트 인증 클래스"""
    
    def __init__(self):
        self.hardware_auth = HardwareAuthenticator()
        self.license_db = LicenseDB()
    
    def check_license(self) -> Tuple[bool, str]:
        """라이선스 확인
        
        Returns:
            (bool, str): (인증 성공 여부, 메시지)
        """
        try:
            # 하드웨어 ID 가져오기
            hardware_id = self.hardware_auth.get_hardware_id()
            if not hardware_id:
                return False, "하드웨어 ID를 생성할 수 없습니다."
            
            # 라이선스 확인
            if not self.license_db.is_licensed(hardware_id):
                return False, f"라이선스가 없습니다.\n\n하드웨어 ID: {hardware_id}\n\n관리자에게 이 하드웨어 ID를 전달하여 라이선스를 발급받으세요."
            
            return True, "라이선스가 유효합니다."
            
        except Exception as e:
            return False, f"라이선스 확인 중 오류가 발생했습니다: {str(e)}"
