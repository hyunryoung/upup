"""
등업 작업 워커 스레드
실제 카페 등업 작업을 백그라운드에서 수행하는 QThread 워커입니다.
"""

import time
import logging
from typing import Optional
from PyQt5.QtCore import QThread, pyqtSignal
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from ..data.models import Account, CafeInfo, LevelupConditions, WorkResult, WorkStatus
from ..automation.web_driver import web_driver_manager
from ..automation.naver_login import naver_login_handler
from ..automation.levelup_extractor import levelup_extractor
from ..automation.deleted_member_finder import deleted_member_finder
from ..automation.content_writer import content_writer
from ..core.proxy_manager import ProxyManager


class LevelupWorker(QThread):
    """등업 작업 워커 스레드"""
    
    # 시그널 정의
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str, str)
    account_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int, int, int)  # posts, comments, visits
    finished_signal = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, cafe_info: CafeInfo, account: Account, 
                 conditions: Optional[LevelupConditions] = None,
                 proxy_manager: Optional[ProxyManager] = None,
                 work_settings: Optional[dict] = None,
                 reuse_browser: bool = False,
                 existing_driver: Optional[webdriver.Chrome] = None):
        """
        등업 워커 초기화
        
        Args:
            cafe_info: 카페 정보
            account: 계정 정보
            conditions: 등급 조건 (선택사항)
            proxy_manager: 프록시 매니저 (선택사항)
            work_settings: 작업 설정 (선택사항)
            reuse_browser: 브라우저 재사용 여부
            existing_driver: 기존 드라이버 (재사용 시)
        """
        super().__init__()
        
        self.cafe_info = cafe_info
        self.account = account
        self.conditions = conditions
        self.proxy_manager = proxy_manager
        self.work_settings = work_settings or {}
        self.reuse_browser = reuse_browser
        self.existing_driver = existing_driver
        self.keep_open_after_finish = False  # ★ 추가: 기본은 닫기
        
        # 디버깅: 초기 설정 확인
        self.log_signal.emit(f"🔍 워커 초기화: reuse_browser = {self.reuse_browser}")
        
        self.driver: Optional[webdriver.Chrome] = existing_driver if reuse_browser else None
        self.logger = logging.getLogger(__name__)
        
        # 작업 설정 기본값
        self.comment_text = self.work_settings.get('comment_text', '안녕하세요')
        self.post_title = self.work_settings.get('post_title', '안녕하세요')
        self.post_content = self.work_settings.get('post_content', '잘부탁드립니다')
        self.add_random_numbers = self.work_settings.get('add_random_numbers', False)
        self.delete_after_work = self.work_settings.get('delete_after_work', False)
        self.skip_if_visit_insufficient = self.work_settings.get('skip_if_visit_insufficient', False)
        
        # 현재 활동 카운트
        self.current_posts_count = 0
        self.current_comments_count = 0
        self.current_visits_count = 0
    
    def run(self):
        """워커 스레드 실행"""
        try:
            self.log_signal.emit("=" * 50)
            self.log_signal.emit(f"🚀 등업 작업 시작: {self.account.id} → {self.cafe_info.cafe_id}")
            
            # 웹 드라이버 생성 또는 재사용
            if self.reuse_browser and self.existing_driver:
                self.driver = self.existing_driver
                # 재사용 모드 표시 (종료 방지)
                self.driver._reuse_mode = True
                self.log_signal.emit("🔄 기존 브라우저 재사용 중...")
                # 브라우저가 살아있는지 확인 (더 안전한 방법)
                try:
                    # current_url 대신 window_handles로 체크 (연결 오류 방지)
                    if self.driver.window_handles:
                        self.log_signal.emit("✅ 기존 브라우저 상태 정상 (창 존재)")
                    else:
                        raise Exception("브라우저 창 없음")
                except Exception as e:
                    self.log_signal.emit(f"❌ 기존 브라우저 비정상: {str(e)}, 새로 생성")
                    # reuse_browser 플래그 절대 변경 금지! (finally 블록에서 종료 방지)
                    self.driver = None  # 기존 드라이버 해제
                    # 새 브라우저 생성하되 재사용 플래그는 유지
                    if not self._create_driver():
                        self.finished_signal.emit(False, "드라이버 생성 실패")
                        return
                    # 새 브라우저로 로그인 필요
                    if not self._login_to_naver():
                        self.finished_signal.emit(False, "새 브라우저 로그인 실패")
                        return
            else:
                if not self._create_driver():
                    self.finished_signal.emit(False, "드라이버 생성 실패")
                    return
            
            # 네이버 로그인 (재사용 시 생략)
            if not self.reuse_browser:
                if not self._login_to_naver():
                    self.finished_signal.emit(False, "네이버 로그인 실패")
                    return
            else:
                self.log_signal.emit("✅ 브라우저 재사용으로 로그인 생략")
            
            # 등급 조건 확인
            if not self.conditions:
                self.conditions = self._extract_levelup_conditions()
            
            if not self.conditions:
                self.finished_signal.emit(False, "등급 조건 추출 실패")
                return
            
            # 이미 등급 달성된 경우
            if self.conditions.already_achieved:
                self.log_signal.emit("🎉 이미 등급이 달성되어 있습니다!")
                self.finished_signal.emit(True, "등급 이미 달성")
                return
            
            # 방문 횟수 부족시 넘기기 옵션 확인
            if self.skip_if_visit_insufficient and self.conditions.get_needed_visits() > 0:
                self.log_signal.emit(f"❌ 방문 횟수가 {self.conditions.get_needed_visits()}회 부족하여 작업을 종료합니다.")
                self.finished_signal.emit(False, "방문 횟수 부족")
                return
            
            # 실제 등업 작업 수행
            success = self._perform_levelup_work()
            
            # 작업 완료 후 정리
            if success and self.delete_after_work:
                self._cleanup_created_content()
            
            result_message = "등업 작업 완료" if success else "등업 작업 실패"
            self.finished_signal.emit(success, result_message)
            
        except Exception as e:
            self.log_signal.emit(f"❌ 등업 작업 중 예외 발생: {str(e)}")
            self.finished_signal.emit(False, f"예외 발생: {str(e)}")
        finally:
            # 드라이버 정리 여부 결정 (메인의 지시 따름)
            self.log_signal.emit(f"🔍 워커 finally: reuse_browser = {self.reuse_browser}, keep_open = {self.keep_open_after_finish}")
            
            # 재사용 모드가 아니어도, 메인에서 keep_open_after_finish를 켜면 닫지 않음
            if not self.reuse_browser and not self.keep_open_after_finish:
                self.log_signal.emit("❌ 드라이버 정리 모드 → 브라우저 종료")
                self._cleanup_driver()
            else:
                self.log_signal.emit("🔄 브라우저 재사용/유지 모드 - 정리 생략")
                # 드라이버 보호
                if self.driver:
                    self.driver._protected_from_close = True
    
    def _create_driver(self) -> bool:
        """웹 드라이버 생성"""
        try:
            # 프록시 할당
            proxy = None
            if self.proxy_manager:
                proxy_info = self.proxy_manager.get_next_proxy()
                if proxy_info:
                    proxy = proxy_info['raw_proxy']
                    proxy_display = proxy_info['raw_proxy'].split('@')[-1] if '@' in proxy_info['raw_proxy'] else proxy_info['raw_proxy']
                    self.log_signal.emit(f"👤 {self.account.id} → 🔗 프록시: {proxy_display} [{proxy_info['index']}/{proxy_info['total']}]")
                else:
                    self.log_signal.emit(f"👤 {self.account.id} → 🔗 프록시: 할당 실패")
            else:
                self.log_signal.emit(f"👤 {self.account.id} → 🔗 프록시: 사용 안 함")
            
            # 헤드리스 모드 설정
            headless = self.work_settings.get('headless_mode', False)
            
            # 드라이버 생성 (프록시 실제 적용!)
            self.driver = web_driver_manager.create_driver_with_proxy(
                proxy=proxy, 
                headless=headless, 
                purpose=f"{self.account.id} 등업작업"
            )
            
            # 현재 IP 확인
            current_ip = web_driver_manager.get_current_ip(self.driver)
            self.status_signal.emit("current_ip", current_ip)
            
            return True
            
        except Exception as e:
            self.log_signal.emit(f"❌ 드라이버 생성 실패: {str(e)}")
            return False
    
    def _login_to_naver(self) -> bool:
        """네이버 로그인"""
        try:
            self.status_signal.emit("search_status", f"{self.account.id} 로그인 중")
            
            success = naver_login_handler.login_with_account(self.driver, self.account)
            
            if success:
                self.account_signal.emit(self.account.id, "로그인 성공")
                self.log_signal.emit(f"✅ {self.account.id} 네이버 로그인 성공")
            else:
                self.account_signal.emit(self.account.id, "로그인 실패")
                self.log_signal.emit(f"❌ {self.account.id} 네이버 로그인 실패")
            
            return success
            
        except Exception as e:
            self.log_signal.emit(f"❌ 로그인 중 예외: {str(e)}")
            self.account_signal.emit(self.account.id, "로그인 예외")
            return False
    
    def _extract_levelup_conditions(self) -> Optional[LevelupConditions]:
        """등급 조건 추출"""
        try:
            self.status_signal.emit("search_status", f"{self.cafe_info.cafe_id} 등급조건 확인")
            self.log_signal.emit(f"🔍 {self.cafe_info.cafe_id} 카페 등급조건 확인 중...")
            
            conditions = levelup_extractor.extract_levelup_conditions(
                self.driver, 
                self.cafe_info.target_board_id
            )
            
            if conditions:
                self.log_signal.emit("✅ 등급조건 추출 성공")
                
                # 현재 활동 카운트 업데이트
                self.current_posts_count = conditions.current_posts
                self.current_comments_count = conditions.current_comments
                self.current_visits_count = conditions.current_visits
                
                self.progress_signal.emit(
                    self.current_posts_count,
                    self.current_comments_count, 
                    self.current_visits_count
                )
            else:
                self.log_signal.emit("❌ 등급조건 추출 실패 (등업게시판 방식 또는 기타 오류)")
                self.log_signal.emit("🚫 해당 카페는 작업에서 제외됩니다.")
            
            return conditions
            
        except Exception as e:
            self.log_signal.emit(f"❌ 등급조건 추출 중 예외: {str(e)}")
            return None
    
    def _perform_levelup_work(self) -> bool:
        """실제 등업 작업 수행 (원본과 동일한 고속 방식)"""
        try:
            self.status_signal.emit("search_status", f"{self.cafe_info.cafe_id} 등업 작업 중")
            
            # 필요한 작업량 계산
            needed_posts = self.conditions.get_needed_posts()
            needed_comments = self.conditions.get_needed_comments()
            needed_visits = self.conditions.get_needed_visits()
            
            self.log_signal.emit(f"🎯 작업 목표: 게시글 {needed_posts}개, 댓글 {needed_comments}개, 방문 {needed_visits}회")
            
            success = True
            
            # 🚀 원본 방식: 한 번에 탈퇴회원 찾고 댓글+답글 동시 배분
            if needed_comments > 0 or needed_posts > 0:
                success &= self._write_comments_and_replies_optimized(needed_comments, needed_posts)
            
            # 방문 횟수는 페이지 이동으로 자동 증가
            if needed_visits > 0:
                success &= self._increase_visits(needed_visits)
            
            # 최종 결과 로그
            self.log_signal.emit(f"📈 최종 결과: 게시글 {self.current_posts_count}개, 댓글 {self.current_comments_count}개, 방문 {self.current_visits_count}회")
            
            return success
            
        except Exception as e:
            self.log_signal.emit(f"❌ 등업 작업 중 예외: {str(e)}")
            return False
    
    def _write_comments_and_replies_optimized(self, needed_comments: int, needed_posts: int) -> bool:
        """댓글+답글 통합 작성 (원본 방식 - 고속)"""
        try:
            total_needed = needed_comments + needed_posts
            self.log_signal.emit(f"🚀 통합 작성 시작: 댓글 {needed_comments}개 + 답글 {needed_posts}개")
            
            # 1. 한 번만 탈퇴회원 찾기 (답글 35개 제한 고려)
            start_page = self.work_settings.get('reply_start_page', 1)
            target_posts = deleted_member_finder.calculate_needed_deleted_posts(needed_comments, needed_posts)
            deleted_posts = deleted_member_finder.find_deleted_member_posts(
                self.driver, 
                self.cafe_info, 
                self.cafe_info.work_board_id,
                start_page,
                target_posts
            )
            
            if not deleted_posts:
                self.log_signal.emit("❌ 작성할 탈퇴 회원 게시글을 찾을 수 없습니다.")
                return False
            
            if len(deleted_posts) < total_needed:
                self.log_signal.emit(f"⚠️ 필요한 게시글: {total_needed}개, 찾은 게시글: {len(deleted_posts)}개")
            
            success = True
            
            # 2. 효율적 배분: 한 탈퇴회원에게 집중 작업 (원본 방식)
            if needed_comments > 0:
                # 댓글은 한 게시글에 무한정 가능 - 첫 번째 탈퇴회원에게 집중
                comment_posts = [deleted_posts[0]] if deleted_posts else []
                self.log_signal.emit(f"💬 댓글 {needed_comments}개 작성 시작... ('{deleted_posts[0].author}' 게시글에 집중)")
                
                written_comments = content_writer.write_comments_to_posts(
                    self.driver,
                    comment_posts,
                    self.comment_text,
                    needed_comments
                )
                
                self.current_comments_count += written_comments
                self.progress_signal.emit(
                    self.current_posts_count,
                    self.current_comments_count,
                    self.current_visits_count
                )
                
                self.log_signal.emit(f"✅ 댓글 작성 완료: {written_comments}개")
                success &= (written_comments > 0)
            
            # 3. 답글 작성 - 최대 35개까지 한 게시글에 가능
            if needed_posts > 0:
                # 답글도 가능한 한 적은 수의 게시글에 집중 (최대 35개/게시글)
                posts_needed = min((needed_posts + 34) // 35, len(deleted_posts))  # 올림 계산
                reply_posts = deleted_posts[:posts_needed]
                self.log_signal.emit(f"📝 답글 {needed_posts}개 작성 시작... ({posts_needed}개 게시글에 배분)")
                
                written_replies = content_writer.write_replies_to_posts(
                    self.driver,
                    reply_posts,
                    self.post_title,
                    self.post_content,
                    needed_posts
                )
                
                self.current_posts_count += written_replies
                self.progress_signal.emit(
                    self.current_posts_count,
                    self.current_comments_count,
                    self.current_visits_count
                )
                
                self.log_signal.emit(f"✅ 답글 작성 완료: {written_replies}개")
                success &= (written_replies > 0)
            
            return success
            
        except Exception as e:
            self.log_signal.emit(f"❌ 통합 작성 중 예외: {str(e)}")
            return False

    def _write_comments(self, needed_comments: int) -> bool:
        """댓글 작성"""
        try:
            self.log_signal.emit(f"💬 댓글 {needed_comments}개 작성 시작...")
            
            # 탈퇴 회원 게시글 찾기 (댓글만 필요하므로 1명)
            start_page = self.work_settings.get('reply_start_page', 1)
            target_posts = deleted_member_finder.calculate_needed_deleted_posts(needed_comments, 0)
            deleted_posts = deleted_member_finder.find_deleted_member_posts(
                self.driver, 
                self.cafe_info, 
                self.cafe_info.work_board_id,
                start_page,
                target_posts
            )
            
            if not deleted_posts:
                self.log_signal.emit("❌ 댓글을 작성할 탈퇴 회원 게시글을 찾을 수 없습니다.")
                return False
            
            # 스마트 댓글 작성 (입력창 없으면 다른 탈퇴회원 자동 찾기)
            written_comments = content_writer.write_comments_to_posts_smart(
                self.driver,
                self.cafe_info,
                self.cafe_info.work_board_id,
                self.comment_text,
                needed_comments,
                self.add_random_numbers,
                start_page
            )
            
            # 카운트 업데이트
            self.current_comments_count += written_comments
            self.progress_signal.emit(
                self.current_posts_count,
                self.current_comments_count,
                self.current_visits_count
            )
            
            self.log_signal.emit(f"✅ 댓글 작성 완료: {written_comments}개")
            return written_comments > 0
            
        except Exception as e:
            self.log_signal.emit(f"❌ 댓글 작성 중 예외: {str(e)}")
            return False

    def _write_replies(self, needed_replies: int) -> bool:
        """답글 작성 (원본 방식 - 새 탭 처리)"""
        try:
            self.log_signal.emit(f"📝 답글 {needed_replies}개 작성 시작...")
            
            # 탈퇴 회원 게시글 찾기 (답글 35개 제한 고려)
            start_page = self.work_settings.get('reply_start_page', 1)
            target_posts = deleted_member_finder.calculate_needed_deleted_posts(0, needed_replies)
            deleted_posts = deleted_member_finder.find_deleted_member_posts(
                self.driver, 
                self.cafe_info, 
                self.cafe_info.work_board_id,
                start_page,
                target_posts
            )
            
            if not deleted_posts:
                self.log_signal.emit("❌ 답글을 작성할 탈퇴 회원 게시글을 찾을 수 없습니다.")
                return False
            
            # 답글 작성
            written_replies = content_writer.write_replies_to_posts(
                self.driver,
                deleted_posts,
                self.post_title,
                self.post_content,
                needed_replies,
                self.add_random_numbers
            )
            
            # 카운트 업데이트
            self.current_posts_count += written_replies
            self.progress_signal.emit(
                self.current_posts_count,
                self.current_comments_count,
                self.current_visits_count
            )
            
            self.log_signal.emit(f"✅ 답글 작성 완료: {written_replies}개")
            return written_replies > 0
            
        except Exception as e:
            self.log_signal.emit(f"❌ 답글 작성 중 예외: {str(e)}")
            return False
    
    def _write_posts(self, needed_posts: int) -> bool:
        """게시글 작성"""
        try:
            self.log_signal.emit(f"📝 게시글 {needed_posts}개 작성 시작...")
            
            written_posts = 0
            for i in range(needed_posts):
                success = content_writer.write_post_to_target_board(
                    self.driver,
                    self.cafe_info,
                    self.cafe_info.target_board_id,
                    self.post_title,
                    self.post_content,
                    self.add_random_numbers
                )
                
                if success:
                    written_posts += 1
                    self.current_posts_count += 1
                    self.log_signal.emit(f"✅ 게시글 {i+1}/{needed_posts} 작성 완료")
                    
                    # 실시간 카운트 업데이트
                    self.progress_signal.emit(
                        self.current_posts_count,
                        self.current_comments_count,
                        self.current_visits_count
                    )
                    
                    # 게시글 간 딜레이
                    if i < needed_posts - 1:
                        delay = self.work_settings.get('post_delay', 10000) / 1000  # ms -> s
                        time.sleep(delay)
                else:
                    self.log_signal.emit(f"❌ 게시글 {i+1}/{needed_posts} 작성 실패")
            
            self.log_signal.emit(f"✅ 게시글 작성 완료: {written_posts}개")
            return written_posts > 0
            
        except Exception as e:
            self.log_signal.emit(f"❌ 게시글 작성 중 예외: {str(e)}")
            return False
    
    def _increase_visits(self, needed_visits: int) -> bool:
        """방문 횟수 증가"""
        try:
            self.log_signal.emit(f"🚶 방문 횟수 {needed_visits}회 증가 시작...")
            
            # 카페 내 다른 게시판들을 방문하여 방문 횟수 증가
            visit_urls = [
                f"https://cafe.naver.com/{self.cafe_info.cafe_id}",  # 메인 페이지
                f"https://cafe.naver.com/{self.cafe_info.cafe_id}/1",  # 공지사항
                f"https://cafe.naver.com/{self.cafe_info.cafe_id}/2",  # 가입인사
            ]
            
            visits_made = 0
            for i in range(needed_visits):
                try:
                    url = visit_urls[i % len(visit_urls)]
                    self.driver.get(url)
                    time.sleep(2)
                    
                    visits_made += 1
                    self.current_visits_count += 1
                    
                    self.log_signal.emit(f"🚶 방문 {i+1}/{needed_visits} 완료")
                    
                    # 실시간 카운트 업데이트
                    self.progress_signal.emit(
                        self.current_posts_count,
                        self.current_comments_count,
                        self.current_visits_count
                    )
                    
                    # 방문 간 딜레이
                    if i < needed_visits - 1:
                        time.sleep(1)
                        
                except Exception as e:
                    self.log_signal.emit(f"❌ 방문 {i+1} 실패: {str(e)}")
            
            self.log_signal.emit(f"✅ 방문 완료: {visits_made}회")
            return visits_made > 0
            
        except Exception as e:
            self.log_signal.emit(f"❌ 방문 중 예외: {str(e)}")
            return False
    
    def _cleanup_created_content(self):
        """생성된 콘텐츠 정리 (통합 최적화)"""
        try:
            self.log_signal.emit("🗑️ 작업 완료 후 생성된 콘텐츠 삭제 시작...")
            
            # 댓글+게시글 통합 삭제 (한 번에 처리)
            if content_writer.delete_created_comments_and_posts_optimized(self.driver, self.cafe_info):
                self.log_signal.emit("✅ 댓글+게시글 통합 삭제 완료")
            else:
                self.log_signal.emit("⚠️ 일부 삭제 실패 (계속 진행)")
            
        except Exception as e:
            self.log_signal.emit(f"❌ 콘텐츠 정리 중 오류: {str(e)}")
    
    def _cleanup_driver(self):
        """드라이버 정리 (재사용 로직 개선)"""
        try:
            if self.driver:
                if self.reuse_browser:
                    # 재사용 모드일 때는 절대 브라우저 종료하지 않음
                    self.log_signal.emit("🔄 브라우저 재사용 모드 - 유지됨")
                    # driver를 None으로 설정하지 않음 (재사용을 위해)
                else:
                    # 일반 모드일 때만 종료
                    try:
                        web_driver_manager.close_driver(self.driver)
                        self.driver = None
                        self.log_signal.emit("🔚 브라우저 종료 완료")
                    except:
                        self.log_signal.emit("🔚 브라우저 종료 완료")
        except Exception as e:
            self.log_signal.emit(f"⚠️ 드라이버 정리 중 오류: {str(e)}")


class LevelupConditionWorker(QThread):
    """단일 카페 등급조건 확인 워커"""
    
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(dict, str)
    button_signal = pyqtSignal(str, bool, str)
    account_signal = pyqtSignal(str, str)
    
    def __init__(self, cafe_info: CafeInfo, account: Account):
        super().__init__()
        self.cafe_info = cafe_info
        self.account = account
        self.driver: Optional[webdriver.Chrome] = None
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        """실제 등급조건 확인 작업 (원본 방식)"""
        try:
            self.log_signal.emit("🔄 드라이버 생성 중...")
            
            # 드라이버 생성 (원본 방식)
            self.driver = web_driver_manager.create_driver_with_proxy(purpose="등급조건 확인")
            self.log_signal.emit("✅ 드라이버 생성 완료")
            
            self.log_signal.emit(f"🔑 로그인 시작: {self.account.id}")
            
            # 로그인 (원본 방식)
            if not naver_login_handler.login_with_account(self.driver, self.account):
                self.log_signal.emit("❌ 로그인 실패")
                self.account_signal.emit(self.account.id, "로그인 실패")
                return
            
            self.log_signal.emit("✅ 로그인 성공")
            
            # 카페 숫자 ID 추출 (원본 방식)
            self.log_signal.emit("🔍 카페 숫자 ID 추출 중...")
            cafe_numeric_id = levelup_extractor.extract_cafe_numeric_id(self.cafe_info, self.driver)
            if not cafe_numeric_id:
                self.log_signal.emit("❌ 카페 숫자 ID를 찾을 수 없습니다.")
                return
            
            self.log_signal.emit(f"✅ 카페 숫자 ID: {cafe_numeric_id}")
            
            # 등급조건 확인 URL로 이동 (원본 방식)
            target_board_id = self.cafe_info.target_board_id
            levelup_url = f"https://cafe.naver.com/ca-fe/cafes/{cafe_numeric_id}/menus/{target_board_id}/articles/write"
            self.log_signal.emit(f"🌐 등급조건 페이지로 이동...")
            
            self.driver.get(levelup_url)
            time.sleep(3)
            
            self.log_signal.emit("🔍 등급조건 정보 추출 중...")
            
            # 등급조건 정보 추출 (원본 방식)
            conditions = levelup_extractor.extract_levelup_conditions(self.driver, target_board_id)
            
            if conditions:
                self.log_signal.emit("✅ 등급조건 확인 완료!")
                
                # 결과를 딕셔너리로 변환
                conditions_dict = {
                    'posts_required': conditions.posts_required,
                    'comments_required': conditions.comments_required,
                    'visits_required': conditions.visits_required,
                    'current_posts': conditions.current_posts,
                    'current_comments': conditions.current_comments,
                    'current_visits': conditions.current_visits,
                    'already_achieved': conditions.already_achieved,
                    'skip_work': getattr(conditions, 'skip_work', False)
                }
                
                self.result_signal.emit(conditions_dict, f"게시판ID: {target_board_id}")
            else:
                self.log_signal.emit("❌ 등급조건을 찾을 수 없습니다. 페이지 구조를 확인해주세요.")
                
        except Exception as e:
            self.log_signal.emit(f"❌ 등급조건 확인 중 치명적 오류: {str(e)}")
            import traceback
            self.log_signal.emit(f"📋 오류 상세: {traceback.format_exc()}")
        finally:
            try:
                if self.driver:
                    self.driver.switch_to.default_content()
                    # 단일 등급조건 확인 후에는 브라우저 종료 (정상)
                    web_driver_manager.close_driver(self.driver)
                    self.driver = None
                self.log_signal.emit("🔄 등급조건 확인 작업 완료")
                
                # 버튼 복구
                self.button_signal.emit("check_conditions", True, "등급조건 확인하기")
            except:
                pass


class AllLevelupConditionWorker(QThread):
    """모든 카페 등급조건 확인 워커"""
    
    log_signal = pyqtSignal(str)
    table_signal = pyqtSignal(str, dict)
    button_signal = pyqtSignal(str, bool, str)
    account_signal = pyqtSignal(str, str)
    
    def __init__(self, cafes: list, account: Account):
        super().__init__()
        self.cafes = cafes
        self.account = account
        self.driver: Optional[webdriver.Chrome] = None
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        """모든 카페 등급조건 확인 작업 (원본 방식 완전 이식)"""
        try:
            self.log_signal.emit("🔄 드라이버 생성 중...")
            
            # 드라이버 생성
            self.driver = web_driver_manager.create_driver_with_proxy(purpose="전체 등급조건 확인")
            self.log_signal.emit("✅ 드라이버 생성 완료")
            
            self.log_signal.emit(f"🔑 로그인 시작: {self.account.id}")
            
            # 로그인
            if not naver_login_handler.login_with_account(self.driver, self.account):
                self.log_signal.emit("❌ 로그인 실패")
                self.account_signal.emit(self.account.id, "로그인 실패")
                return
            
            self.log_signal.emit("✅ 로그인 성공! 모든 카페 순회 시작...")
            
            success_count = 0
            fail_count = 0
            
            # 각 카페별 등급조건 확인 (원본 로직)
            for i, cafe_info in enumerate(self.cafes, 1):
                try:
                    self.log_signal.emit(f"🏪 [{i}/{len(self.cafes)}] {cafe_info.cafe_id} 확인 중...")
                    
                    # 카페 숫자 ID 추출
                    cafe_numeric_id = levelup_extractor.extract_cafe_numeric_id(cafe_info, self.driver)
                    if not cafe_numeric_id:
                        self.log_signal.emit(f"❌ {cafe_info.cafe_id}: 카페 접근 실패")
                        fail_count += 1
                        continue
                    
                    # 등급조건 확인 URL로 이동
                    target_board_id = cafe_info.target_board_id
                    levelup_url = f"https://cafe.naver.com/ca-fe/cafes/{cafe_numeric_id}/menus/{target_board_id}/articles/write"
                    self.driver.get(levelup_url)
                    time.sleep(2)  # 대기시간 단축
                    
                    # 달성 여부 확인
                    achievement_status = levelup_extractor._check_levelup_achievement_status(self.driver)
                    
                    if achievement_status == "already_achieved":
                        self.log_signal.emit(f"🎉 {self.account.id}: {cafe_info.cafe_id} 이미 달성됨")
                        
                        conditions_dict = {
                            'posts_required': 0,
                            'comments_required': 0,
                            'visits_required': 0,
                            'current_posts': 999,
                            'current_comments': 999,
                            'current_visits': 999,
                            'already_achieved': True
                        }
                        
                        success_count += 1
                    else:
                        # 미달성 계정 - 등급조건 추출 시도
                        self.log_signal.emit(f"🎯 {self.account.id}: {cafe_info.cafe_id} 미달성! 등급조건 추출 중...")
                        
                        # 등급조건 정보 추출
                        conditions = levelup_extractor.extract_levelup_conditions(self.driver, target_board_id)
                        
                        if conditions:
                            self.log_signal.emit(f"✅ {cafe_info.cafe_id} 등급조건 추출 성공!")
                            
                            conditions_dict = {
                                'posts_required': conditions.posts_required,
                                'comments_required': conditions.comments_required,
                                'visits_required': conditions.visits_required,
                                'current_posts': conditions.current_posts,
                                'current_comments': conditions.current_comments,
                                'current_visits': conditions.current_visits,
                                'already_achieved': conditions.already_achieved
                            }
                            
                            success_count += 1
                        else:
                            self.log_signal.emit(f"❌ {cafe_info.cafe_id} 등급조건 추출 실패 (등업게시판 방식 또는 기타 오류)")
                            self.log_signal.emit(f"🚫 {cafe_info.cafe_id} 카페는 작업에서 제외됩니다.")
                            
                            # 실패 사유를 테이블에 표시
                            conditions_dict = {
                                'posts_required': 0,
                                'comments_required': 0,
                                'visits_required': 0,
                                'current_posts': 0,
                                'current_comments': 0,
                                'current_visits': 0,
                                'already_achieved': False,
                                'failure_reason': '등업게시판 방식'  # 실패 사유 추가
                            }
                            
                            fail_count += 1
                    
                    # UI 업데이트
                    self.table_signal.emit(cafe_info.cafe_id, conditions_dict)
                    
                except Exception as e:
                    self.log_signal.emit(f"❌ {cafe_info.cafe_id} 확인 중 오류: {str(e)}")
                    fail_count += 1
                    continue
            
            self.log_signal.emit("🎉 모든 카페 등급조건 확인 완료!")
            self.log_signal.emit(f"📊 결과: 성공 {success_count}개, 실패 {fail_count}개")
            
        except Exception as e:
            self.log_signal.emit(f"❌ 전체 등급조건 확인 중 예외: {str(e)}")
        finally:
            # 등급조건 확인 완료 후 브라우저 종료 (정상)
            if self.driver:
                self.driver.switch_to.default_content()
                web_driver_manager.close_driver(self.driver)  # 등급조건 확인 후에는 종료
            
            self.button_signal.emit("check_all_conditions", True, "🔍 모든 카페 등급조건 확인")


class SheetLevelupWorker(QThread):
    """시트별 병렬 처리를 위한 워커"""
    
    # 시그널 정의
    log_signal = pyqtSignal(str, str)  # (sheet_name, message)
    progress_signal = pyqtSignal(str, int, int)  # (sheet_name, current, total)
    result_signal = pyqtSignal(str, str, str, str)  # (sheet_name, account_id, cafe_id, result)
    work_result_signal = pyqtSignal(object)  # WorkResult 객체 전송
    finished_signal = pyqtSignal(str)  # (sheet_name)
    
    def __init__(self, sheet_name: str, accounts: list, cafes: list, 
                 conditions_cache: dict, manual_conditions: dict, 
                 work_settings: dict, proxy_manager=None):
        super().__init__()
        
        self.sheet_name = sheet_name
        self.accounts = accounts
        self.cafes = cafes
        self.conditions_cache = conditions_cache
        self.manual_conditions = manual_conditions
        self.work_settings = work_settings
        self.proxy_manager = proxy_manager
        
        self.driver = None
        self.current_account_id = None
        self.current_proxy = None  # 현재 사용 중인 프록시 추적
        
    def run(self):
        """시트별 작업 실행"""
        try:
            self.log_signal.emit(self.sheet_name, f"🚀 작업 시작 - {len(self.accounts)}개 계정, {len(self.cafes)}개 카페")
            
            total_tasks = len(self.accounts) * len(self.cafes)
            current_task = 0
            
            # 계정별로 순차 처리 (같은 계정은 브라우저 재사용)
            for account in self.accounts:
                self.log_signal.emit(self.sheet_name, f"👤 계정 시작: {account.id}")
                
                # 계정 변경 시 브라우저 새로 생성
                if self.current_account_id != account.id:
                    self._create_new_browser(account)
                    self.current_account_id = account.id
                
                # 해당 계정으로 모든 카페 처리
                for cafe in self.cafes:
                    current_task += 1
                    self.progress_signal.emit(self.sheet_name, current_task, total_tasks)
                    
                    try:
                        # 등급조건 확인
                        manual_key = f"{self.sheet_name}_{account.id}_{cafe.cafe_id}"
                        
                        if manual_key in self.manual_conditions:
                            # 수동 수정된 조건 사용
                            condition_text = self.manual_conditions[manual_key]
                            self.log_signal.emit(self.sheet_name, f"✏️ 수동 조건 사용: {cafe.cafe_id} → {condition_text}")
                            posts_req, comments_req = self._parse_manual_condition(condition_text)
                            
                            from ..data.models import LevelupConditions
                            conditions = LevelupConditions(
                                posts_required=posts_req,
                                comments_required=comments_req,
                                visits_required=0,
                                current_posts=0,
                                current_comments=0,
                                current_visits=0,
                                already_achieved=False,
                                target_level_name=f"수정됨({condition_text})"
                            )
                        else:
                            # 캐시된 조건 사용
                            if cafe.cafe_id not in self.conditions_cache:
                                self.log_signal.emit(self.sheet_name, f"⚠️ {cafe.cafe_id} 등급조건 없음 - 건너뜀")
                                continue
                            
                            conditions_dict = self.conditions_cache[cafe.cafe_id]
                            if conditions_dict.get('failure_reason'):
                                self.log_signal.emit(self.sheet_name, f"❌ {cafe.cafe_id} 처리 불가 - {conditions_dict['failure_reason']}")
                                continue
                            
                            from ..data.models import LevelupConditions
                            conditions = LevelupConditions(**conditions_dict)
                        
                        # 실제 등업 작업 수행
                        result = self._perform_levelup_work(account, cafe, conditions)
                        self.result_signal.emit(self.sheet_name, account.id, cafe.cafe_id, result)
                        
                    except Exception as e:
                        error_msg = f"❌ 작업 실패: {str(e)}"
                        self.log_signal.emit(self.sheet_name, error_msg)
                        self.result_signal.emit(self.sheet_name, account.id, cafe.cafe_id, "실패")
            
            self.log_signal.emit(self.sheet_name, f"✅ 모든 작업 완료!")
            
        except Exception as e:
            self.log_signal.emit(self.sheet_name, f"❌ 시트 작업 중 예외: {str(e)}")
        finally:
            # 브라우저 정리
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            self.finished_signal.emit(self.sheet_name)
    
    def _create_new_browser(self, account):
        """새 브라우저 생성 및 로그인"""
        try:
            # 기존 브라우저 종료
            if self.driver:
                self.driver.quit()
            
            # 프록시 할당
            proxy = None
            if self.proxy_manager:
                proxy_info = self.proxy_manager.get_next_proxy()
                if proxy_info:
                    proxy = proxy_info['raw_proxy']
                    self.current_proxy = proxy  # 프록시 정보 저장
                    proxy_display = proxy.split('@')[-1] if proxy and '@' in proxy else proxy or "없음"
                    self.log_signal.emit(self.sheet_name, f"🌐 프록시 할당: {proxy_display} [{proxy_info['index']}/{proxy_info['total']}]")
                else:
                    self.current_proxy = None
                    self.log_signal.emit(self.sheet_name, f"🌐 프록시: 할당 실패")
            else:
                self.current_proxy = None
                self.log_signal.emit(self.sheet_name, f"🌐 프록시: 사용 안함")
            
            # 새 브라우저 생성
            self.driver = web_driver_manager.create_driver_with_proxy(
                proxy, 
                headless=self.work_settings.get('headless_mode', True)
            )
            
            # 브라우저 창 위치 설정 (헤드리스가 아닌 경우에만)
            if not self.work_settings.get('headless_mode', True):
                self._set_browser_window_position()
            
            # 로그인 수행
            self.log_signal.emit(self.sheet_name, f"🔐 {account.id} 로그인 시도...")
            login_success = naver_login_handler.login_with_account(self.driver, account)
            
            if login_success:
                self.log_signal.emit(self.sheet_name, f"✅ {account.id} 로그인 성공")
            else:
                raise Exception(f"로그인 실패")
            
        except Exception as e:
            self.log_signal.emit(self.sheet_name, f"❌ 브라우저 생성 실패: {str(e)}")
            raise
    
    def _perform_levelup_work(self, account, cafe, conditions):
        """실제 등업 작업 수행"""
        try:
            self.log_signal.emit(self.sheet_name, f"🎯 {cafe.cafe_id} 등업 작업 시작...")
            
            # 기존 LevelupWorker의 로직을 재사용
            levelup_worker = LevelupWorker(
                cafe_info=cafe,  # cafe → cafe_info로 수정
                account=account,
                conditions=conditions,
                work_settings=self.work_settings
            )
            
            # 동기적으로 실행하기 위해 직접 호출
            levelup_worker.driver = self.driver  # 브라우저 공유
            levelup_worker.reuse_browser = True
            
            # 작업 수행 (올바른 메서드 호출)
            success = levelup_worker._perform_levelup_work()
            
            # 삭제 설정이 있고 작업이 성공했으면 삭제 실행
            if success and self.work_settings.get('delete_after_work', False):
                self.log_signal.emit(self.sheet_name, f"🗑️ {cafe.cafe_id} 생성된 콘텐츠 삭제 시작...")
                levelup_worker._cleanup_created_content()
                self.log_signal.emit(self.sheet_name, f"✅ {cafe.cafe_id} 콘텐츠 삭제 완료")
            
            result = "성공" if success else "실패"
            
            # WorkResult 생성 시 프록시 정보 포함
            from ..data.models import WorkResult
            from datetime import datetime
            
            proxy_display = "사용안함"
            if self.current_proxy:
                proxy_display = self.current_proxy.split('@')[-1] if '@' in self.current_proxy else self.current_proxy
            
            work_result = WorkResult(
                account_id=account.id,
                account_password="●" * len(account.pw),  # 보안상 마스킹
                cafe_name=cafe.cafe_id,
                cafe_url=cafe.url,
                work_result=result,
                work_datetime=datetime.now(),
                posts_count=getattr(levelup_worker, 'current_posts_count', 0),
                comments_count=getattr(levelup_worker, 'current_comments_count', 0),
                visits_count=getattr(levelup_worker, 'current_visits_count', 0),
                used_proxy=proxy_display
            )
            
            # WorkResult를 UI로 전송
            self.work_result_signal.emit(work_result)
            
            self.log_signal.emit(self.sheet_name, f"✅ {cafe.cafe_id} 작업 완료: {result} (프록시: {proxy_display})")
            return result
            
        except Exception as e:
            self.log_signal.emit(self.sheet_name, f"❌ {cafe.cafe_id} 작업 실패: {str(e)}")
            return "실패"
    
    def _parse_manual_condition(self, condition: str) -> tuple:
        """수동 입력된 조건을 파싱해서 게시글/댓글 수 반환"""
        import re
        
        posts_required = 0
        comments_required = 0
        
        # 게시글 수 추출
        post_match = re.search(r'게시글(\d+)', condition)
        if post_match:
            posts_required = int(post_match.group(1))
        
        # 댓글 수 추출  
        comment_match = re.search(r'댓글(\d+)', condition)
        if comment_match:
            comments_required = int(comment_match.group(1))
        
        return posts_required, comments_required
    
    def _set_browser_window_position(self):
        """브라우저 창 위치를 시트별로 분산 배치"""
        try:
            # 화면 크기 감지 (기본값: 1920x1080)
            import tkinter as tk
            root = tk.Tk()
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            root.destroy()
            
            # 시트 번호 추출 (Sheet1 → 1, Sheet2 → 2, ...)
            import re
            sheet_match = re.search(r'Sheet(\d+)', self.sheet_name)
            sheet_index = int(sheet_match.group(1)) - 1 if sheet_match else 0
            
            # 창 크기 설정 (모니터링용 작은 크기)
            window_width = 600   # 고정 600px
            window_height = 600  # 고정 400px
            
            # 창 위치 계산 (격자 배치)
            positions = [
                (0, 0),                                    # Sheet1: 좌상
                (window_width, 0),                         # Sheet2: 우상  
                (0, window_height),                        # Sheet3: 좌하
                (window_width, window_height),             # Sheet4: 우하
                (window_width // 2, 0),                    # Sheet5: 중상
                (window_width // 2, window_height),        # Sheet6: 중하
            ]
            
            # 시트 개수가 많으면 순환
            pos_x, pos_y = positions[sheet_index % len(positions)]
            
            # 브라우저 창 위치 및 크기 설정
            self.driver.set_window_position(pos_x, pos_y)
            self.driver.set_window_size(window_width, window_height)
            
            self.log_signal.emit(self.sheet_name, f"🖥️ 창 위치 설정: ({pos_x}, {pos_y}) - {window_width}x{window_height}")
            
        except Exception as e:
            self.log_signal.emit(self.sheet_name, f"⚠️ 창 위치 설정 실패: {str(e)}")
            # 실패해도 작업은 계속 진행
