"""
네이버 로그인 처리 모듈
네이버 계정 로그인 및 IP보안 해제를 담당합니다.
"""

import time
import logging
from typing import Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..core.config import NAVER_LOGIN_URL, SELECTORS
from ..data.models import Account


class NaverLoginHandler:
    """네이버 로그인 처리 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def login_with_account(self, driver: webdriver.Chrome, account: Account) -> bool:
        """
        계정으로 네이버 로그인을 수행합니다.
        
        Args:
            driver: WebDriver 인스턴스
            account: 로그인할 계정 정보
            
        Returns:
            로그인 성공 여부
        """
        try:
            self.logger.info(f"🔑 네이버 로그인 시작: {account.id}")
            
            # 네이버 로그인 페이지로 이동
            if not self._navigate_to_login_page(driver):
                return False
            
            # IP보안 해제 시도
            if not self._disable_ip_security(driver):
                self.logger.warning("⚠️ IP보안 해제 실패 - 로그인 계속 진행")
            
            # 계정 정보 입력
            if not self._input_credentials(driver, account):
                return False
            
            # 로그인 버튼 클릭
            if not self._click_login_button(driver):
                return False
            
            # 로그인 결과 확인
            if self._verify_login_success(driver, account):
                self.logger.info(f"✅ {account.id} 네이버 로그인 성공")
                return True
            else:
                self.logger.error(f"❌ {account.id} 네이버 로그인 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ {account.id} 로그인 중 예외 발생: {str(e)}")
            return False
    
    def _navigate_to_login_page(self, driver: webdriver.Chrome) -> bool:
        """네이버 로그인 페이지로 이동"""
        try:
            self.logger.info("🌐 네이버 로그인 페이지로 이동 중...")
            driver.get(NAVER_LOGIN_URL)
            
            # 로그인 폼 로딩 대기 (하드 슬립 → WebDriverWait)
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#frmNIDLogin, .login_wrap"))
                )
                self.logger.info("✅ 로그인 페이지 로딩 완료")
            except TimeoutException:
                self.logger.warning("⚠️ 로그인 페이지 로딩 지연")
                time.sleep(2)  # 폴백
            
            # 페이지 로딩 확인
            page_title = driver.title
            page_url = driver.current_url
            self.logger.info(f"📄 페이지 제목: {page_title}")
            self.logger.info(f"📍 현재 URL: {page_url}")
            
            # 로그인 폼 확인
            try:
                login_form = driver.find_element(By.CSS_SELECTOR, SELECTORS['login']['login_form'])
                self.logger.info("✅ 로그인 폼 확인됨")
                return True
            except:
                self.logger.warning("⚠️ 로그인 폼을 찾을 수 없음 - 계속 진행")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ 네이버 페이지 이동 실패: {str(e)}")
            return False
    
    def _disable_ip_security(self, driver: webdriver.Chrome) -> bool:
        """로그인 페이지에서 IP보안 해제"""
        try:
            self.logger.info("🔍 IP보안 스위치 검색 시작...")
            
            # 페이지 로딩 상태 확인 (최적화)
            try:
                ready_state = driver.execute_script("return document.readyState")
                self.logger.info(f"📄 페이지 상태: {ready_state}")
                if ready_state != "complete":
                    self.logger.info("⏳ 페이지 로딩 미완료 - 1초 추가 대기")
                    time.sleep(1)  # 2초 → 1초
            except Exception:
                pass
            
            ip_security_selectors = [
                "#ipOnOff",
                "span.switch_on[role='checkbox']",
                "span[role='checkbox'][class*='switch_on']",
                ".ip_security_switch",
                "input[type='checkbox'][id*='ip']",
                ".security_switch.on"
            ]
            
            ip_switch_found = False
            for i, selector in enumerate(ip_security_selectors, 1):
                if ip_switch_found:
                    break
                    
                try:
                    ip_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if not ip_elements:
                        continue
                        
                    ip_element = ip_elements[0]
                    self.logger.info(f"✅ IP보안 요소 발견: {selector}")
                    
                    # 요소 타입 및 상태 확인
                    element_tag = ip_element.tag_name
                    element_type = ip_element.get_attribute("type") or ""
                    element_class = ip_element.get_attribute("class") or ""
                    element_role = ip_element.get_attribute("role") or ""
                    
                    if element_tag == "input" and element_type == "checkbox":
                        is_checked = ip_element.is_selected()
                        if is_checked:
                            self.logger.info("🔄 체크박스 ON 상태 - OFF로 변경 중...")
                            ip_element.click()
                            time.sleep(0.2)  # 0.5초 → 0.2초
                            self.logger.info("🔓 IP보안 체크박스 OFF 완료")
                            ip_switch_found = True
                            break
                        else:
                            self.logger.info("✅ 체크박스 이미 OFF 상태")
                            ip_switch_found = True
                            break
                            
                    elif "switch" in selector.lower() or "switch" in element_class.lower() or element_role == "checkbox":
                        if "switch_on" in element_class or "on" in element_class:
                            self.logger.info("🔄 스위치 ON 상태 - OFF로 변경 중...")
                            ip_element.click()
                            time.sleep(0.2)  # 0.5초 → 0.2초
                            self.logger.info("🔓 IP보안 스위치 OFF 완료")
                            ip_switch_found = True
                            break
                        else:
                            self.logger.info("✅ 스위치 이미 OFF 상태")
                            ip_switch_found = True
                            break
                            
                except Exception as selector_error:
                    continue
            
            if ip_switch_found:
                time.sleep(0.3)  # 1초 → 0.3초
                self.logger.info("🔓 IP보안 해제 작업 완료")
                return True
            else:
                self.logger.warning("⚠️ IP보안 스위치를 찾을 수 없습니다.")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ IP보안 해제 중 예외 발생: {str(e)}")
            return False
    
    def _input_credentials(self, driver: webdriver.Chrome, account: Account) -> bool:
        """계정 정보 입력 (고속 JavaScript 방식)"""
        try:
            self.logger.info("🔑 계정 정보 입력 시작...")
            
            # JavaScript 한 방에 ID/PW 입력 (최적화)
            js_input_script = f"""
            // ID와 PW를 한 번에 입력
            var idInput = document.querySelector('{SELECTORS['login']['id_input']}');
            var pwInput = document.querySelector('{SELECTORS['login']['pw_input']}');
            
            if (idInput && pwInput) {{
                idInput.value = '{account.id}';
                pwInput.value = '{account.pw}';
                
                // 입력 이벤트 트리거
                idInput.dispatchEvent(new Event('input', {{bubbles: true}}));
                pwInput.dispatchEvent(new Event('input', {{bubbles: true}}));
                
                return true;
            }}
            return false;
            """
            
            result = driver.execute_script(js_input_script)
            if result:
                self.logger.info(f"📝 ID 입력: {account.id}")
                self.logger.info("📝 비밀번호 입력 중...")
                self.logger.info("✅ 계정 정보 입력 완료")
                time.sleep(0.2)  # 최소 대기
                return True
            else:
                self.logger.error("❌ JavaScript 입력 실패")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ 계정 정보 입력 실패: {str(e)}")
            return False
    
    def _click_login_button(self, driver: webdriver.Chrome) -> bool:
        """로그인 버튼 클릭"""
        try:
            self.logger.info("🖱️ 로그인 버튼 클릭 시도...")
            
            # 다양한 로그인 버튼 선택자 시도
            login_button_selectors = [
                "#log\\.login",  # 기존 선택자
                ".btn_login",    # 새로운 선택자
                ".btn_global",   # 글로벌 버튼
                "button[type='submit']",  # submit 버튼
                ".login_btn",    # 로그인 버튼 클래스
                "input[type='submit']",  # submit input
                ".btn_login_wrap button",  # 로그인 래퍼 내 버튼
                "#frmNIDLogin button[type='submit']",  # 폼 내 submit 버튼
                "#frmNIDLogin input[type='submit']"   # 폼 내 submit input
            ]
            
            login_button = None
            for selector in login_button_selectors:
                try:
                    login_button = driver.find_element(By.CSS_SELECTOR, selector)
                    if login_button.is_displayed() and login_button.is_enabled():
                        self.logger.info(f"✅ 로그인 버튼 발견: {selector}")
                        break
                except:
                    continue
            
            if not login_button:
                self.logger.error("❌ 로그인 버튼을 찾을 수 없습니다.")
                return False
            
            # 버튼 클릭 (JavaScript 우선 시도)
            try:
                driver.execute_script("arguments[0].click();", login_button)
                self.logger.info("✅ JavaScript로 로그인 버튼 클릭 완료")
            except:
                try:
                    login_button.click()
                    self.logger.info("✅ 일반 클릭으로 로그인 버튼 클릭 완료")
                except Exception as click_error:
                    self.logger.error(f"❌ 로그인 버튼 클릭 실패: {str(click_error)}")
                    return False
            
            # 로그인 완료까지 대기 (안정화)
            time.sleep(2)  # 로그인 버튼 클릭 후 충분한 대기
            
            try:
                WebDriverWait(driver, 12).until(  # 8초 → 12초 (안정화)
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "#gnb")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".gnb_my")),
                        EC.url_contains("naver.com"),
                        EC.url_changes("https://nid.naver.com/nidlogin.login")  # URL 변경 감지
                    )
                )
                self.logger.info("✅ 로그인 완료 신호 감지")
            except TimeoutException:
                self.logger.warning("⚠️ 로그인 완료 신호 대기 시간 초과")
                time.sleep(3)  # 1초 → 3초 (추가 대기)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 로그인 버튼 클릭 실패: {str(e)}")
            return False
    
    def _verify_login_success(self, driver: webdriver.Chrome, account: Account) -> bool:
        """로그인 성공 확인"""
        try:
            self.logger.info("🔍 로그인 결과 확인 중...")
            
            current_url = driver.current_url
            self.logger.info(f"📍 로그인 후 URL: {current_url}")
            
            if "nidlogin.login" not in current_url:
                # 기기 확인 페이지 처리
                if "deviceConfirm" in current_url:
                    self.logger.info("📱 기기 확인 페이지 감지 - 로그인 성공")
                    self._handle_device_confirmation(driver)
                
                self.logger.info(f"✅ {account.id} 네이버 로그인 성공")
                return True
            else:
                # IP보안 재해제 시도
                self.logger.info("🔄 로그인 실패 - IP보안 재해제 시도")
                if self._retry_with_ip_security_disable(driver):
                    return True
                
                self.logger.error(f"❌ {account.id} 로그인 최종 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 로그인 결과 확인 실패: {str(e)}")
            return False
    
    def _handle_device_confirmation(self, driver: webdriver.Chrome) -> None:
        """기기 확인 페이지 처리"""
        try:
            no_register_btn = WebDriverWait(driver, 3).until(  # 5초 → 3초
                EC.element_to_be_clickable((By.LINK_TEXT, "등록안함"))
            )
            no_register_btn.click()
            self.logger.info("📱 기기 등록 안함 선택 완료")
            time.sleep(0.3)  # 1초 → 0.3초
        except Exception as e:
            self.logger.warning(f"⚠️ 기기 등록 안함 처리 실패: {str(e)}")
    
    def _retry_with_ip_security_disable(self, driver: webdriver.Chrome) -> bool:
        """IP보안 재해제 후 재시도"""
        try:
            self._disable_ip_security(driver)
            time.sleep(2)  # 1초 → 2초 (충분한 대기)
            
            # 로그인 버튼 다시 찾기 (더 안정적인 선택자들)
            login_button_selectors = [
                "#log\\.login",
                ".btn_login", 
                ".btn_global",
                "button[type='submit']",
                ".login_btn",
                "input[type='submit']"
            ]
            
            login_button = None
            for selector in login_button_selectors:
                try:
                    login_button = driver.find_element(By.CSS_SELECTOR, selector)
                    if login_button.is_displayed() and login_button.is_enabled():
                        break
                except:
                    continue
            
            if not login_button:
                self.logger.error("❌ 재시도용 로그인 버튼을 찾을 수 없습니다")
                return False
            
            login_button.click()
            time.sleep(5)  # 3초 → 5초 (충분한 대기)
            
            current_url = driver.current_url
            if "nidlogin.login" not in current_url:
                self.logger.info("✅ IP보안 재해제 후 로그인 성공")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ IP보안 재해제 과정에서 오류: {str(e)}")
            return False


# 전역 네이버 로그인 핸들러 인스턴스
naver_login_handler = NaverLoginHandler()
