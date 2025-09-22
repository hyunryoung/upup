"""
카페 관련 유틸리티 함수들
네이버 카페 작업에 필요한 공통 유틸리티 함수들을 제공합니다.
"""

import re
import time
import logging
from typing import Optional, List, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


class CafeUtils:
    """카페 관련 유틸리티 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_cafe_id_from_url(self, url: str) -> str:
        """URL에서 카페 ID 추출"""
        if not url:
            return ""
        
        if "cafe.naver.com/" in url:
            match = re.search(r'cafe\.naver\.com/([^/?]+)', url)
            if match:
                return match.group(1)
        
        return url.strip()
    
    def get_author_menu_count(self, driver: webdriver.Chrome) -> int:
        """작성자 메뉴 개수 확인"""
        try:
            time.sleep(2)  # 레이어 메뉴 로딩 대기
            
            # ul.layer_list에서 찾기
            try:
                layer_ul = driver.find_element(By.CSS_SELECTOR, "ul.layer_list")
                layer_items = layer_ul.find_elements(By.CSS_SELECTOR, "li.layer_item")
                return len(layer_items)
                
            except:
                # LayerMore 컨테이너에서 찾기
                try:
                    layer_more = driver.find_element(By.CSS_SELECTOR, ".LayerMore")
                    layer_items = layer_more.find_elements(By.CSS_SELECTOR, "li.layer_item")
                    return len(layer_items)
                    
                except:
                    # 전체 페이지에서 layer_button 검색
                    layer_buttons = driver.find_elements(By.CSS_SELECTOR, "button.layer_button")
                    return len(layer_buttons)
        
        except Exception:
            return 0
    
    def is_deleted_member_by_menu_content(self, driver: webdriver.Chrome) -> bool:
        """메뉴 내용이 '게시글 보기' + '블로그보기'인지 확인 (탈퇴회원 판단)"""
        try:
            time.sleep(1)  # 메뉴 로딩 대기
            
            # 메뉴 버튼들의 텍스트 수집
            menu_texts = []
            
            # ul.layer_list에서 찾기
            try:
                layer_ul = driver.find_element(By.CSS_SELECTOR, "ul.layer_list")
                layer_buttons = layer_ul.find_elements(By.CSS_SELECTOR, "button.layer_button")
                for button in layer_buttons:
                    text = button.text.strip()
                    if text:
                        menu_texts.append(text)
                        
            except:
                # LayerMore 컨테이너에서 찾기
                try:
                    layer_more = driver.find_element(By.CSS_SELECTOR, ".LayerMore")
                    layer_buttons = layer_more.find_elements(By.CSS_SELECTOR, "button.layer_button")
                    for button in layer_buttons:
                        text = button.text.strip()
                        if text:
                            menu_texts.append(text)
                            
                except:
                    # 전체 페이지에서 layer_button 검색
                    layer_buttons = driver.find_elements(By.CSS_SELECTOR, "button.layer_button")
                    for button in layer_buttons:
                        text = button.text.strip()
                        if text:
                            menu_texts.append(text)
            
            # 탈퇴회원 기준: '게시글 보기'와 '블로그보기' 2개만 있는 경우
            has_post_view = any("게시글" in text and "보기" in text for text in menu_texts)
            has_blog_view = any("블로그" in text and "보기" in text for text in menu_texts)
            
            if len(menu_texts) == 2 and has_post_view and has_blog_view:
                return True
            
            return False
            
        except Exception:
            return False
    
    def close_author_menu(self, driver: webdriver.Chrome) -> None:
        """작성자 메뉴 닫기"""
        try:
            # 여러 방법으로 레이어 메뉴 닫기 시도
            close_methods = [
                "document.querySelector('.LayerMore').style.display = 'none';",
                "document.querySelector('.member_layer').style.display = 'none';", 
                "document.querySelector('[role=\"menu\"]').style.display = 'none';",
                "document.querySelector('.layer_list').parentElement.style.display = 'none';"
            ]
            
            for method in close_methods:
                try:
                    driver.execute_script(method)
                    break
                except:
                    continue
            
            # ESC 키로도 시도
            try:
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except:
                pass
                
        except Exception as e:
            self.logger.error(f"레이어 메뉴 닫기 실패: {str(e)}")
    
    def find_post_link_from_author_button(self, author_button) -> Optional[str]:
        """작성자 닉네임 버튼에서 해당 게시글 링크 찾기"""
        try:
            # 작성자 버튼의 부모들을 거슬러 올라가서 게시글 링크 찾기
            current_element = author_button
            for step in range(15):  # 최대 15단계까지 부모 요소 탐색
                try:
                    # 현재 요소에서 게시글 링크 찾기
                    post_link_selectors = [
                        "a.article",  # 새로운 구조의 게시글 링크
                        "a[href*='ArticleRead.nhn']",  # 구버전
                        "a[href*='/articles/']",  # 신버전
                        "a[href*='/f-e/cafes/']",  # 신버전 상세
                        "a[href*='articleid=']",  # article ID가 있는 링크
                        "a.article_link",  # 게시글 링크 클래스
                        ".title a",  # 제목 링크
                        ".article_title a",  # 게시글 제목 링크
                        "td a",  # 테이블 셀 내의 링크 (포괄적)
                    ]
                    
                    for selector in post_link_selectors:
                        try:
                            post_links = current_element.find_elements(By.CSS_SELECTOR, selector)
                            for link in post_links:
                                href = link.get_attribute("href")
                                if href and ("articleread" in href.lower() or "articles" in href.lower() or "articleid=" in href.lower()):
                                    return href
                        except:
                            continue
                    
                    # 부모 요소로 이동
                    current_element = current_element.find_element(By.XPATH, "..")
                except:
                    break
            
            return None
            
        except Exception as e:
            self.logger.error(f"게시글 링크 찾기 오류: {str(e)}")
            return None
    
    def calculate_needed_comments(self, current_comments: int, required_comments: int) -> int:
        """필요한 댓글 수 계산"""
        return max(0, required_comments - current_comments)
    
    def calculate_needed_posts(self, current_posts: int, required_posts: int) -> int:
        """필요한 게시글 수 계산"""
        return max(0, required_posts - current_posts)
    
    def calculate_needed_visits(self, current_visits: int, required_visits: int) -> int:
        """필요한 방문 수 계산"""
        return max(0, required_visits - current_visits)
    
    def get_current_page_number(self, driver: webdriver.Chrome) -> int:
        """현재 페이지 번호 확인"""
        try:
            current_page_selectors = [
                "button.btn.number[aria-current='page']",     
                "button.btn.number[aria-pressed='true']",     
                "button[aria-current='page']",                
                "button[aria-pressed='true']",                
                ".Pagination button[aria-current='page']",   
                ".Pagination button[aria-pressed='true']"    
            ]
            
            for selector in current_page_selectors:
                try:
                    current_button = driver.find_element(By.CSS_SELECTOR, selector)
                    if current_button:
                        page_text = current_button.text.strip()
                        if page_text.isdigit():
                            return int(page_text)
                except:
                    continue
            
            return 1  # 기본값
            
        except:
            return 1
    
    def go_to_page(self, driver: webdriver.Chrome, target_page: int) -> bool:
        """지정된 페이지로 이동"""
        try:
            self.logger.info(f"📄 {target_page}페이지로 이동 시도...")
            
            # 페이징 영역 찾기
            pagination_selectors = [
                "div.Pagination",
                "#cafe_content div.SearchBoxLayout.type_bottom div.Pagination",
                "#cafe_content div.Pagination",
                ".SearchBoxLayout .Pagination",
                ".Pagination",
                ".pagination",
                ".paging",
                ".page_navigation"
            ]
            
            for selector in pagination_selectors:
                try:
                    pagination = driver.find_element(By.CSS_SELECTOR, selector)
                    if pagination:
                        # 페이지 버튼 찾기
                        page_buttons = pagination.find_elements(By.CSS_SELECTOR, "button.btn.number")
                        
                        for button in page_buttons:
                            try:
                                button_text = button.text.strip()
                                aria_pressed = button.get_attribute("aria-pressed")
                                aria_current = button.get_attribute("aria-current")
                                
                                # 목표 페이지 번호와 일치하고 현재 페이지가 아닌 경우
                                if (button_text == str(target_page) and 
                                    aria_pressed != "true" and 
                                    aria_current != "page"):
                                    
                                    driver.execute_script("arguments[0].click();", button)
                                    time.sleep(2)
                                    
                                    # 페이지 이동 확인
                                    current_page = self.get_current_page_number(driver)
                                    if current_page == target_page:
                                        self.logger.info(f"✅ {target_page}페이지로 이동 성공")
                                        return True
                                    else:
                                        self.logger.warning(f"⚠️ 페이지 이동 실패: 현재 {current_page}페이지")
                                        return False
                                        
                            except Exception:
                                continue
                        break
                        
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 페이지 이동 실패: {str(e)}")
            return False
    
    def get_max_page_number(self, driver: webdriver.Chrome) -> int:
        """최대 페이지 번호 확인"""
        try:
            # 페이징 영역에서 숫자 버튼들 확인
            page_buttons = driver.find_elements(By.CSS_SELECTOR, "button.btn.number")
            page_numbers = []
            
            for btn in page_buttons:
                try:
                    btn_text = btn.text.strip()
                    if btn_text.isdigit():
                        page_numbers.append(int(btn_text))
                except:
                    continue
            
            if page_numbers:
                max_page = max(page_numbers)
                
                # '다음' 버튼 확인
                try:
                    next_button = driver.find_element(By.CSS_SELECTOR, "button.btn.type_next:not([disabled])")
                    if next_button:
                        # 더 많은 페이지가 있을 수 있음
                        return max_page * 2  # 추정값
                    else:
                        return max_page
                except:
                    return max_page
            else:
                return 1
                
        except Exception as e:
            self.logger.error(f"❌ 최대 페이지 확인 실패: {str(e)}")
            return 1


class PageNavigator:
    """페이지 네비게이션 유틸리티"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def navigate_to_board_url(self, driver: webdriver.Chrome, cafe_numeric_id: str, 
                             board_id: str, page: int = 1) -> bool:
        """게시판 URL로 직접 이동"""
        try:
            board_url = f"https://cafe.naver.com/ca-fe/cafes/{cafe_numeric_id}/menus/{board_id}?size=50&viewType=L&page={page}"
            
            self.logger.info(f"🔗 게시판 직접 이동: {board_url}")
            driver.get(board_url)
            time.sleep(3)
            
            # 페이지 로딩 확인
            current_url = driver.current_url
            if "error" not in current_url.lower():
                self.logger.info("✅ 게시판 페이지 이동 성공")
                return True
            else:
                self.logger.warning("⚠️ 게시판 페이지 오류")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 게시판 이동 실패: {str(e)}")
            return False
    
    def find_author_links_optimized(self, driver: webdriver.Chrome) -> List:
        """최적화된 작성자 링크 찾기"""
        try:
            # JavaScript로 빠른 검색
            author_buttons = driver.execute_script("""
                // 메인 페이지에서 찾기
                var mainButtons = document.querySelectorAll('button.nick_btn');
                if (mainButtons.length > 0) {
                    return Array.from(mainButtons);
                }
                
                // iframe 내부에서 찾기
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
            
            # 폴백: 일반 방법
            return self._find_author_links_fallback(driver)
            
        except Exception as e:
            self.logger.warning(f"⚠️ JavaScript 검색 실패: {str(e)} - 폴백 시도")
            return self._find_author_links_fallback(driver)
    
    def _find_author_links_fallback(self, driver: webdriver.Chrome) -> List:
        """작성자 링크 찾기 폴백 방법"""
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
                        self.logger.info(f"✅ 폴백으로 닉네임 버튼 {len(valid_buttons)}개 발견")
                        return valid_buttons
            except:
                continue
        
        return []


class TextProcessor:
    """텍스트 처리 유틸리티"""
    
    @staticmethod
    def add_random_number(text: str, min_num: int = 1000, max_num: int = 9999) -> str:
        """텍스트에 랜덤 숫자 추가"""
        import random
        random_num = random.randint(min_num, max_num)
        return f"{text} {random_num}"
    
    @staticmethod
    def clean_html_text(html_text: str) -> str:
        """HTML 태그 제거"""
        clean_text = re.sub(r'<[^>]+>', '', html_text)
        clean_text = re.sub(r'&\w+;', ' ', clean_text)
        return clean_text.strip()
    
    @staticmethod
    def extract_numbers_from_text(text: str, pattern: str) -> Optional[int]:
        """텍스트에서 숫자 추출"""
        try:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
            return None
        except:
            return None


# 전역 인스턴스들
cafe_utils = CafeUtils()
page_navigator = PageNavigator()
text_processor = TextProcessor()
