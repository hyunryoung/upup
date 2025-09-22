"""
데이터 모델 정의
애플리케이션에서 사용하는 데이터 구조를 정의합니다.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class WorkStatus(Enum):
    """작업 상태"""
    PENDING = "대기중"
    IN_PROGRESS = "진행중"
    COMPLETED = "완료"
    FAILED = "실패"
    SKIPPED = "건너뜀"


class AccountStatus(Enum):
    """계정 상태"""
    READY = "준비됨"
    LOGIN_SUCCESS = "로그인 성공"
    LOGIN_FAILED = "로그인 실패"
    LOGIN_EXCEPTION = "로그인 예외"
    WORKING = "작업중"
    COMPLETED = "작업완료"


@dataclass
class Account:
    """네이버 계정 정보"""
    id: str
    pw: str
    status: AccountStatus = AccountStatus.READY
    last_used: Optional[datetime] = None
    
    def __post_init__(self):
        if isinstance(self.status, str):
            # 문자열을 Enum으로 변환
            for status in AccountStatus:
                if status.value == self.status:
                    self.status = status
                    break


@dataclass
class CafeInfo:
    """카페 정보"""
    url: str
    cafe_id: str
    work_board_id: str
    target_board_id: str
    name: Optional[str] = None
    numeric_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.cafe_id and self.url:
            # URL에서 카페 ID 추출
            import re
            if "cafe.naver.com/" in self.url:
                match = re.search(r'cafe\.naver\.com/([^/?]+)', self.url)
                if match:
                    self.cafe_id = match.group(1)


@dataclass
class LevelupConditions:
    """등급 조건 정보"""
    posts_required: int = 0
    comments_required: int = 0
    visits_required: int = 0
    current_posts: int = 0
    current_comments: int = 0
    current_visits: int = 0
    already_achieved: bool = False
    skip_work: bool = False
    target_level_name: Optional[str] = None
    failure_reason: Optional[str] = None  # 실패 사유 (글쓰기 조건 등)
    
    def get_needed_posts(self) -> int:
        """필요한 게시글 수 반환"""
        return max(0, self.posts_required - self.current_posts)
    
    def get_needed_comments(self) -> int:
        """필요한 댓글 수 반환"""
        return max(0, self.comments_required - self.current_comments)
    
    def get_needed_visits(self) -> int:
        """필요한 방문 수 반환"""
        return max(0, self.visits_required - self.current_visits)
    
    def is_completed(self) -> bool:
        """등급 조건 완료 여부"""
        return (self.current_posts >= self.posts_required and 
                self.current_comments >= self.comments_required and 
                self.current_visits >= self.visits_required)


@dataclass
class DeletedPost:
    """탈퇴 회원 게시글 정보"""
    link: str
    author: str
    title: Optional[str] = None
    
    def get_article_id(self) -> Optional[str]:
        """게시글 ID 추출"""
        import re
        if "articles/" in self.link:
            match = re.search(r'/articles/(\d+)', self.link)
            if match:
                return match.group(1)
        elif "articleid=" in self.link:
            match = re.search(r'articleid=(\d+)', self.link)
            if match:
                return match.group(1)
        return None


@dataclass
class WorkResult:
    """작업 결과 정보"""
    account_id: str
    account_password: str
    cafe_name: str
    cafe_url: str
    work_result: str
    work_datetime: datetime
    posts_count: int = 0
    comments_count: int = 0
    visits_count: int = 0
    used_proxy: str = "사용안함"
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            '계정': self.account_id,
            '암호': self.account_password,
            '카페명': self.cafe_name,
            '카페URL': self.cafe_url,
            '작업결과': self.work_result,
            '작업일시': self.work_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            '게시글수': self.posts_count,
            '댓글수': self.comments_count,
            '방문횟수': self.visits_count,
            '사용프록시': self.used_proxy
        }


@dataclass
class WorkTask:
    """작업 태스크 정보"""
    account_idx: int
    account: Account
    cafe_idx: int
    cafe_info: CafeInfo
    conditions: Optional[LevelupConditions] = None
    status: WorkStatus = WorkStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    sheet_name: Optional[str] = None  # 통합 엑셀용 시트 이름
    
    def get_duration(self) -> Optional[float]:
        """작업 소요 시간 (초) 반환"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


@dataclass
class AppState:
    """애플리케이션 상태"""
    accounts: List[Account] = field(default_factory=list)
    cafes: List[CafeInfo] = field(default_factory=list)
    work_results: List[WorkResult] = field(default_factory=list)
    current_work_queue: List[WorkTask] = field(default_factory=list)
    current_work_index: int = 0
    is_running: bool = False
    work_start_time: Optional[datetime] = None
    
    # 등급조건 캐시 (카페별로 저장)
    cafe_conditions: Dict[str, Optional[LevelupConditions]] = field(default_factory=dict)
    
    # 현재 활동 카운트
    current_posts_count: int = 0
    current_comments_count: int = 0
    current_visits_count: int = 0
    
    # 현재 상태
    my_nickname: Optional[str] = None
    my_cafe_nickname: Optional[str] = None
    current_proxy: Optional[str] = None
    last_logged_account: Optional[str] = None
    
    # 브라우저 재사용을 위한 상태
    current_browser_account: Optional[str] = None
    browser_reuse_mode: bool = True
    
    def add_account(self, account: Account) -> None:
        """계정 추가"""
        self.accounts.append(account)
    
    def add_cafe(self, cafe: CafeInfo) -> None:
        """카페 추가"""
        self.cafes.append(cafe)
    
    def add_work_result(self, result: WorkResult) -> None:
        """작업 결과 추가"""
        self.work_results.append(result)
    
    def get_account_by_id(self, account_id: str) -> Optional[Account]:
        """ID로 계정 찾기"""
        for account in self.accounts:
            if account.id == account_id:
                return account
        return None
    
    def get_cafe_by_id(self, cafe_id: str) -> Optional[CafeInfo]:
        """ID로 카페 찾기"""
        for cafe in self.cafes:
            if cafe.cafe_id == cafe_id:
                return cafe
        return None
    
    def reset_activity_counts(self) -> None:
        """활동 카운트 초기화"""
        self.current_posts_count = 0
        self.current_comments_count = 0
        self.current_visits_count = 0
    
    def get_work_statistics(self) -> Dict[str, Any]:
        """작업 통계 반환"""
        total_accounts = len(self.accounts)
        total_cafes = len(self.cafes)
        total_works = len(self.work_results)
        
        # 결과별 통계
        result_counts = {}
        for result in self.work_results:
            status = result.work_result
            result_counts[status] = result_counts.get(status, 0) + 1
        
        # 작업 시간 계산
        elapsed_time = None
        if self.work_start_time:
            elapsed_time = datetime.now() - self.work_start_time
        
        return {
            'total_accounts': total_accounts,
            'total_cafes': total_cafes,
            'total_works': total_works,
            'result_counts': result_counts,
            'elapsed_time': elapsed_time
        }
