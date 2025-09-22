"""
웹 드라이버 관리 모듈
Selenium WebDriver 생성, 설정, 관리를 담당합니다.
"""

import time
import logging
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

from ..core.config import config, SELECTORS


class WebDriverManager:
    """웹 드라이버 관리 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        import threading
        self._lock = threading.Lock()  # 스레드 안전성을 위한 락
    
    def create_driver_with_proxy(self, proxy: Optional[str] = None, headless: bool = False, purpose: str = "작업") -> webdriver.Chrome:
        """
        Chrome WebDriver를 생성합니다. (스레드 안전)
        
        Args:
            proxy: 프록시 서버 주소 (선택사항)
            headless: 헤드리스 모드 여부
            purpose: 드라이버 생성 목적 (로깅용)
            
        Returns:
            Chrome WebDriver 인스턴스
        """
        with self._lock:  # 스레드 안전한 드라이버 생성
            try:
                options = Options()
                
                # 시크릿모드 (incognito) 활성화
                options.add_argument('--incognito')
                self.logger.info(f"🕵️ {purpose} - 시크릿모드로 브라우저 생성")
                
                # 헤드리스 모드
                if headless:
                    options.add_argument('--headless')
                    self.logger.info(f"👻 {purpose} - 헤드리스 모드 활성화")
                else:
                    self.logger.info(f"🖥️ {purpose} - 일반 모드 (브라우저 표시)")
                
                # 기본 안정성 옵션들
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--disable-software-rasterizer')
                options.add_argument('--disable-background-timer-throttling')
                options.add_argument('--disable-backgrounding-occluded-windows')
                options.add_argument('--disable-renderer-backgrounding')
                options.add_argument('--disable-web-security')
                options.add_argument('--allow-running-insecure-content')
                
                # WebGL 관련 오류 해결  
                options.add_argument('--use-gl=swiftshader')
                options.add_argument('--enable-unsafe-swiftshader')
                
                # 로그 레벨 조정 (오류 메시지 줄이기)
                options.add_argument('--log-level=3')
                options.add_argument('--silent')
                
                # 자동화 탐지 우회 (필수)
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                
                # 프록시 설정 (치명적 버그 수정!)
                if proxy:
                    if '@' in proxy:
                        # user:pass@host:port 형식
                        proxy_url = f"http://{proxy}"
                    else:
                        # host:port 형식
                        proxy_url = f"http://{proxy}"
                    
                    options.add_argument(f'--proxy-server={proxy_url}')
                    proxy_display = proxy.split('@')[-1] if '@' in proxy else proxy
                    self.logger.info(f"🔗 {purpose} - 프록시 {proxy_display} 실제 적용됨")
                else:
                    self.logger.info(f"🌐 {purpose} - 직접 연결")
                
                # User-Agent 설정
                options.add_argument(f'--user-agent={config.webdriver.user_agent}')
                
                # 성능 최적화: 불필요한 리소스 차단 (이미지는 허용 - 탈퇴회원 아이콘 표시용)
                options.add_experimental_option("prefs", {
                    "profile.managed_default_content_settings.images": 1,  # 이미지 허용 (탈퇴회원 아이콘 표시)
                    "profile.managed_default_content_settings.stylesheets": 1,  # CSS 허용
                    "profile.managed_default_content_settings.cookies": 1,  # 쿠키 허용
                    "profile.managed_default_content_settings.javascript": 1,  # JS 허용
                    "profile.managed_default_content_settings.plugins": 2,  # 플러그인 차단
                    "profile.managed_default_content_settings.popups": 2,  # 팝업 차단
                    "profile.managed_default_content_settings.geolocation": 2,  # 위치 차단
                    "profile.managed_default_content_settings.notifications": 2,  # 알림 차단
                    "profile.managed_default_content_settings.media_stream": 2,  # 미디어 차단
                    "profile.managed_default_content_settings.automatic_downloads": 2,  # 자동 다운로드 차단
                })
                
                # 빠른 페이지 로딩 전략 (이미지는 허용)
                
                # 페이지 로드 전략 최적화 (eager로 고정)
                options.page_load_strategy = 'eager'  # DOM 완료시 제어 가능
                
                # 드라이버 생성
                try:
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=options)
                except:
                    driver = webdriver.Chrome(options=options)
                
                # 자동화 감지 우회 스크립트 실행
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                # 타임아웃 설정 (암묵적 대기 OFF)
                driver.implicitly_wait(0)  # 암묵적 대기 OFF
                driver.set_page_load_timeout(config.webdriver.page_load_timeout)
                driver.set_script_timeout(config.webdriver.script_timeout)
                
                self.logger.info(f"✅ {purpose} - 브라우저 시작 완료")
                return driver
                
            except Exception as e:
                self.logger.error(f"❌ {purpose} - 브라우저 시작 실패: {str(e)}")
                raise Exception(f"웹 드라이버 생성 실패: {str(e)}")
    
    def switch_to_iframe(self, driver: webdriver.Chrome, iframe_name: str = "cafe_main") -> bool:
        """
        지정된 iframe으로 전환합니다 (고속 최적화 버전).
        
        Args:
            driver: WebDriver 인스턴스
            iframe_name: iframe 이름
            
        Returns:
            전환 성공 여부
        """
        iframe_selectors = [
            f"iframe[name='{iframe_name}']",
            f"iframe[title='{iframe_name}']", 
            f"iframe[name='main']",
            f"iframe[title='main']",
            f"iframe.main_frame",
            f"iframe[src*='cafe']",
            f"iframe[src*='ArticleList']",
            f"iframe[src*='menu']",
            f"iframe",  # 첫 번째 iframe (최후 수단)
        ]
        
        for selector in iframe_selectors:
            try:
                # 빠른 iframe 전환 (대기 시간 단축)
                try:
                    iframe = WebDriverWait(driver, 2).until(  # 5초 → 2초
                        EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, selector))
                    )
                    self.logger.debug(f"✅ iframe 전환 성공: {selector}")
                    return True
                except TimeoutException:
                    continue
                    
            except Exception as e:
                self.logger.debug(f"🔍 iframe 선택자 '{selector}' 처리 실패: {str(e)}")
                continue
                
        # 폴백: 직접 찾기 (더 빠른 방법)
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                driver.switch_to.frame(iframes[0])
                self.logger.debug("✅ iframe 전환 성공 (폴백)")
                return True
        except Exception as e:
            self.logger.debug(f"🔍 iframe 폴백 실패: {str(e)}")
                
        self.logger.warning("⚠️ iframe 전환 실패")
        return False
    
    def switch_to_default_content(self, driver: webdriver.Chrome) -> None:
        """기본 컨텐츠로 전환합니다."""
        try:
            driver.switch_to.default_content()
            self.logger.debug("🔄 기본 프레임으로 복귀 완료")
        except Exception as e:
            self.logger.warning(f"⚠️ 기본 프레임 복귀 실패: {str(e)}")
    
    def wait_for_element(self, driver: webdriver.Chrome, selector: str, timeout: int = 10, by: By = By.CSS_SELECTOR):
        """
        요소가 나타날 때까지 대기합니다.
        
        Args:
            driver: WebDriver 인스턴스
            selector: 요소 선택자
            timeout: 대기 시간 (초)
            by: 선택자 타입
            
        Returns:
            찾은 요소
        """
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            return element
        except Exception as e:
            self.logger.warning(f"⚠️ 요소 대기 실패: {selector}, 오류: {str(e)}")
            return None
    
    def wait_for_clickable_element(self, driver: webdriver.Chrome, selector: str, timeout: int = 10, by: By = By.CSS_SELECTOR):
        """
        요소가 클릭 가능할 때까지 대기합니다.
        
        Args:
            driver: WebDriver 인스턴스
            selector: 요소 선택자
            timeout: 대기 시간 (초)
            by: 선택자 타입
            
        Returns:
            클릭 가능한 요소
        """
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, selector))
            )
            return element
        except Exception as e:
            self.logger.warning(f"⚠️ 클릭 가능한 요소 대기 실패: {selector}, 오류: {str(e)}")
            return None
    
    def safe_click(self, driver: webdriver.Chrome, element) -> bool:
        """
        요소를 안전하게 클릭합니다.
        
        Args:
            driver: WebDriver 인스턴스
            element: 클릭할 요소
            
        Returns:
            클릭 성공 여부
        """
        try:
            # JavaScript로 클릭 시도
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            try:
                # 일반 클릭 시도
                element.click()
                return True
            except Exception as e2:
                self.logger.warning(f"⚠️ 요소 클릭 실패: {str(e2)}")
                return False
    
    def get_current_ip(self, driver: webdriver.Chrome) -> str:
        """
        현재 IP 주소를 확인합니다.
        
        Args:
            driver: WebDriver 인스턴스
            
        Returns:
            현재 IP 주소
        """
        try:
            driver.get("https://httpbin.org/ip")
            time.sleep(2)
            
            # JSON 응답에서 IP 추출
            ip_element = driver.find_element(By.TAG_NAME, "pre")
            ip_json = ip_element.text
            
            import json
            ip_data = json.loads(ip_json)
            return ip_data.get("origin", "알 수 없음")
            
        except Exception as e:
            self.logger.warning(f"⚠️ IP 확인 실패: {str(e)}")
            return "확인 실패"
    
    def close_driver(self, driver: webdriver.Chrome) -> None:
        """
        WebDriver를 안전하게 종료합니다. (스레드 안전)
        
        Args:
            driver: 종료할 WebDriver 인스턴스
        """
        with self._lock:  # 스레드 안전한 드라이버 종료
            try:
                if driver:
                    # 호출 스택 추적 (디버깅용)
                    import traceback
                    caller_info = traceback.extract_stack()[-2]
                    self.logger.info(f"🔍 close_driver 호출: {caller_info.filename}:{caller_info.lineno} - {caller_info.name}")
                
                    # 이중 보호: 재사용 중인 드라이버인지 확인
                    if (hasattr(driver, '_reuse_mode') and driver._reuse_mode) or \
                       (hasattr(driver, '_protected_from_close') and driver._protected_from_close):
                        self.logger.info("🔄 재사용/보호 모드 드라이버 - 종료 방지")
                        return
                    
                    driver.quit()
                    self.logger.info("🔚 브라우저 종료 완료")
            except Exception as e:
                self.logger.warning(f"⚠️ 브라우저 종료 중 오류: {str(e)}")
    
    def refresh_page(self, driver: webdriver.Chrome, wait_time: int = 2) -> None:
        """
        페이지를 새로고침합니다.
        
        Args:
            driver: WebDriver 인스턴스
            wait_time: 새로고침 후 대기 시간
        """
        try:
            driver.refresh()
            time.sleep(wait_time)
            self.logger.debug("🔄 페이지 새로고침 완료")
        except Exception as e:
            self.logger.warning(f"⚠️ 페이지 새로고침 실패: {str(e)}")
    
    def execute_in_iframe(self, driver: webdriver.Chrome, iframe_name: str, func, *args, **kwargs):
        """
        iframe 내에서 함수 실행 후 자동으로 원래 프레임으로 복귀
        iframe 전환/복귀 최소화를 위한 헬퍼 함수
        
        Args:
            driver: WebDriver 인스턴스
            iframe_name: iframe 이름
            func: 실행할 함수
            *args, **kwargs: 함수 인자
            
        Returns:
            함수 실행 결과
        """
        original_frame = None
        try:
            # 현재 프레임 정보 저장 (가능한 경우)
            try:
                original_frame = driver.current_window_handle
            except:
                pass
            
            # iframe 전환
            if self.switch_to_iframe(driver, iframe_name):
                # iframe 내에서 함수 실행
                result = func(driver, *args, **kwargs)
                return result
            else:
                self.logger.warning(f"⚠️ iframe '{iframe_name}' 전환 실패")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ iframe 내 함수 실행 실패: {str(e)}")
            return None
        finally:
            # 반드시 원래 프레임으로 복귀
            try:
                self.switch_to_default_content(driver)
            except Exception as e:
                self.logger.warning(f"⚠️ 원래 프레임 복귀 실패: {str(e)}")
    
    def batch_execute_in_iframe(self, driver: webdriver.Chrome, iframe_name: str, operations: list):
        """
        iframe 내에서 여러 작업을 한 번에 실행
        프레임 전환 횟수를 최소화하여 성능 향상
        
        Args:
            driver: WebDriver 인스턴스
            iframe_name: iframe 이름
            operations: 실행할 작업 리스트 [(func, args, kwargs), ...]
            
        Returns:
            각 작업의 실행 결과 리스트
        """
        results = []
        
        try:
            # iframe 전환
            if not self.switch_to_iframe(driver, iframe_name):
                self.logger.warning(f"⚠️ iframe '{iframe_name}' 전환 실패")
                return results
            
            # 모든 작업을 순차 실행
            for i, (func, args, kwargs) in enumerate(operations):
                try:
                    result = func(driver, *args, **kwargs)
                    results.append(result)
                    self.logger.debug(f"✅ iframe 내 작업 {i+1}/{len(operations)} 완료")
                except Exception as e:
                    self.logger.warning(f"⚠️ iframe 내 작업 {i+1} 실패: {str(e)}")
                    results.append(None)
            
            return results
            
        except Exception as e:
            self.logger.error(f"❌ iframe 일괄 작업 실패: {str(e)}")
            return results
        finally:
            # 반드시 원래 프레임으로 복귀
            self.switch_to_default_content(driver)


# 전역 웹 드라이버 매니저 인스턴스
web_driver_manager = WebDriverManager()
