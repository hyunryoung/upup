"""
탈퇴 회원 게시글 탐색 모듈
카페에서 탈퇴한 회원의 게시글을 찾아서 댓글 작성 대상으로 활용합니다.
"""

import re
import time
import logging
from typing import List, Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from ..data.models import DeletedPost, CafeInfo
from .web_driver import WebDriverManager


class DeletedMemberFinder:
    """탈퇴 회원 게시글 탐색 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        from ..automation.web_driver import WebDriverManager
        self.web_driver_manager = WebDriverManager()
        # 새로가입 카페 전용 - 닉네임 저장 불필요
    
    def find_deleted_member_posts(self, driver: webdriver.Chrome, cafe_info: CafeInfo, 
                                 work_board_id: str, start_page: int = 1, 
                                 target_posts: int = 1) -> List[DeletedPost]:
        """
        여러 페이지를 순회하며 탈퇴한 회원의 게시글 찾기
        
        Args:
            driver: WebDriver 인스턴스
            cafe_info: 카페 정보
            work_board_id: 작업 게시판 ID
            start_page: 탐색 시작 페이지
            target_posts: 목표 게시글 수
            
        Returns:
            탈퇴 회원 게시글 목록
        """
        deleted_posts = []
        
        try:
            # 작업 게시판으로 이동
            if not self._navigate_to_board(driver, cafe_info, work_board_id):
                return deleted_posts
            
            # 카페 숫자 ID 추출
            cafe_numeric_id = self._extract_cafe_numeric_id(driver, cafe_info)
            if not cafe_numeric_id:
                self.logger.error("❌ 카페 숫자 ID 추출 실패")
                return deleted_posts
            
            # 새로가입 카페 전용 - 닉네임 비교 불필요
            self.logger.info("ℹ️ 새로가입 카페 전용 모드 - 닉네임 비교 생략")
            
            # 페이지별 탐색 (빠른 버전 사용)
            deleted_posts = self._search_pages_for_deleted_posts_fast(
                driver, cafe_numeric_id, work_board_id, start_page, target_posts
            )
            
            return deleted_posts
            
        except Exception as e:
            self.logger.error(f"❌ 탈퇴한 회원 찾기 실패: {str(e)}")
            return deleted_posts
        finally:
            self.web_driver_manager.switch_to_default_content(driver)
    
    def _navigate_to_board(self, driver: webdriver.Chrome, cafe_info: CafeInfo, work_board_id: str) -> bool:
        """작업 게시판으로 이동"""
        try:
            # 카페 숫자 ID 추출
            cafe_numeric_id = self._extract_cafe_numeric_id(driver, cafe_info)
            if not cafe_numeric_id:
                return False
            
            # 작업 게시판 URL로 이동 (올바른 URL 형태 + size=50)
            board_urls = [
                f"https://cafe.naver.com/f-e/cafes/{cafe_numeric_id}/menus/{work_board_id}?viewType=L&size=50",   # 올바른 형태
                f"https://cafe.naver.com/ca-fe/cafes/{cafe_numeric_id}/menus/{work_board_id}?viewType=L&size=50",  # 대안
                f"https://cafe.naver.com/{cafe_info.cafe_id}/{work_board_id}",  # 구버전
                f"https://cafe.naver.com/ArticleList.nhn?search.clubid={cafe_numeric_id}&search.menuid={work_board_id}&size=50",  # 직접 URL
            ]
            
            self.logger.info(f"⚒️ 작업 게시판(ID: {work_board_id})으로 이동 시도...")
            
            for i, board_url in enumerate(board_urls, 1):
                try:
                    self.logger.info(f"🔗 {i}/{len(board_urls)} URL 시도: {board_url}")
                    driver.get(board_url)
                    time.sleep(3)
                    
                    current_url = driver.current_url
                    page_title = driver.title
                    
                    if "error" not in current_url.lower() and "NotFound" not in page_title:
                        self.logger.info(f"✅ 게시판 이동 성공: {board_url}")
                        return True
                    else:
                        self.logger.warning(f"⚠️ 페이지 오류 감지, 다음 URL 시도...")
                        
                except Exception as url_error:
                    self.logger.warning(f"❌ URL 이동 실패: {str(url_error)}")
                    continue
            
            self.logger.error("❌ 모든 게시판 URL 이동 실패")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 게시판 이동 중 예외 발생: {str(e)}")
            return False
    
    def _extract_cafe_numeric_id(self, driver: webdriver.Chrome, cafe_info: CafeInfo) -> Optional[str]:
        """카페의 숫자 ID 추출"""
        try:
            cafe_url = f"https://cafe.naver.com/{cafe_info.cafe_id}"
            self.logger.info(f"🌐 카페 페이지로 이동: {cafe_url}")
            
            driver.get(cafe_url)
            time.sleep(3)
            
            page_source = driver.page_source
            if not page_source or len(page_source) < 100:
                self.logger.warning("⚠️ 페이지가 제대로 로드되지 않았습니다.")
                return None
            
            # 숫자 ID 패턴 검색
            patterns = [
                r'/cafes/(\d+)/',
                r'"cafeId":"(\d+)"',
                r'"cafeId":(\d+)',
                r'cafeId=(\d+)',
                r'cafe_id=(\d+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, page_source)
                if match:
                    cafe_id = match.group(1)
                    self.logger.info(f"✅ 카페 숫자 ID 발견: {cafe_id}")
                    return cafe_id
            
            self.logger.warning("⚠️ 카페 숫자 ID를 찾을 수 없습니다.")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 카페 ID 추출 중 예외 발생: {str(e)}")
            return None
    
    def _get_my_nicknames(self, driver: webdriver.Chrome) -> None:
        """본인 닉네임들 확인"""
        if not self.my_nickname:
            self.logger.info("🔍 카페에서 본인 닉네임 확인 중...")
            self.my_nickname = self._get_my_nickname_in_cafe(driver)
            if self.my_nickname:
                self.logger.info(f"✅ 본인 닉네임 저장 완료: '{self.my_nickname}'")
        
        if not self.my_cafe_nickname:
            self.logger.info("🔍 카페 내 실제 닉네임 추가 확인 중...")
            self.my_cafe_nickname = self._get_my_cafe_specific_nickname(driver)
            if self.my_cafe_nickname:
                self.logger.info(f"✅ 카페 내 닉네임 추가 확인: '{self.my_cafe_nickname}'")
    
    def _get_my_nickname_in_cafe(self, driver: webdriver.Chrome) -> Optional[str]:
        """카페에서 본인 닉네임 가져오기"""
        try:
            # JavaScript 변수에서 사용자 ID 가져오기
            try:
                user_id = driver.execute_script("return window.g_sUserId || '';")
                if user_id and user_id.strip():
                    self.logger.info(f"✅ JavaScript에서 사용자 ID 확인: '{user_id}'")
                    return user_id.strip()
            except Exception:
                pass
            
            # GNB에서 닉네임 가져오기
            gnb_selectors = [
                "#gnb_name1",
                "#gnb_name2 .gnb_nick",
                ".gnb_name",
                ".gnb_my .gnb_name"
            ]
            
            for selector in gnb_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    nickname = element.text.strip()
                    if nickname and len(nickname) <= 20:
                        self.logger.info(f"✅ GNB에서 닉네임 확인: '{nickname}'")
                        return nickname
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 본인 닉네임 가져오기 실패: {str(e)}")
            return None
    
    def _get_my_cafe_specific_nickname(self, driver: webdriver.Chrome) -> Optional[str]:
        """카페 내에서 사용되는 실제 닉네임 찾기"""
        try:
            # iframe 내에서 editLayer 확인
            if self.web_driver_manager.switch_to_iframe(driver, "cafe_main"):
                cafe_nickname = self._get_cafe_nickname_from_iframe(driver)
                self.web_driver_manager.switch_to_default_content(driver)
                if cafe_nickname:
                    return cafe_nickname
            
            # 메인 페이지에서 카페 관련 요소 확인
            return self._get_cafe_nickname_from_main_page(driver)
            
        except Exception as e:
            self.logger.error(f"❌ 카페 내 닉네임 탐색 실패: {str(e)}")
            return None
    
    def _get_cafe_nickname_from_iframe(self, driver: webdriver.Chrome) -> Optional[str]:
        """iframe 내에서 카페 닉네임 찾기"""
        selectors = [
            "li#editLayer",
            "li[id='editLayer']",
            ".name#editLayer",
            ".name[title]"
        ]
        
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                
                # title 속성 확인
                title = element.get_attribute("title")
                if title and title.strip() and len(title.strip()) <= 20:
                    return title.strip()
                
                # 내부 링크 텍스트 확인
                try:
                    link = element.find_element(By.CSS_SELECTOR, ".prfl_info a, a")
                    link_text = link.text.strip()
                    if link_text and len(link_text) <= 20:
                        return link_text
                except:
                    pass
                    
            except:
                continue
        
        return None
    
    def _get_cafe_nickname_from_main_page(self, driver: webdriver.Chrome) -> Optional[str]:
        """메인 페이지에서 카페 닉네임 찾기"""
        try:
            # 나의활동 버튼 클릭해서 사이드바 열기
            my_activity_selectors = [
                ("xpath", "//button[contains(text(), '나의활동')]"),
                ("xpath", "//button[@onclick='showMyAction();']"),
                ("css", "li.tit-action button"),
            ]
            
            for selector_type, selector_value in my_activity_selectors:
                try:
                    if selector_type == "xpath":
                        my_activity_btn = driver.find_element(By.XPATH, selector_value)
                    else:
                        my_activity_btn = driver.find_element(By.CSS_SELECTOR, selector_value)
                    
                    my_activity_btn.click()
                    time.sleep(2)
                    break
                except:
                    continue
            
            # 사이드바에서 닉네임 찾기
            selectors = [
                "strong.Sidebar_nickname__EAtDX",
                "[title][id*='edit']",
                ".name[title]",
                ".prfl_info a",
                ".member_info .nick",
                ".cafe_member .nickname"
            ]
            
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        # title 속성 우선 확인
                        title = element.get_attribute("title")
                        if title and title.strip() and len(title.strip()) <= 20:
                            return title.strip()
                        
                        # 텍스트 내용 확인
                        text = element.text.strip()
                        if text and len(text) <= 20:
                            return text
                except:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"⚠️ 메인 페이지 닉네임 탐색 실패: {str(e)}")
            return None
    
    def _search_pages_for_deleted_posts(self, driver: webdriver.Chrome, cafe_numeric_id: str, 
                                       work_board_id: str, start_page: int, 
                                       target_posts: int) -> List[DeletedPost]:
        """페이지별 탈퇴 회원 게시글 검색"""
        deleted_posts = []
        current_page = start_page
        searched_pages = 0
        phase = 1  # 1단계: 시작페이지→끝, 2단계: 1페이지→시작페이지-1
        
        self.logger.info(f"🔄 1단계: {start_page}페이지부터 끝까지 검색 시작")
        
        # 시작 페이지로 이동 (올바른 URL 형태)
        start_page_url = f"https://cafe.naver.com/f-e/cafes/{cafe_numeric_id}/menus/{work_board_id}?viewType=L&page={current_page}&size=50"
        try:
            driver.get(start_page_url)
            time.sleep(2)
            self.logger.info(f"🚀 {current_page}페이지로 이동 완료")
        except Exception as e:
            self.logger.error(f"❌ 시작 페이지 이동 실패: {str(e)}")
            return deleted_posts
        
        # 페이지별로 탈퇴 회원 찾기
        while len(deleted_posts) < target_posts:
            searched_pages += 1
            self.logger.info(f"📄 {current_page}페이지에서 탈퇴 회원 검색 중... (순방향 {searched_pages}번째)")
            
            # 현재 페이지에서 탈퇴 회원 찾기
            page_deleted_posts = self._find_deleted_members_single_page(driver)
            
            if page_deleted_posts:
                deleted_posts.extend(page_deleted_posts)
                self.logger.info(f"✅ {current_page}페이지에서 {len(page_deleted_posts)}개 발견 (총 {len(deleted_posts)}개)")
            else:
                self.logger.info(f"⚠️ {current_page}페이지에서 탈퇴 회원 없음")
            
            # 목표 수량 달성시 중단
            if len(deleted_posts) >= target_posts:
                self.logger.info(f"🎯 목표 수량({target_posts}개) 달성! 검색 완료")
                break
            
            # 다음 페이지로 이동 (올바른 URL 형태)
            current_page += 1
            next_page_url = f"https://cafe.naver.com/f-e/cafes/{cafe_numeric_id}/menus/{work_board_id}?viewType=L&page={current_page}&size=50"
            
            try:
                driver.get(next_page_url)
                time.sleep(2)
                
                # 페이지 유효성 확인
                page_posts = driver.find_elements(By.CSS_SELECTOR, "button.nick_btn")
                if not page_posts:
                    # 1단계에서 끝페이지 도달 시 2단계로 전환
                    if phase == 1 and start_page > 1:
                        self.logger.info(f"🔄 1단계 완료! 2단계 시작: 1페이지 → {start_page-1}페이지")
                        current_page = 1
                        phase = 2
                        driver.get(f"https://cafe.naver.com/ca-fe/cafes/{cafe_numeric_id}/menus/{work_board_id}?size=50&viewType=L&page=1")
                        time.sleep(2)
                        continue
                    else:
                        self.logger.info("🔄 전체 검색 완료!")
                        break
                
                # 2단계에서 시작페이지 도달 시 종료
                if phase == 2 and current_page >= start_page:
                    self.logger.info("🔄 2단계 완료! 전체 검색 완료")
                    break
                
            except Exception as url_error:
                self.logger.warning(f"❌ URL 이동 실패: {str(url_error)}")
                if phase == 1 and start_page > 1:
                    current_page = 1
                    phase = 2
                    continue
                else:
                    break
        
        phase_text = "2단계까지" if phase == 2 else "1단계만"
        self.logger.info(f"🔍 페이지 검색 완료: 총 {len(deleted_posts)}개 탈퇴 회원 게시글 발견 ({phase_text} 완료, 총 {searched_pages}페이지 탐색)")
        
        return deleted_posts

    def _search_pages_for_deleted_posts_fast(self, driver: webdriver.Chrome, cafe_numeric_id: str, 
                                           work_board_id: str, start_page: int, target_posts: int) -> List[DeletedPost]:
        """페이지별 탈퇴 회원 탐색 (빠른 버전)"""
        deleted_posts = []
        current_page = start_page
        phase = 1  # 1단계: 시작페이지부터 끝까지, 2단계: 1페이지부터 시작페이지 전까지
        searched_pages = 0
        
        self.logger.info(f"🔄 1단계: {start_page}페이지부터 끝까지 검색 시작")
        
        # 시작 페이지로 이동 (올바른 URL 형태)
        start_page_url = f"https://cafe.naver.com/f-e/cafes/{cafe_numeric_id}/menus/{work_board_id}?viewType=L&page={current_page}&size=50"
        
        try:
            driver.get(start_page_url)
            self.logger.info(f"🚀 {current_page}페이지로 이동 완료")
            time.sleep(2)
        except Exception as url_error:
            self.logger.error(f"❌ 시작 페이지 이동 실패: {str(url_error)}")
            return deleted_posts
        
        while len(deleted_posts) < target_posts:
            searched_pages += 1
            self.logger.info(f"📄 {current_page}페이지에서 탈퇴 회원 검색 중... ({'순방향' if phase == 1 else '역방향'} {searched_pages}번째)")
            
            # 현재 페이지에서 탈퇴 회원 찾기 (빠른 버전)
            page_deleted_posts = self.find_deleted_members_single_page_fast(driver)
            deleted_posts.extend(page_deleted_posts)
            
            # 목표 개수 달성 시 종료
            if len(deleted_posts) >= target_posts:
                self.logger.info(f"🎉 목표 달성! {len(deleted_posts)}개 탈퇴 회원 게시글 확보")
                break
            
            # 다음 페이지로 이동 (올바른 URL 형태)
            current_page += 1
            next_page_url = f"https://cafe.naver.com/f-e/cafes/{cafe_numeric_id}/menus/{work_board_id}?viewType=L&page={current_page}&size=50"
            
            try:
                driver.get(next_page_url)
                time.sleep(1)  # 대기시간 단축
                
                # 페이지 유효성 확인
                page_posts = driver.find_elements(By.CSS_SELECTOR, "button.nick_btn")
                if not page_posts:
                    # 1단계에서 끝페이지 도달 시 2단계로 전환
                    if phase == 1 and start_page > 1:
                        self.logger.info(f"🔄 1단계 완료! 2단계 시작: 1페이지 → {start_page-1}페이지")
                        current_page = 1
                        phase = 2
                        driver.get(f"https://cafe.naver.com/f-e/cafes/{cafe_numeric_id}/menus/{work_board_id}?viewType=L&page=1&size=50")
                        time.sleep(1)
                        continue
                    else:
                        self.logger.info("🔄 전체 검색 완료!")
                        break
                
                # 2단계에서 시작페이지 도달 시 종료
                if phase == 2 and current_page >= start_page:
                    self.logger.info("🔄 2단계 완료! 전체 검색 완료")
                    break
                
            except Exception as url_error:
                self.logger.warning(f"❌ URL 이동 실패: {str(url_error)}")
                if phase == 1 and start_page > 1:
                    current_page = 1
                    phase = 2
                    continue
                else:
                    break
        
        phase_text = "2단계까지" if phase == 2 else "1단계만"
        self.logger.info(f"🔍 페이지 검색 완료: 총 {len(deleted_posts)}개 탈퇴 회원 게시글 발견 ({phase_text} 완료, 총 {searched_pages}페이지 탐색)")
        
        return deleted_posts
    
    def _find_deleted_members_single_page(self, driver: webdriver.Chrome) -> List[DeletedPost]:
        """현재 페이지에서 탈퇴한 회원의 게시글 찾기"""
        deleted_posts = []
        
        try:
            # 페이지 완전 로딩 대기
            self.logger.info("⏳ 게시판 페이지 완전 로딩 대기 중...")
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(5)  # 동적 콘텐츠 추가 대기
            
            # iframe 상태 초기화
            self.web_driver_manager.switch_to_default_content(driver)
            
            # iframe 전환 시도 (여러 번)
            iframe_success = False
            for attempt in range(5):
                iframe_success = self.web_driver_manager.switch_to_iframe(driver, "iframe[name='cafe_main']")
                if iframe_success:
                    self.logger.info(f"✅ iframe 전환 성공 (시도 {attempt + 1}/5)")
                    break
                self.logger.warning(f"🔄 iframe 전환 재시도 {attempt + 1}/5")
                time.sleep(3)
            
            if not iframe_success:
                self.logger.warning("⚠️ iframe 전환 최종 실패, 폴백 방식 시도")
                return self._find_deleted_members_fallback(driver)
            
            # iframe 내용 로딩 완료 대기
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(2)
            
            # JavaScript로 작성자 버튼 찾기
            author_buttons = self._find_author_buttons_with_js(driver)
            
            if not author_buttons:
                self.logger.warning("❌ 작성자 닉네임 버튼을 찾을 수 없습니다.")
                return self._find_deleted_members_fallback(driver)
            
            self.logger.info(f"🚀 JavaScript로 {len(author_buttons)}명의 탈퇴회원 판별 시작...")
            
            # JavaScript로 탈퇴회원 판별 + 게시글 링크 추출
            deleted_members_data = self._identify_deleted_members_with_js(driver, author_buttons)
            
            # 결과를 DeletedPost 객체로 변환
            for member_data in deleted_members_data:
                deleted_post = DeletedPost(
                    link=member_data['link'],
                    author=member_data['nickname']
                )
                deleted_posts.append(deleted_post)
            
            self.logger.info(f"⚡ JavaScript 고속 처리 완료: {len(deleted_posts)}개 탈퇴 회원 발견")
            
        except Exception as e:
            self.logger.error(f"❌ 단일 페이지 탈퇴 회원 찾기 실패: {str(e)}")
        
        return deleted_posts
    
    def _find_author_buttons_with_js(self, driver: webdriver.Chrome) -> List:
        """JavaScript로 작성자 버튼 찾기"""
        try:
            author_buttons = driver.execute_script("""
                // iframe 내부 확인
                var buttons = [];
                
                // 1. 메인 페이지에서 찾기
                var mainButtons = document.querySelectorAll('button.nick_btn');
                if (mainButtons.length > 0) {
                    return Array.from(mainButtons);
                }
                
                // 2. iframe 내부에서 찾기
                var iframes = document.querySelectorAll('iframe');
                for (var i = 0; i < iframes.length; i++) {
                    try {
                        var iframeDoc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                        var iframeButtons = iframeDoc.querySelectorAll('button.nick_btn');
                        if (iframeButtons.length > 0) {
                            return Array.from(iframeButtons);
                        }
                    } catch (e) {
                        continue;
                    }
                }
                
                return [];
            """)
            
            if author_buttons and len(author_buttons) > 0:
                self.logger.info(f"✅ JavaScript로 작성자 버튼 {len(author_buttons)}개 발견")
                return author_buttons
            else:
                self.logger.warning("⚠️ JavaScript 방식 실패, 기존 방식으로 시도")
                return self._find_author_buttons_fallback(driver)
                
        except Exception as e:
            self.logger.warning(f"⚠️ JavaScript 실행 오류: {str(e)} - 기존 방식으로 전환")
            return self._find_author_buttons_fallback(driver)
    
    def _find_author_buttons_fallback(self, driver: webdriver.Chrome) -> List:
        """기존 방식으로 작성자 버튼 찾기"""
        try:
            # iframe 방식 시도
            if self.web_driver_manager.switch_to_iframe(driver, "cafe_main"):
                time.sleep(0.5)
                author_buttons = self._find_author_links(driver)
                if author_buttons:
                    return author_buttons
                self.web_driver_manager.switch_to_default_content(driver)
            
            # 메인 페이지 방식
            time.sleep(0.5)
            return self._find_author_links(driver)
            
        except Exception as e:
            self.logger.warning(f"❌ 기존 방식도 실패: {str(e)}")
            return []
    
    def _find_author_links(self, driver: webdriver.Chrome) -> List:
        """작성자 닉네임 버튼들 찾기"""
        author_button_selectors = [
            "button.nick_btn",
            ".ArticleBoardWriterInfo button.nick_btn",
            ".article-table button.nick_btn",
            "button[aria-haspopup='true']",
            ".ArticleBoardWriterInfo button",
            ".nickname",
            "button[type='button'][class*='nick']",
            "button[class*='author']",
        ]
        
        for selector in author_button_selectors:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                if buttons:
                    # 유효한 버튼만 필터링
                    valid_buttons = []
                    for button in buttons:
                        try:
                            class_name = button.get_attribute("class") or ""
                            aria_haspopup = button.get_attribute("aria-haspopup")
                            text = button.text.strip()
                            
                            if ("nick_btn" in class_name or aria_haspopup == "true") and text and len(text) <= 50:
                                valid_buttons.append(button)
                        except:
                            continue
                    
                    if valid_buttons:
                        self.logger.info(f"✅ 닉네임 버튼 {len(valid_buttons)}개 발견")
                        return valid_buttons
            except:
                continue
        
        return []
    
    def _identify_deleted_members_with_js(self, driver: webdriver.Chrome, author_buttons: List) -> List[Dict]:
        """JavaScript로 탈퇴회원 판별 + 게시글 링크 추출"""
        try:
            my_nicknames = [nick for nick in [self.my_nickname, self.my_cafe_nickname] if nick]
            
            deleted_members_data = driver.execute_script("""
                var buttons = arguments[0];
                var myNicknames = arguments[1];
                var deletedMembers = [];
                
                for (var i = 0; i < buttons.length; i++) {
                    try {
                        var button = buttons[i];
                        var nickname = button.textContent.trim().split('\\n')[0];
                        
                        // 본인 계정 제외
                        var isMyAccount = false;
                        for (var j = 0; j < myNicknames.length; j++) {
                            if (nickname === myNicknames[j] || 
                                nickname.includes(myNicknames[j]) || 
                                myNicknames[j].includes(nickname)) {
                                isMyAccount = true;
                                break;
                            }
                        }
                        if (isMyAccount) continue;
                        
                        // 레벨 아이콘 확인
                        var levelIcon = null;
                        var parentTr = button.closest('tr');
                        if (parentTr) {
                            levelIcon = parentTr.querySelector('.level_ico, .lv_ico, [class*="level"], [class*="lv"], .ico_level, .grade_ico, [class*="grade"], [class*="member"], img[src*="level"], img[src*="grade"]');
                            
                            // 텍스트에서 등급 정보 확인
                            if (!levelIcon) {
                                var trText = parentTr.textContent || '';
                                if (trText.includes('교대역장') || trText.includes('등업대기') || trText.includes('멤버등급') || trText.includes('씨씨')) {
                                    levelIcon = true;
                                }
                            }
                        }
                        
                        // 레벨 아이콘이 없으면 탈퇴회원
                        if (!levelIcon) {
                            // 게시글 링크 찾기
                            var postLink = null;
                            if (parentTr) {
                                var linkElement = parentTr.querySelector('a[href*="/articles/"], a[href*="ArticleRead"], a[href*="articleid="]');
                                if (linkElement) {
                                    postLink = linkElement.href;
                                }
                            }
                            
                            if (postLink) {
                                deletedMembers.push({
                                    nickname: nickname,
                                    link: postLink
                                });
                            }
                        }
                        
                    } catch (e) {
                        continue;
                    }
                }
                
                return deletedMembers;
            """, author_buttons, my_nicknames)
            
            return deleted_members_data
            
        except Exception as e:
            self.logger.error(f"⚠️ JavaScript 처리 실패: {str(e)}")
            return []
    
    def calculate_needed_deleted_posts(self, needed_comments: int, needed_replies: int = 0) -> int:
        """필요한 탈퇴 회원 게시글 수 계산 (답글 35개 제한 고려)"""
        # 댓글은 무한정 가능, 답글은 최대 35개까지
        if needed_replies == 0:
            return 1  # 댓글만 필요하면 1명
        else:
            # 답글 필요시 35개 제한 고려하여 계산
            return max(1, (needed_replies + 34) // 35)  # 올림 계산
    
    # 새로가입 카페 전용 - 닉네임 비교 함수 제거됨

    def find_deleted_members_single_page_fast(self, driver: webdriver.Chrome) -> List[DeletedPost]:
        """현재 페이지에서 탈퇴한 회원의 게시글 찾기 (원본 JavaScript 방식)"""
        deleted_posts = []
        
        try:
            # iframe 상태 초기화
            try:
                driver.switch_to.default_content()
                time.sleep(0.3)
                self.logger.info("🔄 iframe 상태 초기화 완료")
            except:
                pass
            
            # JavaScript로 직접 작성자 버튼 찾기 (빠른 방식)
            author_buttons = []
            
            self.logger.info("🚀 JavaScript 직접 실행으로 작성자 버튼 찾기 시작")
            
            try:
                # JavaScript로 작성자 버튼 직접 추출
                author_buttons = driver.execute_script("""
                    // iframe 내부 확인
                    var buttons = [];
                    
                    // 1. 메인 페이지에서 찾기
                    var mainButtons = document.querySelectorAll('button.nick_btn');
                    if (mainButtons.length > 0) {
                        return Array.from(mainButtons);
                    }
                    
                    // 2. iframe 내부에서 찾기
                    var iframes = document.querySelectorAll('iframe');
                    for (var i = 0; i < iframes.length; i++) {
                        try {
                            var iframeDoc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                            var iframeButtons = iframeDoc.querySelectorAll('button.nick_btn');
                            if (iframeButtons.length > 0) {
                                return Array.from(iframeButtons);
                            }
                        } catch (e) {
                            // 크로스 도메인 등의 이유로 접근 불가능한 iframe은 건너뛰기
                            continue;
                        }
                    }
                    
                    return [];
                """)
                
                if author_buttons and len(author_buttons) > 0:
                    self.logger.info(f"✅ JavaScript로 작성자 버튼 {len(author_buttons)}개 발견")
                else:
                    self.logger.warning("⚠️ JavaScript 방식 실패, 기존 방식으로 시도")
                    # 기존 iframe 방식으로 폴백
                    iframe_found = self.web_driver_manager.switch_to_iframe(driver, "iframe[name='cafe_main'], iframe#cafe_main")
                    if iframe_found:
                        time.sleep(0.5)
                        author_buttons = self._find_author_links(driver)
                        
            except Exception as js_error:
                self.logger.warning(f"⚠️ JavaScript 실행 오류: {str(js_error)} - 기존 방식으로 전환")
                # 기존 iframe 방식으로 폴백
                iframe_found = self.web_driver_manager.switch_to_iframe(driver, "iframe[name='cafe_main'], iframe#cafe_main")
                if iframe_found:
                    time.sleep(0.5)
                    author_buttons = self._find_author_links(driver)
            
            # 작성자 버튼 재시도 (iframe/메인 전환하며)
            if not author_buttons:
                self.logger.info("🔄 작성자 닉네임 버튼 재시도 - iframe/메인 페이지 전환")
                
                if iframe_found:
                    # iframe에서 못찾았으면 메인 페이지에서 시도
                    try:
                        driver.switch_to.default_content()
                        time.sleep(1)
                        self.logger.info("🔍 메인 페이지에서 작성자 닉네임 버튼 재검색")
                        author_buttons = self._find_author_links(driver)
                    except Exception as switch_error:
                        self.logger.warning(f"⚠️ 메인 페이지 전환 실패: {str(switch_error)}")
                else:
                    # 메인에서 못찾았으면 강제로 iframe 시도
                    try:
                        self.logger.info("🔍 강제 iframe 재시도")
                        all_iframes = driver.find_elements(By.TAG_NAME, "iframe")
                        for iframe in all_iframes:
                            try:
                                driver.switch_to.frame(iframe)
                                time.sleep(1)
                                temp_buttons = self._find_author_links(driver)
                                if temp_buttons:
                                    author_buttons = temp_buttons
                                    self.logger.info("✅ 강제 iframe에서 작성자 닉네임 버튼 발견")
                                    break
                                driver.switch_to.default_content()
                            except:
                                continue
                    except Exception as force_error:
                        self.logger.warning(f"⚠️ 강제 iframe 시도 실패: {str(force_error)}")
            
            if not author_buttons:
                self.logger.warning("❌ 작성자 닉네임 버튼을 찾을 수 없습니다.")
                return deleted_posts
                
            self.logger.info(f"🚀 JavaScript로 {len(author_buttons)}명의 탈퇴회원 한 번에 판별 시작...")
            
            # 순수 JavaScript 방식 - 클릭 없이 DOM에서 직접 레벨 아이콘 확인
            try:
                deleted_members_data = driver.execute_script("""
                    // 페이지에서 모든 작성자 정보를 한 번에 수집
                    var deletedMembers = [];
                    
                    // button.nick_btn 요소들을 직접 찾기
                    var authorButtons = document.querySelectorAll('button.nick_btn');
                    
                    // iframe 내부도 확인
                    var iframes = document.querySelectorAll('iframe');
                    for (var k = 0; k < iframes.length; k++) {
                        try {
                            var iframeDoc = iframes[k].contentDocument || iframes[k].contentWindow.document;
                            if (iframeDoc) {
                                var iframeButtons = iframeDoc.querySelectorAll('button.nick_btn');
                                if (iframeButtons.length > 0) {
                                    authorButtons = iframeButtons;
                                    break;
                                }
                            }
                        } catch (e) {
                            continue;
                        }
                    }
                    
                    for (var i = 0; i < authorButtons.length; i++) {
                        try {
                            var button = authorButtons[i];
                            var nickname = button.textContent.trim().split('\\n')[0];
                            
                            // 레벨 아이콘 확인 (클릭 없이 DOM에서 직접 확인!)
                            var levelIcon = null;
                            var parentTr = button.closest('tr');
                            if (parentTr) {
                                // 다양한 레벨 아이콘 선택자 시도
                                levelIcon = parentTr.querySelector('.level_ico, .lv_ico, [class*="level"], [class*="lv"], .ico_level, .grade_ico, [class*="grade"], [class*="member"], img[src*="level"], img[src*="grade"]');
                                
                                // 텍스트에서 등급 정보 확인
                                if (!levelIcon) {
                                    var trText = parentTr.textContent || '';
                                    if (trText.includes('교대역장') || trText.includes('등업대기') || trText.includes('멤버등급') || trText.includes('씨씨') || trText.includes('VIP') || trText.includes('정회원') || trText.includes('새싹')) {
                                        levelIcon = true; // 등급 정보가 있으면 일반 회원
                                    }
                                }
                            }
                            
                            // 레벨 아이콘이 없으면 탈퇴회원
                            if (!levelIcon) {
                                // 게시글 링크 찾기
                                var postLink = null;
                                if (parentTr) {
                                    var linkElement = parentTr.querySelector('a[href*="/articles/"], a[href*="ArticleRead"], a[href*="articleid="]');
                                    if (linkElement) {
                                        postLink = linkElement.href;
                                    }
                                }
                                
                                if (postLink) {
                                    deletedMembers.push({
                                        nickname: nickname,
                                        link: postLink
                                    });
                                }
                            }
                            
                        } catch (e) {
                            // 개별 버튼 처리 실패는 무시하고 계속
                            continue;
                        }
                    }
                    
                    return deletedMembers;
                """)
                
                # JavaScript 결과를 Python 형식으로 변환
                posts_found = 0
                for member_data in deleted_members_data:
                    deleted_post = DeletedPost(
                        title="탈퇴회원 게시글",
                        author=member_data['nickname'],
                        link=member_data['link']
                    )
                    deleted_posts.append(deleted_post)
                    posts_found += 1
                    self.logger.info(f"✅ 탈퇴 회원 #{posts_found}: {member_data['nickname']} (JavaScript 고속 처리)")
                
                checked_authors = len(author_buttons)
                self.logger.info(f"⚡ JavaScript 고속 처리 완료: {posts_found}개 탈퇴 회원 발견 (총 {checked_authors}명 확인)")
                
            except Exception as js_error:
                self.logger.warning(f"⚠️ JavaScript 처리 실패: {str(js_error)} - 기존 방식으로 폴백")
                # 기존 방식으로 폴백 (간단한 방식)
                posts_found = 0
                checked_authors = 0
                
                for author_button in author_buttons[:10]:  # 최대 10개만
                    try:
                        checked_authors += 1
                        nickname_full = author_button.text.strip()
                        nickname = nickname_full.split('\n')[0] if '\n' in nickname_full else nickname_full
                        
                        # 레벨 아이콘 확인으로 탈퇴회원 판별
                        if self._is_deleted_member_by_level_icon(author_button):
                            post_link = self._find_post_link_from_author_button(author_button)
                            if post_link:
                                deleted_post = DeletedPost(
                                    title="탈퇴회원 게시글",
                                    author=nickname,
                                    link=post_link
                                )
                                deleted_posts.append(deleted_post)
                                posts_found += 1
                                self.logger.info(f"✅ 탈퇴 회원 #{posts_found}: {nickname} (폴백 방식)")
                                
                    except Exception as e:
                        continue
                
                self.logger.info(f"📄 폴백 처리 완료: {posts_found}개 탈퇴 회원 발견 (총 {checked_authors}명 확인)")
            
        except Exception as e:
            self.logger.error(f"❌ 탈퇴한 회원 찾기 실패: {str(e)}")
            
        finally:
            # 원래 프레임으로 돌아가기
            try:
                driver.switch_to.default_content()
            except:
                pass
        
        return deleted_posts

    def _find_post_link_from_author_button(self, author_button) -> Optional[str]:
        """작성자 버튼으로부터 게시글 링크 찾기"""
        try:
            # 작성자 버튼의 부모 tr 요소에서 게시글 링크 찾기
            parent_tr = author_button.find_element(By.XPATH, "./ancestor::tr")
            link_element = parent_tr.find_element(By.CSS_SELECTOR, "a[href*='/articles/'], a[href*='ArticleRead'], a[href*='articleid=']")
            return link_element.get_attribute("href")
        except Exception:
            return None

    def _close_author_menu(self, driver: webdriver.Chrome):
        """작성자 메뉴 닫기"""
        try:
            # ESC 키로 닫기
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except:
            # 클릭으로 닫기
            try:
                driver.find_element(By.TAG_NAME, "body").click()
            except:
                pass

    def _extract_post_id_from_link(self, link: str) -> Optional[str]:
        """게시글 링크에서 게시글 ID 추출"""
        try:
            import re
            # /articles/숫자 또는 articleid=숫자 패턴 찾기
            match = re.search(r'/articles/(\d+)|articleid=(\d+)', link)
            if match:
                return match.group(1) or match.group(2)
            return None
        except:
            return None

    def _is_deleted_member_by_level_icon(self, author_button) -> bool:
        """레벨 아이콘으로 탈퇴회원 판별"""
        try:
            # 작성자 버튼의 부모 tr에서 레벨 아이콘 찾기
            parent_tr = author_button.find_element(By.XPATH, "./ancestor::tr")
            
            # 레벨 아이콘 선택자들
            level_selectors = [
                '.level_ico', '.lv_ico', '[class*="level"]', '[class*="lv"]', 
                '.ico_level', '.grade_ico', '[class*="grade"]', '[class*="member"]', 
                'img[src*="level"]', 'img[src*="grade"]'
            ]
            
            # 레벨 아이콘 찾기
            for selector in level_selectors:
                try:
                    level_icon = parent_tr.find_element(By.CSS_SELECTOR, selector)
                    if level_icon:
                        return False  # 레벨 아이콘이 있으면 일반 회원
                except:
                    continue
            
            # 텍스트에서 등급 정보 확인
            tr_text = parent_tr.text
            if any(keyword in tr_text for keyword in ['교대역장', '등업대기', '멤버등급', '씨씨']):
                return False  # 등급 정보가 있으면 일반 회원
            
            # 레벨 아이콘이 없으면 탈퇴회원
            return True
            
        except:
            # 닉네임 span도 못 찾으면 일반 회원으로 간주
            return False


# 전역 탈퇴 회원 탐색기 인스턴스
deleted_member_finder = DeletedMemberFinder()
