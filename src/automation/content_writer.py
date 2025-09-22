"""
댓글/게시글 자동 작성 모듈
네이버 카페에서 댓글과 게시글을 자동으로 작성합니다.
"""

import re
import time
import random
import logging
from typing import List, Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

try:
    from ..data.models import DeletedPost, CafeInfo, LevelupConditions
except ImportError:
    # 직접 실행 시 절대 import 사용
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from src.data.models import DeletedPost, CafeInfo, LevelupConditions
try:
    from .web_driver import WebDriverManager
except ImportError:
    from src.automation.web_driver import WebDriverManager


class ContentWriter:
    """댓글/게시글 자동 작성 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.web_driver_manager = WebDriverManager()
    
    def _exec_in_cafe_frame(self, driver: webdriver.Chrome, script: str, *args):
        """cafe_main iframe에서 JavaScript 실행"""
        switched = False
        try:
            # iframe으로 진입
            driver.switch_to.frame(driver.find_element(By.CSS_SELECTOR, "iframe#cafe_main, iframe[name='cafe_main']"))
            switched = True
            return driver.execute_script(script, *args)
        except Exception as e:
            self.logger.warning(f"iframe 진입 실패: {e}")
            # iframe 없으면 상위에서 시도
            return driver.execute_script(script, *args)
        finally:
            if switched:
                try:
                    driver.switch_to.default_content()
                except:
                    pass
    
    def _wait_my_tab_loaded(self, driver: webdriver.Chrome):
        """나의활동 탭 로딩 완료 대기"""
        try:
            WebDriverWait(driver, 5).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#cafe_main, iframe[name='cafe_main']"))
            )
            WebDriverWait(driver, 5).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table, ul, .list_area, .ArticleList")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "td.blocked_list, .empty_message"))
                )
            )
            self.logger.info("✅ 나의활동 탭 로딩 완료")
        except:
            self.logger.warning("⚠️ 탭 로딩 확인 실패")
        finally:
            try:
                driver.switch_to.default_content()
            except:
                pass
    
    def _wait_list_reloaded(self, driver: webdriver.Chrome):
        """삭제 후 리스트 재로딩 대기 (staleness 감지)"""
        try:
            # 이전 목록의 tbody 기준으로 staleness 대기
            driver.switch_to.default_content()
            WebDriverWait(driver, 6).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#cafe_main, iframe[name='cafe_main']"))
            )
            
            anchor = None
            for css in ("table tbody", ".ArticleList", ".list_area", "table"):
                els = driver.find_elements(By.CSS_SELECTOR, css)
                if els:
                    anchor = els[0]
                    break
            
            driver.switch_to.default_content()
            
            if anchor:
                try:
                    WebDriverWait(driver, 6).until(EC.staleness_of(anchor))
                    self.logger.info("✅ 리스트 재로딩 감지")
                except:
                    pass
            
            # 재로딩 완료 신호
            self._wait_my_tab_loaded(driver)
            
        except Exception as e:
            self.logger.warning(f"⚠️ 리스트 재로딩 대기 실패: {e}")
            driver.switch_to.default_content()
    
    def _is_empty_list(self, driver: webdriver.Chrome) -> bool:
        """빈 리스트 여부 확인 (빠른 종료용)"""
        try:
            driver.switch_to.default_content()
            WebDriverWait(driver, 5).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#cafe_main, iframe[name='cafe_main']"))
            )
            empty = driver.find_elements(By.CSS_SELECTOR, "td.blocked_list, .empty_message")
            return bool(empty)
        except:
            return False
        finally:
            driver.switch_to.default_content()
    
    def write_comments_to_posts_smart(self, driver: webdriver.Chrome, cafe_info, work_board_id: str,
                                     comment_text: str, needed_comments: int, 
                                     add_random_numbers: bool = False, start_page: int = 1) -> int:
        """
        스마트 탈퇴회원 댓글 작성 (댓글 입력창 없으면 다른 탈퇴회원 자동 탐색)
        
        Args:
            driver: WebDriver 인스턴스
            cafe_info: 카페 정보
            work_board_id: 작업 게시판 ID
            comment_text: 작성할 댓글 내용
            needed_comments: 필요한 댓글 수
            add_random_numbers: 랜덤 숫자 추가 여부
            start_page: 시작 페이지
            
        Returns:
            실제 작성된 댓글 수
        """
        try:
            if not comment_text.strip():
                self.logger.error("❌ 댓글 내용이 설정되지 않았습니다.")
                return 0
            
            if needed_comments <= 0:
                self.logger.info("✅ 이미 댓글 조건을 만족했습니다.")
                return 0
            
            # +1개 추가로 달기
            needed_comments += 1
            
            written_comments = 0
            retry_count = 0
            MAX_RETRY = 3
            
            self.logger.info(f"🎯 스마트 댓글 작성 시작: {needed_comments}개 목표")
            
            # 필요한 댓글 수 달성까지 반복
            while written_comments < needed_comments and retry_count < MAX_RETRY:
                retry_count += 1
                self.logger.info(f"🔄 탈퇴회원 찾기 시도 {retry_count}/{MAX_RETRY}")
                
                # 탈퇴회원 게시글 찾기
                from ..automation.deleted_member_finder import deleted_member_finder
                target_posts = max(1, (needed_comments - written_comments + 4) // 5)  # 여유있게 찾기
                
                deleted_posts = deleted_member_finder.find_deleted_member_posts(
                    driver, cafe_info, work_board_id, start_page, target_posts
                )
                
                if not deleted_posts:
                    self.logger.warning(f"⚠️ 시도 {retry_count}: 탈퇴회원 게시글을 찾을 수 없습니다.")
                    start_page += 5  # 다음 페이지 범위로 이동
                    continue
                
                # 찾은 게시글들에 댓글 시도
                for deleted_post in deleted_posts:
                    if written_comments >= needed_comments:
                        break
                    
                    # 게시글 페이지로 이동
                    if self._navigate_to_post(driver, deleted_post.link):
                        # 댓글 입력창 검증
                        if self._check_comment_input_available(driver):
                            # 댓글 작성 가능 → 작성 시도
                            remaining_comments = needed_comments - written_comments
                            comments_to_write = min(5, remaining_comments)  # 한 게시글에 최대 5개
                            
                            post_written = self._write_comments_to_single_post(
                                driver, comment_text, comments_to_write, add_random_numbers
                            )
                            written_comments += post_written
                            
                            if post_written > 0:
                                self.logger.info(f"✅ {deleted_post.author} 게시글: {post_written}개 댓글 작성 완료")
                            else:
                                self.logger.warning(f"⚠️ {deleted_post.author} 게시글: 댓글 작성 실패")
                        else:
                            # 댓글 입력창 없음 → 건너뛰고 다음 게시글로
                            self.logger.warning(f"⚠️ {deleted_post.author} 게시글: 댓글 입력 불가 - 건너뜀")
                            continue
                    else:
                        self.logger.warning(f"⚠️ {deleted_post.author} 게시글: 페이지 이동 실패")
                
                # 목표 달성 확인
                if written_comments >= needed_comments:
                    self.logger.info(f"🎉 목표 달성! {written_comments}개 댓글 작성 완료")
                    break
                else:
                    remaining = needed_comments - written_comments
                    self.logger.info(f"🔄 추가 필요: {remaining}개 댓글 (다음 탈퇴회원 찾기)")
                    start_page += 3  # 다음 페이지 범위로 이동
            
            if written_comments < needed_comments:
                self.logger.warning(f"⚠️ 목표 미달성: {written_comments}/{needed_comments}개 작성 (최대 재시도 완료)")
            
            return written_comments
            
        except Exception as e:
            self.logger.error(f"❌ 스마트 댓글 작성 중 예외: {str(e)}")
            return written_comments
    
    def _check_comment_input_available(self, driver: webdriver.Chrome) -> bool:
        """댓글 입력창 사용 가능 여부 확인"""
        try:
            # iframe 진입 시도
            try:
                iframe = driver.find_element(By.CSS_SELECTOR, "iframe#cafe_main, iframe[name='cafe_main']")
                driver.switch_to.frame(iframe)
            except:
                pass  # iframe 없으면 메인에서 확인
            
            # 댓글 입력창 찾기
            selectors = [
                "textarea[name='content']", 
                "#comment_content", 
                "textarea[placeholder*='댓글']",
                "textarea[placeholder*='내용']",
                "textarea.input_text"
            ]
            
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            self.logger.info(f"✅ 댓글 입력창 확인됨: {selector}")
                            return True
                except:
                    continue
            
            # 댓글 차단 메시지 확인
            blocking_messages = [
                "댓글을 작성할 수 없습니다",
                "댓글이 차단되었습니다", 
                "댓글 작성 권한이 없습니다",
                "로그인이 필요합니다"
            ]
            
            page_text = driver.page_source
            for message in blocking_messages:
                if message in page_text:
                    self.logger.warning(f"⚠️ 댓글 차단 감지: {message}")
                    return False
            
            self.logger.warning("⚠️ 댓글 입력창을 찾을 수 없습니다")
            return False
            
        except Exception as e:
            self.logger.warning(f"⚠️ 댓글 입력창 확인 실패: {str(e)}")
            return False
        finally:
            try:
                driver.switch_to.default_content()
            except:
                pass
    
    def write_comments_to_posts(self, driver: webdriver.Chrome, deleted_posts: List[DeletedPost], 
                               comment_text: str, needed_comments: int, 
                               add_random_numbers: bool = False) -> int:
        """
        탈퇴 회원 게시글에 댓글 작성
        
        Args:
            driver: WebDriver 인스턴스
            deleted_posts: 탈퇴 회원 게시글 목록
            comment_text: 작성할 댓글 내용
            needed_comments: 필요한 댓글 수
            add_random_numbers: 랜덤 숫자 추가 여부
            
        Returns:
            실제 작성된 댓글 수
        """
        try:
            if not comment_text.strip():
                self.logger.error("❌ 댓글 내용이 설정되지 않았습니다.")
                return 0
            
            if not deleted_posts:
                self.logger.error("❌ 댓글을 작성할 탈퇴 회원 게시글이 없습니다.")
                return 0
            
            if needed_comments <= 0:
                self.logger.info("✅ 이미 댓글 조건을 만족했습니다.")
                return 0
            
            # +1개 추가로 달기
            needed_comments += 1
            
            # 게시글당 댓글 수 계산
            total_posts = len(deleted_posts)
            if needed_comments >= total_posts:
                comments_per_post = needed_comments // total_posts
                extra_comments = needed_comments % total_posts
            else:
                comments_per_post = 0
                extra_comments = needed_comments
            
            self.logger.info(f"💬 댓글 작성 계획: {needed_comments}개 댓글을 {total_posts}개 게시글에 배분")
            self.logger.info(f"📝 게시글당 {comments_per_post}개씩, {extra_comments}개 게시글에 1개씩 추가")
            
            written_comments = 0
            
            for i, deleted_post in enumerate(deleted_posts):
                if written_comments >= needed_comments:
                    break
                
                # 현재 게시글에 작성할 댓글 수 결정
                comments_to_write = comments_per_post
                if i < extra_comments:
                    comments_to_write += 1
                
                if comments_to_write == 0:
                    continue
                
                self.logger.info(f"📝 게시글 {i+1}/{total_posts}: '{deleted_post.author}' 작성자의 게시글에 {comments_to_write}개 댓글 작성")
                
                # 게시글 페이지로 이동
                if self._navigate_to_post(driver, deleted_post.link):
                    # 댓글 작성
                    post_written = self._write_comments_to_single_post(
                        driver, comment_text, comments_to_write, add_random_numbers
                    )
                    written_comments += post_written
                    
                    if post_written > 0:
                        self.logger.info(f"✅ 게시글 {i+1}: {post_written}개 댓글 작성 완료")
                    else:
                        self.logger.warning(f"⚠️ 게시글 {i+1}: 댓글 작성 실패")
                else:
                    self.logger.warning(f"⚠️ 게시글 {i+1}: 페이지 이동 실패")
                
                # 다음 게시글로 이동하기 전 잠시 대기
                time.sleep(2)
            
            self.logger.info(f"💬 댓글 작성 완료: 총 {written_comments}개 작성됨")
            return written_comments
            
        except Exception as e:
            self.logger.error(f"❌ 댓글 작성 중 오류: {str(e)}")
            return 0

    def write_replies_to_posts(self, driver: webdriver.Chrome, deleted_posts: List[DeletedPost], 
                              post_title: str, post_content: str, needed_replies: int, 
                              add_random_numbers: bool = False) -> int:
        """탈퇴 회원 게시글에 답글 작성 (원본 방식 - 새 탭 처리)"""
        try:
            self.logger.info(f"📝 답글 작성 계획: {needed_replies}개 답글을 {len(deleted_posts)}개 게시글에 배분")
            
            if needed_replies <= 0:
                return 0
            
            # 답글 배분 계산
            total_posts = min(len(deleted_posts), needed_replies)
            replies_per_post = needed_replies // total_posts
            extra_replies = needed_replies % total_posts
            
            self.logger.info(f"📝 게시글당 {replies_per_post}개씩, {extra_replies}개 게시글에 1개씩 추가")
            
            written_replies = 0
            
            for i, deleted_post in enumerate(deleted_posts):
                if written_replies >= needed_replies:
                    break
                
                # 현재 게시글에 작성할 답글 수 결정
                replies_to_write = replies_per_post
                if i < extra_replies:
                    replies_to_write += 1
                
                if replies_to_write == 0:
                    continue
                
                self.logger.info(f"📝 게시글 {i+1}/{total_posts}: '{deleted_post.author}' 작성자의 게시글에 {replies_to_write}개 답글 작성")
                
                # 게시글 페이지로 이동
                if self._navigate_to_post(driver, deleted_post.link):
                    # 답글 작성 (새 탭 처리)
                    post_written = self._write_replies_to_single_post(
                        driver, post_title, post_content, replies_to_write, add_random_numbers
                    )
                    written_replies += post_written
                    
                    if post_written > 0:
                        self.logger.info(f"✅ 게시글 {i+1}: {post_written}개 답글 작성 완료")
                    else:
                        self.logger.warning(f"⚠️ 게시글 {i+1}: 답글 작성 실패")
                else:
                    self.logger.warning(f"⚠️ 게시글 {i+1}: 페이지 이동 실패")
                
                # 다음 게시글로 이동하기 전 잠시 대기
                time.sleep(2)
            
            self.logger.info(f"📝 답글 작성 완료: 총 {written_replies}개 작성됨")
            return written_replies
            
        except Exception as e:
            self.logger.error(f"❌ 답글 작성 중 오류: {str(e)}")
            return 0
    
    def _navigate_to_post(self, driver: webdriver.Chrome, post_url: str) -> bool:
        """게시글 페이지로 이동 (프레임+본문 로딩 대기)"""
        try:
            self.logger.info(f"🔗 게시글로 이동: {post_url}")
            driver.get(post_url)
            
            # 프레임+본문 로딩 대기 (time.sleep 대신)
            try:
                # 1) 프레임 대기
                WebDriverWait(driver, 20).until(
                    EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#cafe_main, iframe[name='cafe_main']"))
                )
                
                # 2) 본문 요소 대기
                WebDriverWait(driver, 15).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".ArticleContent, .article_container, #app")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "textarea, [contenteditable='true']"))
                    )
                )
                
                # 3) 댓글 입력창까지 완전 로딩 대기 (스마트 대기 - 최대 5초)
                try:
                    WebDriverWait(driver, 5).until(  # 10초 → 5초로 단축
                        EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[placeholder*='댓글'], .comment_write, .comment-input"))
                    )
                    self.logger.info("✅ 댓글 입력창 로딩 확인 (스마트 대기)")
                except:
                    self.logger.warning("⚠️ 댓글 입력창 로딩 미확인 (계속 진행)")
                
                driver.switch_to.default_content()
                self.logger.info("✅ 게시글 페이지 이동 성공")
                return True
                
            except Exception as loading_error:
                self.logger.warning(f"프레임/본문 로딩 실패: {loading_error}")
                driver.switch_to.default_content()
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 게시글 페이지 이동 실패: {str(e)}")
            driver.switch_to.default_content()
            return False
    
    def _write_comments_to_single_post(self, driver: webdriver.Chrome, comment_text: str, 
                                      comment_count: int, add_random_numbers: bool) -> int:
        """단일 게시글에 여러 댓글 작성"""
        written_count = 0
        
        try:
            for i in range(comment_count):
                # 댓글 내용 준비
                final_comment = comment_text
                if add_random_numbers:
                    random_num = random.randint(1000, 9999)
                    final_comment = f"{comment_text} {random_num}"
                
                # 댓글 작성
                if self._write_single_comment(driver, final_comment):
                    written_count += 1
                    self.logger.info(f"✅ 댓글 {i+1}/{comment_count} 작성 완료")
                    
                    # 댓글 간 딜레이 (5초로 고정)
                    if i < comment_count - 1:  # 마지막 댓글이 아니면 대기
                        time.sleep(5)
                else:
                    self.logger.warning(f"⚠️ 댓글 {i+1}/{comment_count} 작성 실패")
            
            return written_count
            
        except Exception as e:
            self.logger.error(f"❌ 단일 게시글 댓글 작성 실패: {str(e)}")
            return written_count
    
    def _write_single_comment(self, driver: webdriver.Chrome, comment_text: str) -> bool:
        """단일 댓글 작성 (간단한 직접 방식)"""
        try:
            # 1. iframe 진입 시도
            try:
                iframe = driver.find_element(By.CSS_SELECTOR, "iframe#cafe_main, iframe[name='cafe_main']")
                driver.switch_to.frame(iframe)
                self.logger.info("✅ iframe 진입 성공")
            except:
                self.logger.info("ℹ️ iframe 없음 - 메인에서 진행")
            
            # 2. 댓글 입력창 찾기
            comment_input = None
            selectors = [
                "textarea[name='content']", 
                "#comment_content", 
                "textarea[placeholder*='댓글']",
                "textarea[placeholder*='내용']",
                "textarea.input_text"
            ]
            
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            comment_input = element
                            self.logger.info(f"✅ 댓글 입력창 발견: {selector}")
                            break
                    if comment_input:
                        break
                except:
                    continue
            
            if not comment_input:
                self.logger.warning("❌ 댓글 입력창을 찾을 수 없습니다")
                return False
            
            # 3. 댓글 입력
            comment_input.click()
            comment_input.clear()
            comment_input.send_keys(comment_text)
            self.logger.info("✅ 댓글 내용 입력 완료")
            
            # 4. 등록 버튼 찾기 및 클릭
            submit_selectors = [
                'button[type="submit"]',
                '.btn_register',
                '.btn_comment',
                'button[onclick*="submit"]',
                'input[type="submit"]'
            ]
            
            submit_btn = None
            for selector in submit_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            submit_btn = element
                            self.logger.info(f"✅ 등록 버튼 발견: {selector}")
                            break
                    if submit_btn:
                        break
                except:
                    continue
            
            if not submit_btn:
                self.logger.warning("❌ 등록 버튼을 찾을 수 없습니다")
                return False
            
            # 5. 등록 버튼 클릭
            submit_btn.click()
            time.sleep(1)
            self.logger.info("✅ 댓글 등록 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 댓글 작성 실패: {str(e)}")
            return False
        finally:
            # iframe에서 나오기
            try:
                driver.switch_to.default_content()
            except:
                pass
    
    def _write_comment_fallback(self, driver: webdriver.Chrome, comment_text: str) -> bool:
        """댓글 작성 폴백 방식 (빠른 버전)"""
        try:
            # 빠른 iframe 전환
            try:
                iframe = driver.find_element(By.CSS_SELECTOR, "iframe[name='cafe_main'], iframe#cafe_main")
                driver.switch_to.frame(iframe)
            except:
                pass  # iframe 없으면 메인에서 진행
            
            # 빠른 입력창 찾기 (원래 버전)
            input_selectors = ["textarea[name='content']", "#comment_content", "textarea[placeholder*='댓글']"]
            comment_input = None
            
            for selector in input_selectors:
                try:
                    comment_input = driver.find_element(By.CSS_SELECTOR, selector)
                    if comment_input.is_displayed():
                        break
                except:
                    continue
            
            if not comment_input:
                return False
            
            # 빠른 입력
            comment_input.click()
            comment_input.clear()
            comment_input.send_keys(comment_text)
            
            # 빠른 등록 버튼 클릭
            submit_selectors = ["button[type='submit']", ".btn_register", ".btn_comment"]
            for selector in submit_selectors:
                try:
                    submit_btn = driver.find_element(By.CSS_SELECTOR, selector)
                    if submit_btn.is_displayed():
                        submit_btn.click()
                        time.sleep(1)
                        self.logger.info("✅ 폴백 댓글 작성 성공")
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.warning(f"❌ 폴백 댓글 작성 실패: {str(e)}")
            return False
        finally:
            try:
                driver.switch_to.default_content()
            except:
                pass
    
    def write_post_to_target_board(self, driver: webdriver.Chrome, cafe_info: CafeInfo, 
                                  target_board_id: str, post_title: str, post_content: str,
                                  add_random_numbers: bool = False) -> bool:
        """
        목표 게시판에 게시글 작성
        
        Args:
            driver: WebDriver 인스턴스
            cafe_info: 카페 정보
            target_board_id: 목표 게시판 ID
            post_title: 게시글 제목
            post_content: 게시글 내용
            add_random_numbers: 랜덤 숫자 추가 여부
            
        Returns:
            작성 성공 여부
        """
        try:
            # 카페 숫자 ID 추출
            cafe_numeric_id = self._extract_cafe_numeric_id(driver, cafe_info)
            if not cafe_numeric_id:
                return False
            
            # 목표 게시판 글쓰기 페이지로 이동 (올바른 URL 형태)
            write_url = f"https://cafe.naver.com/ca-fe/cafes/{cafe_numeric_id}/menus/{target_board_id}/articles/write?boardType=L"
            
            self.logger.info(f"📝 목표 게시판 글쓰기 페이지로 이동: {write_url}")
            driver.get(write_url)
            time.sleep(5)
            
            # 글쓰기 권한 확인
            if not self._check_write_permission(driver):
                self.logger.warning("❌ 글쓰기 권한이 없습니다.")
                return False
            
            # 제목 입력
            final_title = post_title
            if add_random_numbers:
                random_num = random.randint(1000, 9999)
                final_title = f"{post_title} {random_num}"
            
            if not self._input_post_title(driver, final_title):
                return False
            
            # 내용 입력
            final_content = post_content
            if add_random_numbers:
                random_num = random.randint(1000, 9999)
                final_content = f"{post_content} {random_num}"
            
            if not self._input_post_content(driver, final_content):
                return False
            
            # 게시글 등록
            if self._submit_post(driver):
                self.logger.info("✅ 게시글 작성 성공")
                return True
            else:
                self.logger.warning("❌ 게시글 등록 실패")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ 게시글 작성 중 오류: {str(e)}")
            return False
    
    def _extract_cafe_numeric_id(self, driver: webdriver.Chrome, cafe_info: CafeInfo) -> Optional[str]:
        """카페의 숫자 ID 추출"""
        try:
            if cafe_info.numeric_id:
                return cafe_info.numeric_id
            
            cafe_url = f"https://cafe.naver.com/{cafe_info.cafe_id}"
            driver.get(cafe_url)
            time.sleep(3)
            
            page_source = driver.page_source
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
                    cafe_info.numeric_id = cafe_id  # 캐시
                    return cafe_id
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 카페 숫자 ID 추출 실패: {str(e)}")
            return None
    
    def _check_write_permission(self, driver: webdriver.Chrome) -> bool:
        """글쓰기 권한 확인"""
        try:
            current_url = driver.current_url
            page_text = driver.page_source
            
            # URL에 write가 있고 접근되었다면 권한 있음
            if "write" in current_url and "cafes" in current_url:
                self.logger.info("✅ 글쓰기 페이지 접근 성공 - 권한 확인")
                return True
            
            # 권한 제한 메시지 확인
            restriction_messages = [
                "등급이 부족", "글쓰기 권한이 없습니다", "등급 조건을 만족",
                "레벨업이 필요", "등급이 되시면", "권한이 없음"
            ]
            
            for msg in restriction_messages:
                if msg in page_text:
                    self.logger.warning(f"❌ 글쓰기 권한 제한: '{msg}'")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 글쓰기 권한 확인 실패: {str(e)}")
            return False
    
    def _input_post_title(self, driver: webdriver.Chrome, title: str) -> bool:
        """게시글 제목 입력"""
        try:
            # iframe 전환 시도
            if not self.web_driver_manager.switch_to_iframe(driver, "cafe_main"):
                self.logger.warning("⚠️ iframe 전환 실패, 메인 페이지에서 시도")
            
            # 제목 입력창 찾기
            title_input_selectors = [
                "input[name='subject']",
                "input[placeholder*='제목']",
                "#subject",
                ".title_input",
                "input[type='text'][placeholder*='제목']"
            ]
            
            title_input = None
            for selector in title_input_selectors:
                try:
                    title_input = driver.find_element(By.CSS_SELECTOR, selector)
                    if title_input.is_displayed() and title_input.is_enabled():
                        break
                except:
                    continue
            
            if not title_input:
                self.logger.error("❌ 제목 입력창을 찾을 수 없습니다.")
                return False
            
            # 제목 입력
            title_input.clear()
            title_input.send_keys(title)
            time.sleep(1)
            
            self.logger.info(f"✅ 제목 입력 완료: {title}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 제목 입력 실패: {str(e)}")
            return False
    
    def _input_post_content(self, driver: webdriver.Chrome, content: str) -> bool:
        """게시글 내용 입력"""
        try:
            # 스마트 에디터 또는 일반 텍스트 영역 찾기
            content_input_selectors = [
                "textarea[name='content']",
                "div[contenteditable='true']",
                ".se-awp-content",
                ".smart_editor textarea",
                "#content",
                ".content_input"
            ]
            
            content_input = None
            for selector in content_input_selectors:
                try:
                    content_input = driver.find_element(By.CSS_SELECTOR, selector)
                    if content_input.is_displayed():
                        break
                except:
                    continue
            
            if not content_input:
                self.logger.error("❌ 내용 입력창을 찾을 수 없습니다.")
                return False
            
            # 내용 입력
            if content_input.tag_name.lower() == "textarea":
                content_input.clear()
                content_input.send_keys(content)
            else:
                # contenteditable div의 경우
                driver.execute_script("arguments[0].innerHTML = arguments[1];", content_input, content)
            
            time.sleep(1)
            self.logger.info(f"✅ 내용 입력 완료: {content[:50]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 내용 입력 실패: {str(e)}")
            return False
    
    def _submit_post(self, driver: webdriver.Chrome) -> bool:
        """게시글 등록"""
        try:
            # 등록 버튼 찾기
            submit_button_selectors = [
                "button[type='submit']",
                ".btn_register",
                ".btn_write",
                "button[onclick*='submit']",
                "input[type='submit']",
                "button[class*='submit']",
                "button[class*='register']"
            ]
            
            submit_button = None
            for selector in submit_button_selectors:
                try:
                    submit_button = driver.find_element(By.CSS_SELECTOR, selector)
                    if submit_button.is_displayed() and submit_button.is_enabled():
                        break
                except:
                    continue
            
            if not submit_button:
                self.logger.error("❌ 등록 버튼을 찾을 수 없습니다.")
                return False
            
            # 등록 버튼 클릭
            self.web_driver_manager.safe_click(driver, submit_button)
            time.sleep(3)
            
            # 등록 성공 확인 (URL 변화 또는 성공 메시지)
            current_url = driver.current_url
            if "write" not in current_url or "success" in current_url.lower():
                self.logger.info("✅ 게시글 등록 성공")
                return True
            else:
                self.logger.warning("⚠️ 게시글 등록 실패")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ 게시글 등록 실패: {str(e)}")
            return False
        finally:
            self.web_driver_manager.switch_to_default_content(driver)
    
    def delete_created_comments_and_posts_optimized(self, driver: webdriver.Chrome, cafe_info: CafeInfo) -> bool:
        """댓글과 게시글 통합 삭제 (초고속 최적화)"""
        try:
            self.logger.info("🗑️ 댓글+게시글 통합 삭제 시작...")
            
            # 카페 메인으로 이동 (빠른 이동)
            cafe_main_url = cafe_info.url
            driver.get(cafe_main_url)
            time.sleep(1)  # 3초 → 1초
            
            # 1. 나의활동 한 번만 클릭
            if not self._click_my_activity(driver):
                return False
            
            # 나의활동 페이지 안정화 대기 (여유롭게)
            time.sleep(5)
            
            success = True
            
            # 2. 댓글 탭에서 댓글 삭제
            self.logger.info("💬 댓글 삭제 중...")
            if not self._click_my_comments(driver):
                self.logger.warning("⚠️ 댓글 탭 클릭 실패")
            else:
                # 빈 리스트 체크 (빠른 종료)
                if self._is_empty_list(driver):
                    self.logger.info("ℹ️ 작성한 댓글이 없습니다 - 건너뛰기")
                else:
                    # 댓글 리스트 페이지 로딩 완료 대기
                    self.logger.info("⏳ 댓글 페이지 로딩 완료 대기...")
                    time.sleep(3)
                    success &= self._execute_comment_deletion(driver)
            
            # 3. 게시글 탭으로 전환 (모든 컨텍스트 시도)
            driver.switch_to.default_content()
            self._wait_my_tab_loaded(driver)
            self.logger.info("📝 게시글 삭제 중...")
            if not self._open_my_posts_anywhere(driver, reopen_if_needed=True):
                self.logger.warning("⚠️ 게시글 탭 전환 실패")
            else:
                # 빈 리스트 체크 (빠른 종료)
                if self._is_empty_list(driver):
                    self.logger.info("ℹ️ 작성한 게시글이 없습니다 - 건너뛰기")
                else:
                    # 게시글 리스트 페이지 로딩 완료 대기
                    self.logger.info("⏳ 게시글 페이지 로딩 완료 대기...")
                    time.sleep(3)
                    success &= self._execute_post_deletion(driver)
            
            self.logger.info("✅ 통합 삭제 완료")
            return success
            
        except Exception as e:
            self.logger.error(f"❌ 통합 삭제 중 오류: {str(e)}")
            return False
    
    def _click_posts_tab_in_same_page(self, driver: webdriver.Chrome) -> bool:
        """같은 나의활동 페이지에서 게시글 탭으로 전환 (HTML 분석 기반)"""
        try:
            # HTML 분석: 작성글 탭 클릭 (정확한 선택자)
            posts_tab_selectors = [
                "a.link_sort:not(.on)",  # 현재 활성화되지 않은 탭 (작성글 탭)
                "//a[@class='link_sort'][contains(text(), '작성글')]",  
                "a.link_sort",
                "//a[contains(text(), '작성글')]"
            ]
            
            for i, selector in enumerate(posts_tab_selectors):
                try:
                    self.logger.info(f"🔍 같은 페이지 작성글 탭 시도 {i+1}/4: {selector}")
                    
                    if selector.startswith("//"):
                        posts_tab = driver.find_element(By.XPATH, selector)
                    else:
                        posts_tab = driver.find_element(By.CSS_SELECTOR, selector)
                    
                    self.logger.info(f"✅ 요소 발견: '{posts_tab.text}' (표시됨: {posts_tab.is_displayed()})")
                    
                    if posts_tab.is_displayed() and "작성글" in posts_tab.text:
                        posts_tab.click()
                        self.logger.info("✅ 게시글 탭으로 전환 성공")
                        
                        # 탭 로딩 완료 대기 (sleep 제거)
                        self._wait_my_tab_loaded(driver)
                        return True
                except Exception as e:
                    self.logger.warning(f"⚠️ 선택자 {i+1}번 실패: {str(e)}")
                    continue
            
            # 모든 선택자 실패 시 페이지 링크 확인
            try:
                self.logger.error("❌ 모든 작성글 탭 선택자 실패! 현재 페이지 링크 확인:")
                links = driver.find_elements(By.TAG_NAME, "a")
                for link in links[:15]:  # 처음 15개만
                    href = link.get_attribute("href") or ""
                    text = link.text.strip()
                    if "작성글" in text or "게시글" in text or "article" in href.lower():
                        self.logger.info(f"🔗 발견된 링크: '{text}' → {href}")
            except:
                pass
            
            self.logger.error("❌ 게시글 탭을 찾을 수 없습니다")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 게시글 탭 전환 실패: {str(e)}")
            return False

    def delete_created_comments(self, driver: webdriver.Chrome, cafe_info: CafeInfo) -> bool:
        """생성된 댓글 삭제 (레거시 - 통합 삭제 사용)"""
        return self.delete_created_comments_and_posts_optimized(driver, cafe_info)
    
    def delete_created_posts(self, driver: webdriver.Chrome, cafe_info: CafeInfo) -> bool:
        """생성된 게시글 삭제 (레거시 - 통합 삭제 사용)"""
        return True  # 통합 삭제에서 이미 처리됨
    
    def _click_my_activity(self, driver: webdriver.Chrome) -> bool:
        """나의활동 버튼 클릭 (모달 처리 포함)"""
        try:
            # 먼저 방해 요소 제거 (모달/팝업 닫기)
            try:
                # dim 레이어 제거
                driver.execute_script("""
                    var dimElements = document.querySelectorAll('#dim, .dim_open, .modal, .popup');
                    dimElements.forEach(function(el) { 
                        el.style.display = 'none'; 
                        el.remove(); 
                    });
                """)
                
                # 혹시 있을 Alert 닫기
                try:
                    alert = driver.switch_to.alert
                    alert.accept()
                except:
                    pass
                    
            except Exception as cleanup_error:
                self.logger.debug(f"모달 정리 시도: {cleanup_error}")
            
            my_activity_selectors = [
                ("xpath", "//button[contains(text(), '나의활동')]"),
                ("xpath", "//button[@onclick='showMyAction();']"),
                ("css", "li.tit-action button"),
                ("css", "button.Sidebar__button"),
            ]
            
            for selector_type, selector_value in my_activity_selectors:
                try:
                    if selector_type == "xpath":
                        my_activity_btn = WebDriverWait(driver, 2).until(  # 8초 → 2초
                            EC.element_to_be_clickable((By.XPATH, selector_value))
                        )
                    else:
                        my_activity_btn = WebDriverWait(driver, 2).until(  # 8초 → 2초
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector_value))
                        )
                    
                    # JavaScript 클릭으로 모달 우회
                    driver.execute_script("arguments[0].click();", my_activity_btn)
                    time.sleep(1)  # 2초 → 1초
                    self.logger.info("✅ 나의활동 클릭 성공")
                    return True
                except TimeoutException:
                    continue
            
            self.logger.error("❌ 나의활동 버튼을 찾을 수 없습니다.")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 나의활동 클릭 실패: {str(e)}")
            return False
    
    def _click_my_comments(self, driver: webdriver.Chrome) -> bool:
        """내가 쓴 댓글 클릭"""
        try:
            # HTML 분석 기반 정확한 선택자
            comment_selectors = [
                ("css", "a.Sidebar_btn_text__8ZGCR[href*='tab=comments']"),  # HTML에서 확인된 정확한 선택자
                ("xpath", "//a[contains(text(), '내가 쓴 댓글')]"),
                ("css", "a[href*='tab=comments']"),
            ]
            
            for selector_type, selector_value in comment_selectors:
                try:
                    if selector_type == "xpath":
                        comment_link = WebDriverWait(driver, 2).until(  # 8초 → 2초
                            EC.element_to_be_clickable((By.XPATH, selector_value))
                        )
                    else:
                        comment_link = WebDriverWait(driver, 2).until(  # 8초 → 2초
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector_value))
                        )
                    
                    comment_link.click()
                    self.logger.info("✅ 내가 쓴 댓글 클릭 성공")
                    
                    # 탭 로딩 완료 대기 (sleep 제거)
                    self._wait_my_tab_loaded(driver)
                    return True
                except TimeoutException:
                    continue
            
            self.logger.error("❌ 내가 쓴 댓글 링크를 찾을 수 없습니다.")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 내가 쓴 댓글 클릭 실패: {str(e)}")
            return False
    
    def _click_my_posts(self, driver: webdriver.Chrome) -> bool:
        """내가쓴 게시글 클릭"""
        try:
            # HTML 분석 기반 정확한 선택자
            my_posts_selectors = [
                ("xpath", "//a[contains(text(), '내가쓴 작성글')]"),     # 수정: 작성글
                ("xpath", "//a[contains(text(), '작성글')]"),           # 수정: 작성글
                ("xpath", "//a[contains(text(), '내가 쓴 작성글')]"),   # 수정: 작성글
                ("xpath", "//a[contains(@href, 'articles')]"), 
                ("css", "a[href*='tab=articles']"),
                ("css", "a.Sidebar_btn_text__8ZGCR[href*='tab=articles']"),
                ("css", "a[onclick*='article']"),
                ("xpath", "//a[contains(text(), '내가쓴 게시글')]"),     # 기존 유지
                ("xpath", "//a[contains(text(), '게시글')]"),           # 기존 유지
                ("xpath", "//a[contains(text(), '내가 쓴')]"),
                ("css", "a[href*='boardtype=L']"),
                ("css", "a[href*='articles']")
            ]
            
            for i, (selector_type, selector_value) in enumerate(my_posts_selectors):
                try:
                    self.logger.info(f"🔍 작성글 탭 시도 {i+1}/12: {selector_type} = {selector_value}")
                    
                    if selector_type == "xpath":
                        my_posts_btn = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, selector_value))
                        )
                    else:
                        my_posts_btn = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector_value))
                        )
                    
                    my_posts_btn.click()
                    time.sleep(1)
                    self.logger.info(f"✅ 내가쓴 작성글 클릭 성공 (선택자 {i+1}번)")
                    return True
                except TimeoutException:
                    self.logger.warning(f"⚠️ 선택자 {i+1}번 실패: {selector_value}")
                    continue
                except Exception as e:
                    self.logger.warning(f"⚠️ 선택자 {i+1}번 오류: {str(e)}")
                    continue
            
            # 모든 선택자 실패 시 페이지 HTML 일부 출력
            try:
                self.logger.error("❌ 모든 게시글 탭 선택자 실패! 현재 페이지 링크 확인:")
                links = driver.find_elements(By.TAG_NAME, "a")
                for link in links[:10]:  # 처음 10개만
                    href = link.get_attribute("href") or ""
                    text = link.text.strip()
                    if "게시글" in text or "article" in href.lower():
                        self.logger.info(f"🔗 발견된 링크: '{text}' → {href}")
            except:
                pass
            
            self.logger.error("❌ 내가쓴 작성글 메뉴를 찾을 수 없습니다.")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ 내가쓴 게시글 클릭 실패: {str(e)}")
            return False
    
    def _execute_comment_deletion(self, driver: webdriver.Chrome) -> bool:
        """댓글 삭제 실행 (원본 방식 - while 루프 + 프레임 관리)"""
        try:
            deleted_count = 0
            consecutive_errors = 0
            
            # 원본 방식: while True 반복 루프
            while True:
                if consecutive_errors >= 3:
                    self.logger.warning("⚠️ 연속 에러 3회 - 댓글 삭제 중단")
                    break
                
                try:
                    # 매 루프마다 프레임 상태 초기화
                    driver.switch_to.default_content()
                    
                    # iframe 진입
                    WebDriverWait(driver, 10).until(
                        EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#cafe_main"))
                    )
                    
                    # 페이지 로딩 대기
                    time.sleep(3)
                    
                    # 체크박스 존재 확인
                    has_checkboxes = False
                    
                    # 원본 방식: label[for='chk_all'] 클릭 (더 안전)
                    try:
                        label = driver.find_element(By.CSS_SELECTOR, "label[for='chk_all']")
                        label.click()
                        has_checkboxes = True
                        time.sleep(0.5)
                    except:
                        # 개별 체크박스 선택 (원본 방식)
                        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'].input_check[id^='check_comment_']")
                        if checkboxes:
                            has_checkboxes = True
                            for cb in checkboxes[:5]:
                                try:
                                    checkbox_id = cb.get_attribute('id')
                                    if checkbox_id:
                                        label = driver.find_element(By.CSS_SELECTOR, f"label[for='{checkbox_id}']")
                                        label.click()
                                        time.sleep(0.1)
                                except:
                                    continue
                    
                    if not has_checkboxes:
                        self.logger.info("ℹ️ 더 이상 삭제할 댓글 없음")
                        break
                    
                    # 삭제 버튼 클릭 (원본 XPath)
                    delete_btn = driver.find_element(By.XPATH, "//button[.//span[contains(text(), '삭제')]]")
                    delete_btn.click()
                    time.sleep(0.5)
                    
                    # Alert 처리 (원본 방식)
                    try:
                        WebDriverWait(driver, 8).until(EC.alert_is_present())
                        alert = driver.switch_to.alert
                        alert.accept()
                        time.sleep(3)
                        deleted_count += 1
                        consecutive_errors = 0
                        self.logger.info(f"✅ 댓글 삭제 성공 (총 {deleted_count}회)")
                    except:
                        consecutive_errors += 1
                        time.sleep(2)
                    
                except Exception as e:
                    consecutive_errors += 1
                    self.logger.warning(f"댓글 삭제 중 오류: {str(e)}")
                    time.sleep(5)
                finally:
                    # 원본 핵심: 매 루프마다 프레임 복귀
                    driver.switch_to.default_content()
            
            return deleted_count > 0
            
        except Exception as e:
            self.logger.error(f"❌ 댓글 삭제 실행 실패: {str(e)}")
            return False
    
    def _fallback_comment_deletion(self, driver: webdriver.Chrome) -> bool:
        """댓글 삭제 폴백 방식"""
        try:
            deleted_count = 0
            consecutive_errors = 0
            
            while consecutive_errors < 3:
                try:
                    # iframe 진입
                    if not self.web_driver_manager.switch_to_iframe(driver, "cafe_main"):
                        break
                    
                    # 댓글 존재 확인
                    comments = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
                    actual_comments = [c for c in comments if c.text.strip()]
                    
                    if not actual_comments:
                        self.logger.info(f"더 이상 삭제할 댓글이 없습니다. 총 {deleted_count}개 삭제 완료!")
                        break
                    
                    # 전체선택 또는 개별 선택
                    has_checkboxes = False
                    try:
                        # 전체선택 체크박스 클릭
                        label = driver.find_element(By.CSS_SELECTOR, "label[for='chk_all']")
                        label.click()
                        has_checkboxes = True
                        time.sleep(0.5)
                    except:
                        # 개별 체크박스 선택
                        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'].input_check[id^='check_comment_']")
                        if checkboxes:
                            has_checkboxes = True
                            for cb in checkboxes[:5]:
                                try:
                                    checkbox_id = cb.get_attribute('id')
                                    if checkbox_id:
                                        label = driver.find_element(By.CSS_SELECTOR, f"label[for='{checkbox_id}']")
                                        label.click()
                                        time.sleep(0.1)
                                except:
                                    continue
                    
                    if not has_checkboxes:
                        break
                    
                    # 삭제 버튼 클릭
                    delete_btn = driver.find_element(By.XPATH, "//button[.//span[contains(text(), '삭제')]]")
                    delete_btn.click()
                    time.sleep(0.5)
                    
                    # Alert 처리
                    try:
                        WebDriverWait(driver, 8).until(EC.alert_is_present())
                        alert = driver.switch_to.alert
                        alert.accept()
                        time.sleep(3)
                        deleted_count += 1
                        consecutive_errors = 0
                    except:
                        consecutive_errors += 1
                        time.sleep(2)
                    
                except Exception as e:
                    consecutive_errors += 1
                    self.logger.warning(f"댓글 삭제 중 오류: {str(e)}")
                    time.sleep(5)
                finally:
                    self.web_driver_manager.switch_to_default_content(driver)
            
            return deleted_count > 0
            
        except Exception as e:
            self.logger.error(f"❌ 댓글 삭제 실행 실패: {str(e)}")
            return False
    
    def _execute_post_deletion(self, driver: webdriver.Chrome) -> bool:
        """게시글 삭제 실행 (원본 방식 - while 루프 + 프레임 관리)"""
        try:
            deleted_count = 0
            consecutive_errors = 0
            
            # 원본 방식: while True 반복 루프
            while True:
                if consecutive_errors >= 3:
                    self.logger.warning("⚠️ 연속 에러 3회 - 게시글 삭제 중단")
                    break
                
                try:
                    # 매 루프마다 프레임 상태 초기화
                    driver.switch_to.default_content()
                    
                    # iframe 진입
                    WebDriverWait(driver, 10).until(
                        EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#cafe_main"))
                    )
                    
                    # 페이지 로딩 대기
                    time.sleep(3)
                    
                    # 게시글 존재 확인 (원본 방식)
                    posts = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
                    actual_posts = [p for p in posts if p.text.strip()]
                    
                    if not actual_posts:
                        self.logger.info("ℹ️ 더 이상 삭제할 게시글 없음")
                        break
                    
                    # 체크박스 선택
                    has_checkboxes = False
                    
                    # 원본 방식: label[for='chk_all'] 클릭 (더 안전)
                    try:
                        label = driver.find_element(By.CSS_SELECTOR, "label[for='chk_all']")
                        label.click()
                        has_checkboxes = True
                        time.sleep(0.5)
                    except:
                        # 개별 체크박스 선택 (원본 방식)
                        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'].input_check[id^='check_article_']")
                        if checkboxes:
                            has_checkboxes = True
                            for cb in checkboxes[:5]:
                                try:
                                    checkbox_id = cb.get_attribute('id')
                                    if checkbox_id:
                                        label = driver.find_element(By.CSS_SELECTOR, f"label[for='{checkbox_id}']")
                                        label.click()
                                        time.sleep(0.1)
                                except:
                                    continue
                    
                    if not has_checkboxes:
                        self.logger.info("ℹ️ 더 이상 삭제할 게시글 없음")
                        break
                    
                    # 삭제 버튼 클릭 (원본 XPath)
                    delete_btn = driver.find_element(By.XPATH, "//button[.//span[contains(text(), '삭제')]]")
                    delete_btn.click()
                    time.sleep(0.5)
                    
                    # Alert 처리 (원본 방식)
                    try:
                        WebDriverWait(driver, 8).until(EC.alert_is_present())
                        alert = driver.switch_to.alert
                        alert.accept()
                        time.sleep(3)
                        deleted_count += 1
                        consecutive_errors = 0
                        self.logger.info(f"✅ 게시글 삭제 성공 (총 {deleted_count}회)")
                    except:
                        consecutive_errors += 1
                        time.sleep(2)
                    
                except Exception as e:
                    consecutive_errors += 1
                    self.logger.warning(f"게시글 삭제 중 오류: {str(e)}")
                    time.sleep(5)
                finally:
                    # 원본 핵심: 매 루프마다 프레임 복귀
                    driver.switch_to.default_content()
            
            return deleted_count > 0
            
        except Exception as e:
            self.logger.error(f"❌ 게시글 삭제 실행 실패: {str(e)}")
            return False
    
    def _fallback_post_deletion(self, driver: webdriver.Chrome) -> bool:
        """게시글 삭제 폴백 방식"""
        try:
            deleted_count = 0
            consecutive_errors = 0
            
            while consecutive_errors < 3:
                try:
                    # iframe 진입
                    if not self.web_driver_manager.switch_to_iframe(driver, "cafe_main"):
                        break
                    
                    # 게시글 존재 확인
                    posts = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
                    actual_posts = [p for p in posts if p.text.strip()]
                    
                    if not actual_posts:
                        self.logger.info(f"더 이상 삭제할 게시글이 없습니다. 총 {deleted_count}개 삭제 완료!")
                        break
                    
                    # 전체선택 또는 개별 선택
                    has_checkboxes = False
                    try:
                        label = driver.find_element(By.CSS_SELECTOR, "label[for='chk_all']")
                        label.click()
                        has_checkboxes = True
                        time.sleep(0.5)
                    except:
                        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'].input_check[id^='check_article_']")
                        if checkboxes:
                            has_checkboxes = True
                            for cb in checkboxes[:5]:
                                try:
                                    checkbox_id = cb.get_attribute('id')
                                    if checkbox_id:
                                        label = driver.find_element(By.CSS_SELECTOR, f"label[for='{checkbox_id}']")
                                        label.click()
                                        time.sleep(0.1)
                                except:
                                    continue
                    
                    if not has_checkboxes:
                        break
                    
                    # 삭제 버튼 클릭
                    delete_btn = driver.find_element(By.XPATH, "//button[.//span[contains(text(), '삭제')]]")
                    delete_btn.click()
                    time.sleep(0.5)
                    
                    # Alert 처리
                    try:
                        WebDriverWait(driver, 8).until(EC.alert_is_present())
                        alert = driver.switch_to.alert
                        alert.accept()
                        time.sleep(3)
                        deleted_count += 1
                        consecutive_errors = 0
                    except:
                        consecutive_errors += 1
                        time.sleep(2)
                    
                except Exception as e:
                    consecutive_errors += 1
                    self.logger.warning(f"게시글 삭제 중 오류: {str(e)}")
                    time.sleep(5)
                finally:
                    self.web_driver_manager.switch_to_default_content(driver)
            
            return deleted_count > 0
            
        except Exception as e:
            self.logger.error(f"❌ 게시글 삭제 실행 실패: {str(e)}")
            return False


    def _input_body_with_simple_method(self, driver: webdriver.Chrome, content: str) -> bool:
        """새 탭 전용: iframe 없이 직접 본문 입력 (초고속)"""
        try:
            # 새 탭에서는 iframe 없이 바로 에디터 접근
            self.logger.info("🚀 새 탭 - 직접 에디터 접근")
            
            # 원본과 동일한 ActionChains 방식 (확실한 방법)
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.keys import Keys
            
            # 에디터 선택자들 (원본과 동일)
            selectors = [
                'p.se-text-paragraph',
                '[contenteditable="true"]',
                'div[role="textbox"]',
                'div[data-placeholder]'
            ]
            
            target = None
            for selector in selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():  # is_enabled() 체크 없이 간단하게
                        target = el
                        self.logger.info(f"✅ 에디터 발견: '{selector}'")
                        break
                if target:
                    break

            if not target:
                self.logger.warning("❌ 입력 가능한 요소를 찾지 못했습니다.")
                return False

            # 원본 ActionChains 방식: 클릭 및 입력
            try:
                # 요소가 화면에 보이도록 스크롤
                driver.execute_script("arguments[0].scrollIntoView(true);", target)
                time.sleep(0.5)
                
                ActionChains(driver).move_to_element(target).click().perform()
                time.sleep(0.5)

                # 원본 방식: 본문 내용 줄별 입력
                for line in content.strip().splitlines():
                    if line.strip():
                        ActionChains(driver).send_keys(line).key_down(Keys.SHIFT).send_keys(Keys.ENTER).key_up(Keys.SHIFT).perform()
                        time.sleep(0.1)

                self.logger.info("✅ 원본 ActionChains 본문 입력 성공")
                return True
            except Exception as e:
                self.logger.warning(f"❌ ActionChains 입력 실패: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ 본문 입력 실패: {str(e)}")
            return False

    def _write_replies_to_single_post(self, driver: webdriver.Chrome, post_title: str, post_content: str,
                                    reply_count: int, add_random_numbers: bool) -> int:
        """단일 게시글에 답글 작성 (원본 방식 - 새 탭 처리)"""
        written_count = 0
        
        try:
            for i in range(reply_count):
                if self._write_single_reply(driver, post_title, post_content, add_random_numbers):
                    written_count += 1
                    self.logger.info(f"✅ 답글 {written_count}/{reply_count} 작성 완료")
                else:
                    self.logger.warning(f"❌ 답글 {i+1}/{reply_count} 작성 실패")
                
                # 답글 간 간격
                time.sleep(2)
            
        except Exception as e:
            self.logger.error(f"❌ 답글 작성 중 오류: {str(e)}")
            
        return written_count

    def _write_single_reply(self, driver: webdriver.Chrome, title: str, content: str, add_random_numbers: bool = False) -> bool:
        """단일 답글 작성 (원본 방식 - 새 탭 처리)"""
        try:
            # iframe 전환 시도
            if not self.web_driver_manager.switch_to_iframe(driver, "cafe_main"):
                self.logger.warning("⚠️ iframe 전환 실패, 메인 페이지에서 시도")
            
            # 답글 버튼 찾기 및 클릭
            reply_selectors = [
                "//div[contains(@class, 'ArticleBottomBtns')]//a[contains(@class, 'BaseButton') and .//span[@class='BaseButton__txt' and normalize-space(text())='답글']]",
                "//a[span[text()='답글']]",
                "//a[contains(text(), '답글')]",
                "//*[@id='app']/div/div/div[3]/div[1]/a[2]"
            ]
            
            reply_btn = None
            for selector in reply_selectors:
                try:
                    reply_btn = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except:
                    continue
            
            if not reply_btn:
                self.logger.warning("❌ 답글 버튼을 찾을 수 없습니다.")
                return False
            
            # 답글 버튼 클릭 → 새 탭 감지 및 전환
            original_tabs = driver.window_handles
            reply_btn.click()
            time.sleep(2)
            
            # 새 탭으로 전환
            try:
                WebDriverWait(driver, 15).until(
                    lambda d: len(d.window_handles) > len(original_tabs)
                )
                new_tab = list(set(driver.window_handles) - set(original_tabs))[0]
                driver.switch_to.window(new_tab)
                self.logger.info("🆕 새 탭으로 전환 완료")
                time.sleep(2)
            except:
                self.logger.warning("ℹ️ 새 탭 감지 실패")
                return False
            
            # 제목 입력 (빠른 대기)
            try:
                title_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'textarea[placeholder="제목을 입력해 주세요."]'))
                )
                
                # 제목 변형
                final_title = title
                if add_random_numbers:
                    import random
                    random_num = random.randint(1000, 9999)
                    final_title = f"{title} {random_num}"
                
                title_input.clear()
                title_input.send_keys(final_title)
                self.logger.info("✅ 제목 입력 성공")
            except Exception as e:
                self.logger.warning(f"❌ 제목 입력 실패: {e}")
                return False
            
            # 본문 입력 (2단계 iframe 진입)
            try:
                # 본문 변형
                final_content = content
                if add_random_numbers:
                    import random
                    random_num = random.randint(1000, 9999)
                    final_content = f"{content} {random_num}"
                
                # 새 탭에서는 iframe 없이 직접 접근 (원본 방식)
                self.logger.info("ℹ️ 새 탭 - iframe 없이 직접 본문 입력")
                
                # 본문 입력
                success = self._input_body_with_simple_method(driver, final_content)
                
                if not success:
                    self.logger.warning("⚠️ 기본 방법 실패 - iframe 전체 순회 시도")
                    # iframe 전체 순회 시도
                    driver.switch_to.default_content()
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for iframe in iframes:
                        try:
                            driver.switch_to.frame(iframe)
                            success = self._input_body_with_simple_method(driver, final_content)
                            driver.switch_to.default_content()
                            if success:
                                self.logger.info("✅ iframe 순회로 본문 입력 성공")
                                break
                        except Exception as e:
                            self.logger.warning(f"iframe 진입 실패: {e}")
                            driver.switch_to.default_content()
                    
                    if not success:
                        self.logger.warning("⚠️ 모든 iframe 시도 실패")
                        return False
                
            except Exception as e:
                self.logger.warning(f"❌ 본문 입력 실패: {e}")
                return False
            
            # 전체공개 설정 (멤버공개 → 전체공개)
            try:
                driver.switch_to.default_content()
                
                # 전체공개 라디오 버튼 선택
                try:
                    all_public_radio = driver.find_element(By.CSS_SELECTOR, "input#all[type='radio'][name='public']")
                    if not all_public_radio.is_selected():
                        driver.execute_script("arguments[0].click();", all_public_radio)
                        self.logger.info("✅ 전체공개로 설정 변경")
                    else:
                        self.logger.info("ℹ️ 이미 전체공개로 설정됨")
                except:
                    self.logger.warning("⚠️ 공개 설정 변경 실패 - 기본값 사용")
                
            except Exception as e:
                self.logger.warning(f"⚠️ 공개 설정 처리 실패: {e}")
            
            # 등록 버튼 클릭 (다양한 선택자 시도)
            try:
                
                # 정확한 등록 버튼 찾기 (HTML 분석 기반)
                submit_selectors = [
                    "a.BaseButton.BaseButton--skinGreen",  # 정확한 등록 버튼 (a 태그)
                    "//a[@role='button'][.//span[text()='등록']]",  # 등록 텍스트 포함 a 태그
                    "a.BaseButton",  # BaseButton 일반
                    "//button[contains(text(), '등록')]",
                    "//button[span[contains(text(), '등록')]]",
                    ".btn_register",
                    "button[type='submit']"
                ]
                
                submit_btn = None
                for selector in submit_selectors:
                    try:
                        if selector.startswith("//"):
                            submit_btn = WebDriverWait(driver, 2).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                        else:
                            submit_btn = WebDriverWait(driver, 2).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                        self.logger.info(f"✅ 등록 버튼 발견: {selector}")
                        break
                    except:
                        continue
                
                if submit_btn:
                    # JavaScript로 클릭 시도
                    try:
                        driver.execute_script("arguments[0].click();", submit_btn)
                        self.logger.info("✅ JavaScript로 등록 버튼 클릭 성공")
                    except:
                        # 일반 클릭 시도
                        submit_btn.click()
                        self.logger.info("✅ 일반 클릭으로 등록 버튼 클릭 성공")
                    
                    time.sleep(7)  # 5초 → 7초 (답글 등록 안정화)
                    self.logger.info("✅ 답글 등록 성공")
                else:
                    self.logger.warning("❌ 등록 버튼을 찾을 수 없습니다")
                    return False
                
                # 새 탭 닫기 및 원래 탭으로 돌아가기
                try:
                    driver.close()  # 현재 탭(새 탭) 닫기
                    driver.switch_to.window(original_tabs[0])  # 원래 탭으로 돌아가기
                    self.logger.info("🔄 새 탭 닫기 및 원래 탭 복귀 완료")
                except Exception as tab_error:
                    self.logger.warning(f"⚠️ 탭 전환 실패: {tab_error}")
                
                return True
                
            except Exception as e:
                self.logger.warning(f"❌ 답글 등록 실패: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ 답글 작성 실패: {str(e)}")
            return False
        finally:
            # 안전장치: 원래 탭으로 돌아가기
            try:
                if len(driver.window_handles) > 1:
                    driver.switch_to.window(original_tabs[0])
            except:
                pass
    
    def _open_my_posts_anywhere(self, driver: webdriver.Chrome, reopen_if_needed: bool = False) -> bool:
        """
        '내가쓴 게시글/작성글' 탭을 가장 확실하게 여는 범용 함수.
        1) 상위 DOM(사이드바)에서 찾기 → 실패 시
        2) iframe(cafe_main) 내부 탭(작성글)에서 찾기 → 실패 시
        3) 옵션이 True면 '나의활동'을 다시 열고 상위 DOM에서 재시도
        """
        try:
            driver.switch_to.default_content()

            # 1) 상위 DOM(사이드바)에서 직접 찾기
            upper_selectors = [
                ("xpath", "//a[contains(@href,'tab=articles')]"),
                ("xpath", "//a[contains(text(),'내가쓴 게시글')]"),
                ("xpath", "//a[contains(text(),'내가 쓴 게시글')]"),
                ("css",  "a[href*='tab=articles']"),
            ]
            for t, s in upper_selectors:
                try:
                    el = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, s)) if t=="xpath"
                        else EC.element_to_be_clickable((By.CSS_SELECTOR, s))
                    )
                    el.click()
                    self._wait_my_tab_loaded(driver)
                    self.logger.info("✅ (상위DOM) 내가쓴 게시글 진입 성공")
                    return True
                except:
                    pass

            # 2) iframe 내부 탭(작성글)에서 찾기
            try:
                WebDriverWait(driver, 3).until(
                    EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe#cafe_main,iframe[name='cafe_main']"))
                )
                inner_selectors = [
                    ("xpath", "//a[contains(@class,'link_sort')][contains(.,'작성글')]"),
                    ("xpath", "//a[contains(.,'작성글')]"),
                    ("css",  "a.link_sort:not(.on)"),
                    ("css",  "a[href*='tab=articles']"),
                ]
                for t, s in inner_selectors:
                    try:
                        el = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, s)) if t=="xpath"
                            else EC.element_to_be_clickable((By.CSS_SELECTOR, s))
                        )
                        el.click()
                        self.logger.info("✅ (iframe) 작성글 탭 클릭 성공")
                        driver.switch_to.default_content()
                        self._wait_my_tab_loaded(driver)
                        return True
                    except:
                        pass
            except:
                pass
            finally:
                driver.switch_to.default_content()

            # 3) 필요 시 '나의활동' 재오픈 → 상위 DOM에서 다시 시도
            if reopen_if_needed:
                if not self._click_my_activity(driver):
                    return False
                self._wait_my_tab_loaded(driver)  # 안정화
                for t, s in upper_selectors:
                    try:
                        el = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, s)) if t=="xpath"
                            else EC.element_to_be_clickable((By.CSS_SELECTOR, s))
                        )
                        el.click()
                        self._wait_my_tab_loaded(driver)
                        self.logger.info("✅ (재오픈) 내가쓴 게시글 진입 성공")
                        return True
                    except:
                        pass

            self.logger.error("❌ 게시글 탭 진입 실패(상위/iframe/재오픈 모두 실패)")
            return False

        except Exception as e:
            self.logger.error(f"❌ 게시글 탭 열기 중 오류: {e}")
            return False

# 전역 콘텐츠 작성기 인스턴스
content_writer = ContentWriter()
