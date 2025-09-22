"""
계산 관련 유틸리티
등급 조건 계산, 필요한 작업량 계산 등을 담당합니다.
"""

import math
import logging
from typing import Dict, Any, Optional


class CalculationUtils:
    """계산 관련 유틸리티 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_needed_deleted_posts(self, needed_posts: int) -> int:
        """필요한 탈퇴 회원 게시글 수 계산"""
        try:
            # 한 게시물당 최대 답글 수 (네이버 카페 제한)
            max_replies_per_post = 35
            
            # 필요한 탈퇴 회원 게시글 수 계산 (올림)
            needed_deleted_posts = math.ceil(needed_posts / max_replies_per_post)
            
            # 최소 1개는 확보
            needed_deleted_posts = max(1, needed_deleted_posts)
            
            self.logger.info(f"🧮 최적화 계산:")
            self.logger.info(f"   필요한 게시글: {needed_posts}개")
            self.logger.info(f"   게시물당 최대 답글: {max_replies_per_post}개")
            self.logger.info(f"   필요한 탈퇴 회원 게시글: {needed_deleted_posts}개")
            
            return needed_deleted_posts
            
        except Exception as e:
            self.logger.error(f"❌ 탈퇴 회원 게시글 수 계산 실패: {str(e)}")
            return 3  # 폴백 값
    
    def calculate_needed_posts(self, current_posts: int, required_posts: int) -> int:
        """필요한 게시글 수 계산"""
        needed = max(0, required_posts - current_posts)
        self.logger.info(f"📊 게시글 현황: 현재 {current_posts}개 → 등급조건 {required_posts}개 (필요: {needed}개)")
        return needed
    
    def calculate_needed_comments(self, current_comments: int, required_comments: int) -> int:
        """필요한 댓글 수 계산"""
        needed = max(0, required_comments - current_comments)
        self.logger.info(f"📊 댓글 현황: 현재 {current_comments}개 → 등급조건 {required_comments}개 (필요: {needed}개)")
        return needed
    
    def calculate_needed_visits(self, current_visits: int, required_visits: int) -> int:
        """필요한 방문 수 계산"""
        needed = max(0, required_visits - current_visits)
        self.logger.info(f"📊 방문 현황: 현재 {current_visits}회 → 등급조건 {required_visits}회 (필요: {needed}회)")
        return needed
    
    def check_levelup_needed(self, requirements: Dict[str, int], current_activity: Dict[str, int]) -> tuple:
        """등업 필요 여부 판단"""
        try:
            posts_needed = requirements.get('posts_required', 0) - current_activity.get('current_posts', 0)
            comments_needed = requirements.get('comments_required', 0) - current_activity.get('current_comments', 0)
            visits_needed = requirements.get('visits_required', 0) - current_activity.get('current_visits', 0)
            
            needs_levelup = posts_needed > 0 or comments_needed > 0 or visits_needed > 0
            
            if needs_levelup:
                self.logger.info(f"🔥 등업 필요! 부족한 것: 게시글 {max(0, posts_needed)}개, 댓글 {max(0, comments_needed)}개, 방문 {max(0, visits_needed)}회")
            else:
                self.logger.info("✅ 등업 조건 충족! 등업 작업 불필요")
            
            return needs_levelup, {
                'posts_needed': max(0, posts_needed),
                'comments_needed': max(0, comments_needed),
                'visits_needed': max(0, visits_needed)
            }
            
        except Exception as e:
            self.logger.error(f"⚠️ 등업 필요 여부 판단 실패: {str(e)}")
            return True, {'posts_needed': 0, 'comments_needed': 0, 'visits_needed': 0}
    
    def distribute_comments_across_posts(self, total_comments: int, total_posts: int) -> tuple:
        """댓글을 게시글에 배분"""
        if total_posts == 0:
            return 0, 0
        
        if total_comments >= total_posts:
            comments_per_post = total_comments // total_posts
            extra_comments = total_comments % total_posts
        else:
            comments_per_post = 0
            extra_comments = total_comments
        
        self.logger.info(f"💬 댓글 배분: {total_comments}개를 {total_posts}개 게시글에 배분")
        self.logger.info(f"📝 게시글당 {comments_per_post}개씩, {extra_comments}개 게시글에 1개씩 추가")
        
        return comments_per_post, extra_comments
    
    def calculate_work_statistics(self, work_results: list) -> Dict[str, Any]:
        """작업 통계 계산"""
        try:
            if not work_results:
                return {}
            
            total_works = len(work_results)
            
            # 결과별 통계
            result_counts = {}
            for result in work_results:
                status = result.get('work_result', '알 수 없음')
                result_counts[status] = result_counts.get(status, 0) + 1
            
            # 성공률 계산
            success_count = result_counts.get('등업 작업 완료', 0)
            success_rate = (success_count / total_works * 100) if total_works > 0 else 0
            
            return {
                'total_works': total_works,
                'result_counts': result_counts,
                'success_count': success_count,
                'success_rate': success_rate
            }
            
        except Exception as e:
            self.logger.error(f"❌ 작업 통계 계산 실패: {str(e)}")
            return {}


# 전역 계산 유틸리티 인스턴스
calculation_utils = CalculationUtils()
