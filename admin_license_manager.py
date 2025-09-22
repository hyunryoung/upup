import sys
import json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import tkinter as tk
from tkinter import ttk, messagebox
import os

class AdminLicenseManager:
    def __init__(self):
        self.key = b'YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY='  # LicenseManager와 동일한 키 사용
        self.cipher_suite = Fernet(self.key)
        self.window = tk.Tk()
        self.setup_ui()
        
    def setup_ui(self):
        """UI 구성"""
        self.window.title("라이선스 관리자")
        self.window.geometry("600x400")
        
        # 하드웨어 ID 입력
        ttk.Label(self.window, text="하드웨어 ID:").pack(pady=5)
        self.hw_id_entry = ttk.Entry(self.window, width=50)
        self.hw_id_entry.pack(pady=5)
        
        # 유효기간 설정
        ttk.Label(self.window, text="유효기간 (일):").pack(pady=5)
        self.duration_entry = ttk.Entry(self.window, width=10)
        self.duration_entry.insert(0, "365")
        self.duration_entry.pack(pady=5)
        
        # 라이선스 생성 버튼
        ttk.Button(self.window, text="라이선스 생성", command=self.generate_license).pack(pady=10)
        
        # 생성된 라이선스 표시
        ttk.Label(self.window, text="생성된 라이선스 키:").pack(pady=5)
        self.license_text = tk.Text(self.window, height=5, width=50)
        self.license_text.pack(pady=5)
        
        # 승인된 라이선스 목록
        ttk.Label(self.window, text="승인된 라이선스 목록:").pack(pady=5)
        self.license_list = ttk.Treeview(self.window, columns=("하드웨어ID", "만료일"), show="headings")
        self.license_list.heading("하드웨어ID", text="하드웨어 ID")
        self.license_list.heading("만료일", text="만료일")
        self.license_list.pack(pady=5)
        
    def generate_license(self):
        """라이선스 키 생성"""
        try:
            hardware_id = self.hw_id_entry.get().strip()
            if not hardware_id:
                messagebox.showerror("오류", "하드웨어 ID를 입력해주세요.")
                return
            
            # 유효기간 계산
            try:
                duration = int(self.duration_entry.get())
                expiry_date = datetime.now() + timedelta(days=duration)
            except ValueError:
                messagebox.showerror("오류", "유효한 기간을 입력해주세요.")
                return
            
            # 라이선스 데이터 생성
            license_data = {
                'hardware_id': hardware_id,
                'issue_date': datetime.now().isoformat(),
                'expiry_date': expiry_date.isoformat(),
                'status': 'active'
            }
            
            # 라이선스 암호화
            encrypted_license = self.cipher_suite.encrypt(json.dumps(license_data).encode())
            license_key = encrypted_license.decode()
            
            # 결과 표시
            self.license_text.delete(1.0, tk.END)
            self.license_text.insert(tk.END, license_key)
            
            # 목록에 추가
            self.license_list.insert("", "end", values=(hardware_id, expiry_date.strftime("%Y-%m-%d")))
            
            messagebox.showinfo("성공", "라이선스가 성공적으로 생성되었습니다.")
            
        except Exception as e:
            messagebox.showerror("오류", f"라이선스 생성 중 오류가 발생했습니다: {e}")
    
    def run(self):
        """프로그램 실행"""
        self.window.mainloop()

if __name__ == "__main__":
    app = AdminLicenseManager()
    app.run()
