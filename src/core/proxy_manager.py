"""
프록시 관리 클래스
네이버 카페 등업 프로그램의 프록시 서버 관리를 담당합니다.
"""

import threading
import requests
import logging
from typing import List, Optional, Dict, Set


class ProxyManager:
    """프록시 서버 관리 클래스"""
    
    def __init__(self, proxy_list: List[str]):
        """
        프록시 매니저 초기화
        
        Args:
            proxy_list: 프록시 서버 목록
        """
        self.proxies = [proxy.strip() for proxy in proxy_list if proxy.strip()]
        self.current_index = 0
        self.failed_proxies: Set[str] = set()
        self.failure_count: Dict[str, int] = {}
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
    def get_next_proxy(self) -> Optional[Dict[str, any]]:
        """
        다음 사용 가능한 프록시를 반환합니다.
        
        Returns:
            프록시 정보 딕셔너리 또는 None
        """
        with self.lock:
            if not self.proxies:
                return None
                
            available_proxies = [p for p in self.proxies if p not in self.failed_proxies]
            if not available_proxies:
                # 모든 프록시가 실패했으면 실패 카운트 초기화
                self.failed_proxies.clear()
                self.failure_count.clear()
                available_proxies = self.proxies
                
            if available_proxies:
                proxy_index = self.current_index % len(available_proxies)
                proxy = available_proxies[proxy_index]
                self.current_index += 1
                return {
                    'proxy': self.format_proxy(proxy),
                    'index': proxy_index + 1,  # 1부터 시작하는 번호
                    'total': len(available_proxies),
                    'raw_proxy': proxy
                }
            return None
        
    def format_proxy(self, proxy: str) -> Optional[str]:
        """
        프록시 주소를 포맷팅합니다.
        
        Args:
            proxy: 프록시 주소
            
        Returns:
            포맷팅된 프록시 주소
        """
        if not proxy:
            return None
        if '@' in proxy:
            # user:pass@host:port 형식
            return f"{proxy}"
        else:
            # host:port 형식
            return f"{proxy}"
            
    def mark_failed(self, proxy_str: str) -> None:
        """
        프록시를 실패로 표시합니다.
        
        Args:
            proxy_str: 실패한 프록시 주소
        """
        with self.lock:
            if not proxy_str:
                return
            
            self.failure_count[proxy_str] = self.failure_count.get(proxy_str, 0) + 1
            if self.failure_count[proxy_str] >= 3:
                self.failed_proxies.add(proxy_str)
                
    def test_proxy(self, proxy_str: str) -> bool:
        """
        프록시 서버를 테스트합니다.
        
        Args:
            proxy_str: 테스트할 프록시 주소
            
        Returns:
            프록시 작동 여부
        """
        try:
            # 네이버 검색 페이지로 실제 테스트
            test_url = "https://search.naver.com/search.naver?query=test"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            if '@' in proxy_str:
                # user:pass@host:port 형식
                proxy_dict = {'http': f'http://{proxy_str}', 'https': f'http://{proxy_str}'}
            else:
                # host:port 형식
                proxy_dict = {'http': f'http://{proxy_str}', 'https': f'http://{proxy_str}'}
                
            response = requests.get(test_url, proxies=proxy_dict, headers=headers, timeout=3)
            return response.status_code == 200 and 'naver' in response.text.lower()
        except Exception as e:
            self.logger.warning(f"프록시 테스트 실패: {proxy_str}, 오류: {str(e)}")
            return False
            
    def get_working_proxies(self) -> List[str]:
        """
        작동하는 프록시 목록을 반환합니다.
        
        Returns:
            작동하는 프록시 목록
        """
        with self.lock:
            return [p for p in self.proxies if p not in self.failed_proxies]
    
    def get_proxy_stats(self) -> Dict[str, int]:
        """
        프록시 통계 정보를 반환합니다.
        
        Returns:
            프록시 통계 딕셔너리
        """
        with self.lock:
            return {
                'total': len(self.proxies),
                'working': len(self.get_working_proxies()),
                'failed': len(self.failed_proxies)
            }
