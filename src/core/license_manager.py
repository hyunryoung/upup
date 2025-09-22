import hashlib
import json
import os
import platform
import uuid
import platform
import uuid
import subprocess
from cryptography.fernet import Fernet
from datetime import datetime

class LicenseManager:
    def __init__(self):
        self.key = b'YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY='  # 32바이트 base64 인코딩된 키
        self.cipher_suite = Fernet(self.key)
        self.license_file = "license.dat"
    
    def get_hardware_id(self):
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
            
            # 읽기 쉽게 포맷팅 (8자리씩 그룹화)
            formatted_id = '-'.join([hardware_hash[i:i+8] for i in range(0, 32, 8)])
            return formatted_id
        except Exception as e:
            print(f"하드웨어 ID 생성 중 오류 발생: {e}")
            return None

    def create_license_request(self):
        """라이선스 요청 코드 생성"""
        hardware_id = self.get_hardware_id()
        if not hardware_id:
            return None
        
        request_data = {
            'hardware_id': hardware_id,
            'timestamp': datetime.now().isoformat(),
            'system_info': {
                'os': platform.system(),
                'version': platform.version(),
                'machine': platform.machine()
            }
        }
        
        # 요청 데이터 암호화
        encrypted_data = self.cipher_suite.encrypt(json.dumps(request_data).encode())
        return encrypted_data.decode()

    def verify_license(self, license_key):
        """라이선스 키 검증"""
        try:
            # 라이선스 키 복호화
            decrypted_data = self.cipher_suite.decrypt(license_key.encode())
            license_data = json.loads(decrypted_data)
            
            # 하드웨어 ID 검증
            current_hw_id = self.get_hardware_id()
            if current_hw_id != license_data.get('hardware_id'):
                return False, "유효하지 않은 라이선스입니다."
            
            # 라이선스 만료 확인
            expiry_date = datetime.fromisoformat(license_data.get('expiry_date'))
            if datetime.now() > expiry_date:
                return False, "만료된 라이선스입니다."
            
            # 라이선스 저장
            self.save_license(license_key)
            return True, "라이선스가 성공적으로 등록되었습니다."
        except Exception as e:
            return False, f"라이선스 검증 중 오류가 발생했습니다: {e}"

    def save_license(self, license_key):
        """라이선스 정보 저장"""
        with open(self.license_file, 'w') as f:
            f.write(license_key)

    def load_license(self):
        """저장된 라이선스 정보 로드"""
        try:
            if os.path.exists(self.license_file):
                with open(self.license_file, 'r') as f:
                    return f.read()
            return None
        except Exception:
            return None

    def check_license(self):
        """라이선스 상태 확인"""
        license_key = self.load_license()
        if not license_key:
            return False, "라이선스가 등록되지 않았습니다."
        return self.verify_license(license_key)
