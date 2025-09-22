"""
등급 조건 추출 모듈
네이버 카페의 등급 조건을 자동으로 분석하고 추출합니다.
"""

import re
import time
import logging
from typing import Optional, Dict, List, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from ..data.models import LevelupConditions
from .web_driver import WebDriverManager


class LevelupExtractor:
    """등급 조건 추출 클래스"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.web_driver_manager = WebDriverManager()
    
    def extract_levelup_conditions(self, driver: webdriver.Chrome, board_id: str) -> Optional[LevelupConditions]:
        """
        등급조건 정보 추출 (이미 등급 달성 여부도 확인)
        
        Args:
            driver: WebDriver 인스턴스
            board_id: 게시판 ID
            
        Returns:
            등급 조건 정보 또는 None
        """
        try:
            self.logger.info("🔍 등급 달성 여부 확인 중...")
            page_status = self._check_levelup_achievement_status(driver)
            
            conditions = LevelupConditions()
            
            if page_status == "already_achieved":
                self.logger.info("🎉 이 계정은 이미 등급이 달성되었습니다!")
                conditions.already_achieved = True
                return conditions
            elif page_status == "writing_conditions_required":
                self.logger.warning("❌ 글쓰기 조건 카페 - 자동화 불가능")
                # 실패 사유를 포함한 조건 객체 반환 (UI 표시용)
                conditions.failure_reason = "writing_conditions_required"
                return conditions
            
            self.logger.info("⚠️ 아직 등급 미달성 - 등급조건 추출 시도")
            
            # cafe_main iframe 전환 (필수!) - WebDriverWait 사용
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[name='cafe_main']"))
                )
                iframe = driver.find_element(By.CSS_SELECTOR, "iframe[name='cafe_main']")
                driver.switch_to.frame(iframe)
                self.logger.info("✅ 등급조건 확인용 iframe 전환 성공")
                
                # iframe 내용 로딩 대기
                WebDriverWait(driver, 10).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "ul.list_level li")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".myinfo_area")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".member_info"))
                    )
                )
                self.logger.info("✅ iframe 내용 로딩 완료")
                
            except (TimeoutException, NoSuchElementException) as iframe_error:
                self.logger.warning(f"❌ iframe 전환 실패: {str(iframe_error)} - iframe 없이 시도")
                return self._extract_levelup_without_iframe(driver)
            
            # 등급조건 추출 - JavaScript 일괄 처리 방식
            try:
                # 1. JavaScript로 등급 리스트 및 활동 정보 한 번에 수집
                data = driver.execute_script("""
                    const result = {
                        levels: [],
                        currentActivity: {},
                        pageText: document.body.innerText || ''
                    };
                    
                    // 등급 리스트 수집
                    document.querySelectorAll("ul.list_level li").forEach((li, index) => {
                        try {
                            const nameEl = li.querySelector(".img .txt");
                            const name = nameEl ? nameEl.textContent.trim() : '';
                            
                            let condition = '';
                            li.querySelectorAll("div.desc p").forEach(p => {
                                const text = p.textContent.trim();
                                if (text && text.includes("자동등업")) {
                                    condition = text;
                                }
                            });
                            
                            // 현재 등급인지 확인
                            const itemClass = li.className || '';
                            const itemHtml = li.outerHTML;
                            let isCurrent = false;
                            
                            if (['on', 'current', 'active', 'my_level'].some(cls => itemClass.includes(cls))) {
                                isCurrent = true;
                            }
                            
                            if (li.querySelector('.ico_now, .current, .active, .my_level')) {
                                isCurrent = true;
                            }
                            
                            if (['현재', '내 등급', 'my_level'].some(keyword => itemHtml.includes(keyword))) {
                                isCurrent = true;
                            }
                            
                            result.levels.push({
                                index: index,
                                name: name,
                                condition: condition,
                                isCurrent: isCurrent
                            });
                        } catch (e) {
                            console.log('등급 처리 오류:', e);
                        }
                    });
                    
                    // 현재 활동 정보 수집 (여러 선택자 시도)
                    const activitySelectors = [
                        'dl.list_myinfo dd',
                        '.myinfo_area dd', 
                        '.member_info dd',
                        '.activity_info dd',
                        '.my_activity dd'
                    ];
                    
                    for (const selector of activitySelectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            elements.forEach(el => {
                                const text = el.textContent.trim();
                                if (text.includes('게시글')) {
                                    const match = text.match(/(\\d+)개/);
                                    if (match) result.currentActivity.posts = parseInt(match[1]);
                                } else if (text.includes('댓글')) {
                                    const match = text.match(/(\\d+)개/);
                                    if (match) result.currentActivity.comments = parseInt(match[1]);
                                } else if (text.includes('방문')) {
                                    const match = text.match(/(\\d+)회/);
                                    if (match) result.currentActivity.visits = parseInt(match[1]);
                                }
                            });
                            break; // 첫 번째 성공한 선택자에서 중단
                        }
                    }
                    
                    return result;
                """)
                
                self.logger.info(f"🔍 JavaScript로 {len(data['levels'])}개 등급 정보 수집 완료")
                
                # 2. 목표 등급 결정 (원본 로직)
                target_level = self._determine_target_level_from_data(driver, data['levels'], data['pageText'])
                
                # 3. 선택된 등급의 조건 추출
                if target_level and target_level['condition']:
                    self._parse_level_conditions(target_level['condition'], conditions)
                    conditions.target_level_name = target_level['name']
                    self.logger.info(f"🎯 목표 등급: {target_level['name']}")
                else:
                    self.logger.warning("❌ 목표 등급 조건을 찾을 수 없습니다.")
                
                # 4. 현재 활동 정보 적용
                if 'currentActivity' in data:
                    activity = data['currentActivity']
                    conditions.current_posts = activity.get('posts', 0)
                    conditions.current_comments = activity.get('comments', 0) 
                    conditions.current_visits = activity.get('visits', 0)
                    self.logger.info(f"📊 현재 활동: 게시글 {conditions.current_posts}개, 댓글 {conditions.current_comments}개, 방문 {conditions.current_visits}회")
                
            except Exception as extract_error:
                self.logger.warning(f"⚠️ 등급조건 추출 실패: {str(extract_error)}")
            
            if conditions.posts_required > 0 or conditions.comments_required > 0:
                self.logger.info(f"📊 등급조건: 게시글 {conditions.posts_required}개, 댓글 {conditions.comments_required}개, 방문 {conditions.visits_required}회")
                self.logger.info(f"🏃 현재 활동: 게시글 {conditions.current_posts}개, 댓글 {conditions.current_comments}개, 방문 {conditions.current_visits}회")
            
            return conditions if (conditions.posts_required > 0 or conditions.comments_required > 0 or conditions.visits_required > 0) else None
            
        except Exception as e:
            self.logger.error(f"❌ 등급조건 정보 추출 오류: {str(e)}")
            return None
        finally:
            # 원래 프레임으로 돌아가기
            self.web_driver_manager.switch_to_default_content(driver)
    
    def _check_levelup_achievement_status(self, driver: webdriver.Chrome) -> str:
        """등급 달성 여부 확인 (글쓰기 가능 여부로 판단) - 정확한 판단"""
        try:
            current_url = driver.current_url
            self.logger.info(f"🔍 현재 URL 확인: {current_url}")
            
            # 0. Alert 확인 (글쓰기 조건 등) - 최우선!
            try:
                alert = driver.switch_to.alert
                alert_text = alert.text
                self.logger.info(f"🚨 Alert 감지: {alert_text}")  # warning → info
                
                # 글쓰기 조건 Alert 확인
                writing_condition_messages = [
                    "글쓰기 조건이 있습니다",
                    "게시글을 작성하시려면",
                    "카페 방문",
                    "댓글 작성을 하셔야합니다"
                ]
                
                for condition_msg in writing_condition_messages:
                    if condition_msg in alert_text:
                        alert.accept()  # Alert 닫기
                        self.logger.warning(f"❌ 글쓰기 조건 카페 감지: {alert_text}")
                        return "writing_conditions_required"
                
                # 기타 Alert는 닫고 계속 진행
                alert.accept()
                
            except Exception as alert_error:
                # Alert 없으면 계속 진행 (에러로 로그하지 않음)
                pass

            # 1. 먼저 페이지 텍스트에서 제한 메시지 확인 (우선 순위!)
            try:
                page_text = driver.page_source
                
                # 등급 제한 메시지들 (더 정확한 패턴)
                restriction_messages = [
                    "등급이 되시면 읽기가 가능한 게시판",
                    "등급이 되시면",
                    "등급이 부족",
                    "글쓰기 권한이 없습니다", 
                    "등급 조건을 만족",
                    "레벨업이 필요",
                    "등업에 관련된",
                    "새로가입한 신규 멤버",
                    "등급이 되어야",
                    "등급 이상만",
                    "멤버만 이용",
                    "권한이 없음",
                    "글쓰기 조건이 있습니다",  # 글쓰기 조건 추가
                    "LowLevelAccessGuide"  # 등급 안내 페이지 클래스
                ]
                
                for msg in restriction_messages:
                    if msg in page_text:
                        if "글쓰기 조건" in msg:
                            self.logger.warning(f"❌ 글쓰기 조건 카페 발견: '{msg}'")
                            return "writing_conditions_required"
                        else:
                            self.logger.warning(f"⚠️ 등급 제한 메시지 발견: '{msg}' - 등급 미달성")
                            return "not_achieved"
                
            except Exception as page_error:
                self.logger.warning(f"⚠️ 페이지 텍스트 확인 실패: {str(page_error)}")
            
            # 2. URL 기반 판단 (제한 메시지가 없는 경우에만)
            if "write" in current_url and "cafes" in current_url and "write-error" not in current_url:
                # 3. 실제 글쓰기 폼 존재 확인
                write_form_selectors = [
                    "textarea[placeholder*='제목']",
                    "input[placeholder*='제목']", 
                    ".se-awp-wrap",
                    "div[contenteditable='true']",
                    "form[action*='write']",
                    ".write_form"
                ]
                
                form_found = False
                for selector in write_form_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            for element in elements:
                                if element.is_displayed():
                                    self.logger.info(f"✅ 글쓰기 폼 발견: {selector} - 등급 달성")
                                    form_found = True
                                    break
                        if form_found:
                            break
                    except:
                        continue
                
                if form_found:
                    self.logger.info("✅ 글쓰기 페이지 접근 성공 + 폼 활성화 = 등급 달성 확정!")
                    return "already_achieved"
            
            # 4. 에러 페이지 확인
            error_indicators = [
                "오류가 발생했습니다", "접근 권한이 없습니다", "페이지를 찾을 수 없습니다",
                "write-error"  # URL에 에러 표시
            ]
            
            for indicator in error_indicators:
                if indicator in current_url or indicator in driver.page_source:
                    self.logger.warning(f"❌ 접근 제한 발견: '{indicator}'")
                    return "not_achieved"
            
            # 기본적으로 등급 미달성으로 판단
            self.logger.warning("⚠️ 등급 달성 여부 불명확 - 미달성으로 판단")
            return "not_achieved"
            
        except Exception as e:
            self.logger.error(f"❌ 등급 달성 여부 확인 실패: {str(e)}")
            return "unknown"
    
    def _collect_all_levels(self, driver: webdriver.Chrome, level_items: List) -> List[Dict[str, Any]]:
        """모든 등급 정보 수집"""
        all_levels = []
        current_level_index = -1
        
        for i, item in enumerate(level_items):
            try:
                # 등급명 확인
                level_name_element = item.find_element(By.CSS_SELECTOR, ".img .txt")
                level_name = level_name_element.text.strip()
                
                # 등급 조건 추출
                level_condition = None
                desc_elements = item.find_elements(By.CSS_SELECTOR, "div.desc p")
                for desc in desc_elements:
                    desc_text = desc.text.strip()
                    if desc_text and "자동등업" in desc_text:
                        level_condition = desc_text
                        break
                
                # 자동등업 조건이 없으면 마지막 p 태그 사용
                if not level_condition and desc_elements:
                    level_condition = desc_elements[-1].text.strip()
                
                # 현재 등급인지 확인
                is_current = self._is_current_level(item)
                
                all_levels.append({
                    'index': i,
                    'name': level_name,
                    'condition': level_condition,
                    'is_current': is_current,
                    'element': item
                })
                
                if is_current:
                    current_level_index = i
                    
                self.logger.info(f"📋 등급 {i+1}: {level_name} {'(현재 등급)' if is_current else ''}")
                if level_condition:
                    self.logger.info(f"    📝 조건: {level_condition}")
                    
            except Exception as e:
                self.logger.warning(f"⚠️ 등급 {i+1} 정보 추출 실패: {str(e)}")
                continue
        
        return all_levels
    
    def _is_current_level(self, item) -> bool:
        """현재 등급인지 확인"""
        try:
            item_class = item.get_attribute("class") or ""
            item_html = item.get_attribute("outerHTML")
            
            # 방법 1: CSS 클래스 확인
            if any(cls in item_class for cls in ["on", "current", "active", "my_level"]):
                return True
            
            # 방법 2: 현재 등급 아이콘 확인
            if item.find_elements(By.CSS_SELECTOR, ".ico_now, .current, .active, .my_level"):
                return True
            
            # 방법 3: 텍스트에서 현재 표시 확인
            if any(keyword in item_html for keyword in ["현재", "내 등급", "my_level"]):
                return True
                
            # 방법 4: 설명 텍스트에서 현재 표시 확인
            for desc_elem in item.find_elements(By.CSS_SELECTOR, "div.desc"):
                desc_text = desc_elem.text.strip()
                if any(keyword in desc_text for keyword in ["현재", "내 등급", "달성"]):
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _determine_target_level(self, driver: webdriver.Chrome, all_levels: List[Dict]) -> Optional[Dict]:
        """목표 등급 조건 결정"""
        target_level = None
        
        # 1순위: 게시판 접근 메시지에서 요구하는 등급 먼저 확인
        self.logger.info("🔍 1순위: 목표 게시판이 요구하는 등급을 먼저 확인합니다.")
        required_level_name = self._extract_required_level_from_page(driver)
        
        if required_level_name:
            # 필요한 등급 찾기
            for level in all_levels:
                if required_level_name in level['name'] and level['condition'] and "자동등업" in level['condition']:
                    target_level = level
                    self.logger.info(f"🎯 목표 게시판 요구 등급: {target_level['name']}")
                    break
        
        # 2순위: 현재 등급에서 다음 등급 찾기
        if not target_level:
            self.logger.info("🔍 2순위: 현재 등급에서 다음 등급을 찾습니다.")
            current_level_index = -1
            
            for i, level in enumerate(all_levels):
                if level['is_current']:
                    current_level_index = i
                    break
            
            if current_level_index >= 0:
                self.logger.info(f"✅ 현재 등급 확인: {all_levels[current_level_index]['name']}")
                
                for i in range(current_level_index + 1, len(all_levels)):
                    if all_levels[i]['condition'] and "자동등업" in all_levels[i]['condition']:
                        target_level = all_levels[i]
                        self.logger.info(f"🎯 다음 목표 등급: {target_level['name']}")
                        break
            else:
                # 페이지에서 현재 등급 직접 추출 시도
                current_level_name = self._extract_current_level_from_page(driver)
                if current_level_name:
                    self.logger.info(f"✅ 페이지에서 현재 등급 확인: {current_level_name}")
                    target_level = self._find_next_level_by_name(all_levels, current_level_name)
        
        # 3순위: 첫 번째 자동등업 조건 사용
        if not target_level:
            self.logger.info("🔍 3순위: 첫 번째 자동등업 조건을 사용합니다.")
            for level in all_levels:
                if level['condition'] and "자동등업" in level['condition']:
                    target_level = level
                    self.logger.info(f"🎯 첫 번째 자동등업 등급: {target_level['name']}")
                    break
        
        return target_level
    
    def _extract_required_level_from_page(self, driver: webdriver.Chrome) -> Optional[str]:
        """페이지에서 목표 게시판 접근에 필요한 등급명 추출"""
        try:
            page_text = driver.page_source
            
            # HTML 태그를 제거한 텍스트로 매칭
            clean_text = re.sub(r'<[^>]+>', '', page_text)
            clean_text = re.sub(r'&\w+;', ' ', clean_text)
            
            patterns = [
                r'([가-힣]+)\s*등급이\s*되시면\s*읽기가\s*가능한',
                r'([가-힣]+)\s*등급이\s*되어야\s*읽기가\s*가능',
                r'([가-힣]+)\s*등급\s*이상\s*읽기\s*가능',
                r'([가-힣]+)\s*등급\s*이상이\s*되어야',
                r'([가-힣]+)\s*등급\s*회원만\s*읽기\s*가능',
                r'([가-힣]+)\s*등급이.+?되시면',
                r'([가-힣]+)\s*등급이\s*되시면'
            ]
            
            # HTML 패턴 먼저 시도
            html_patterns = [
                r'<strong[^>]*>([가-힣]+)</strong>\s*등급이\s*되시면',
                r'class=["\']emph["\'][^>]*>([가-힣]+)</[^>]*>\s*등급이\s*되시면'
            ]
            
            for i, pattern in enumerate(html_patterns):
                match = re.search(pattern, page_text)
                if match:
                    required_level = match.group(1).strip()
                    self.logger.info(f"🎯 필요 등급 발견: '{required_level}' (HTML 패턴 {i+1})")
                    return required_level
            
            # 정제된 텍스트에서 매칭 시도
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, clean_text)
                if match:
                    required_level = match.group(1).strip()
                    self.logger.info(f"🎯 필요 등급 발견: '{required_level}' (정제 패턴 {i+1})")
                    return required_level
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 필요 등급 추출 중 오류: {str(e)}")
            return None
    
    def _extract_current_level_from_page(self, driver: webdriver.Chrome) -> Optional[str]:
        """페이지에서 현재 등급명 추출"""
        try:
            page_text = driver.page_source
            clean_text = re.sub(r'<[^>]+>', '', page_text)
            clean_text = re.sub(r'&\w+;', ' ', clean_text)
            
            patterns = [
                r'현재\s+[가-힣a-zA-Z0-9]+님은\s+([가-힣]+)\s*등급이시며',
                r'현재\s+[가-힣a-zA-Z0-9]+님은\s+([가-힣]+)\s*등급입니다',
                r'현재\s+([가-힣]+)\s*등급이며',
                r'현재\s*등급:\s*([가-힣]+)',
                r'내\s*등급:\s*([가-힣]+)',
                r'현재.+?([가-힣]+)\s*등급이시며',
                r'([가-힣]+)\s*등급이시며'
            ]
            
            # HTML 패턴 먼저 시도
            html_patterns = [
                r'현재\s*<em[^>]*>[^<]+</em>님은\s*<strong[^>]*>([가-힣]+)</strong>\s*등급이시며',
                r'현재\s*<em[^>]*class=["\']id["\'][^>]*>[^<]+</em>님은\s*<strong[^>]*class=["\']level["\'][^>]*>([가-힣]+)</strong>\s*등급이시며'
            ]
            
            for i, pattern in enumerate(html_patterns):
                match = re.search(pattern, page_text)
                if match:
                    current_level = match.group(1).strip()
                    self.logger.info(f"🎯 현재 등급 발견: '{current_level}' (HTML 패턴 {i+1})")
                    return current_level
            
            # 정제된 텍스트에서 매칭
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, clean_text)
                if match:
                    current_level = match.group(1).strip()
                    self.logger.info(f"🎯 현재 등급 발견: '{current_level}' (정제 패턴 {i+1})")
                    return current_level
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 현재 등급 추출 중 오류: {str(e)}")
            return None
    
    def _find_next_level_by_name(self, all_levels: List[Dict], current_level_name: str) -> Optional[Dict]:
        """현재 등급명으로 다음 등급 찾기"""
        for i, level in enumerate(all_levels):
            if current_level_name in level['name']:
                # 다음 등급부터 자동등업 조건 찾기
                for j in range(i + 1, len(all_levels)):
                    if all_levels[j]['condition'] and "자동등업" in all_levels[j]['condition']:
                        self.logger.info(f"🎯 다음 목표 등급: {all_levels[j]['name']}")
                        return all_levels[j]
                break
        return None
    
    def _determine_target_level_from_data(self, driver: webdriver.Chrome, levels_data: List[Dict], page_text: str) -> Optional[Dict]:
        """JavaScript로 수집된 데이터에서 목표 등급 결정"""
        target_level = None
        
        # 1순위: 게시판 접근 메시지에서 요구하는 등급 확인
        required_level_name = self._extract_required_level_from_text(page_text)
        
        if required_level_name:
            for level in levels_data:
                if required_level_name in level['name'] and level['condition']:
                    if "자동등업" in level['condition']:
                        target_level = level
                        self.logger.info(f"🎯 목표 게시판 요구 등급: {target_level['name']} (자동등업)")
                        break
                    elif "등업게시판" in level['condition']:
                        self.logger.warning(f"⚠️ 목표 등급 '{level['name']}'은 등업게시판 방식으로 자동화 불가능합니다.")
                        self.logger.warning(f"⚠️ 수동으로 등업 신청이 필요한 카페입니다: {level['condition']}")
                        self.logger.info(f"🚫 해당 카페는 작업에서 제외됩니다.")
                        return None
        
        # 2순위: 현재 등급에서 다음 등급 찾기 (자동등업만)
        if not target_level:
            current_level_index = -1
            for i, level in enumerate(levels_data):
                if level['isCurrent']:
                    current_level_index = i
                    break
            
            if current_level_index >= 0:
                self.logger.info(f"✅ 현재 등급 확인: {levels_data[current_level_index]['name']}")
                for i in range(current_level_index + 1, len(levels_data)):
                    if levels_data[i]['condition'] and "자동등업" in levels_data[i]['condition']:
                        target_level = levels_data[i]
                        self.logger.info(f"🎯 다음 목표 등급: {target_level['name']} (자동등업)")
                        break
        
        # 3순위: 첫 번째 등업 조건 사용 (자동등업만 지원)
        if not target_level:
            # 자동등업만 검색 (등업게시판은 자동화 불가능)
            for level in levels_data:
                if level['condition'] and "자동등업" in level['condition']:
                    target_level = level
                    self.logger.info(f"🎯 첫 번째 자동등업 등급: {target_level['name']}")
                    break
            
            # 자동등업이 없으면 등업게시판 확인하고 경고
            if not target_level:
                for level in levels_data:
                    if level['condition'] and "등업게시판" in level['condition']:
                        self.logger.warning(f"⚠️ '{level['name']}' 등급은 등업게시판 방식으로 자동화 불가능합니다.")
                        self.logger.warning(f"⚠️ 수동으로 등업 신청이 필요한 카페입니다: {level['condition']}")
                        self.logger.info(f"🚫 해당 카페는 작업에서 제외됩니다.")
                        return None  # 작업 불가능한 카페로 판단
        
        return target_level
    
    def _extract_required_level_from_text(self, text: str) -> Optional[str]:
        """텍스트에서 필요한 등급명 추출"""
        try:
            patterns = [
                r'([가-힣]+)\s*등급이\s*되시면\s*읽기가\s*가능한',
                r'([가-힣]+)\s*등급이\s*되어야\s*읽기가\s*가능',
                r'([가-힣]+)\s*등급\s*이상\s*읽기\s*가능',
                r'([가-힣]+)\s*등급\s*이상이\s*되어야',
                r'([가-힣]+)\s*등급\s*회원만\s*읽기\s*가능',
                r'([가-힣]+)\s*등급이\s*되시면'
            ]
            
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, text)
                if match:
                    required_level = match.group(1).strip()
                    self.logger.info(f"🎯 필요 등급 발견: '{required_level}' (패턴 {i+1})")
                    return required_level
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 필요 등급 추출 중 오류: {str(e)}")
            return None
    
    def _parse_level_conditions(self, condition_text: str, conditions: LevelupConditions) -> None:
        """등급 조건 텍스트 파싱"""
        self.logger.info(f"📝 목표 등급 조건: {condition_text}")
        
        post_match = re.search(r'게시글수\s*(\d+)개', condition_text)
        comment_match = re.search(r'댓글수\s*(\d+)개', condition_text)
        visit_match = re.search(r'방문수\s*(\d+)회', condition_text)
        
        if post_match:
            conditions.posts_required = int(post_match.group(1))
        if comment_match:
            conditions.comments_required = int(comment_match.group(1))
        if visit_match:
            conditions.visits_required = int(visit_match.group(1))
        
        self.logger.info(f"🎯 추출된 조건: 게시글 {conditions.posts_required}개, 댓글 {conditions.comments_required}개, 방문 {conditions.visits_required}회")
    
    def _extract_current_activity(self, driver: webdriver.Chrome, conditions: LevelupConditions) -> None:
        """현재 활동정보 추출 (iframe 안에서 실행)"""
        try:
            activity_selectors = [
                "dl.list_myinfo dd",
                ".myinfo_area dd",
                ".member_info dd",
                ".activity_info dd",
                ".my_activity dd"
            ]
            
            for selector in activity_selectors:
                try:
                    myinfo_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if myinfo_elements:
                        for element in myinfo_elements:
                            text = element.text.strip()
                            if '게시글' in text:
                                post_match = re.search(r'(\d+)개', text)
                                if post_match:
                                    conditions.current_posts = int(post_match.group(1))
                            elif '댓글수' in text or '댓글' in text:
                                comment_match = re.search(r'(\d+)개', text)
                                if comment_match:
                                    conditions.current_comments = int(comment_match.group(1))
                            elif '방문수' in text or '방문' in text:
                                visit_match = re.search(r'(\d+)회', text)
                                if visit_match:
                                    conditions.current_visits = int(visit_match.group(1))
                        break
                except:
                    continue
                    
        except Exception as e:
            self.logger.warning(f"⚠️ 활동정보 추출 실패: {str(e)}")
    
    def _extract_levelup_without_iframe(self, driver: webdriver.Chrome) -> Optional[LevelupConditions]:
        """iframe 없이 등급조건 추출 시도 - 광역 텍스트 파싱"""
        try:
            self.logger.info("🔄 iframe 없이 등급조건 추출 시도...")
            
            conditions = LevelupConditions()
            
            # 광역 텍스트 스캔 (원본 방식)
            txt = driver.execute_script("return document.body.innerText || ''")
            
            # 느슨한 정규식으로 조건 추출 (관대한 패턴)
            def pick_number(pattern: str, text: str) -> int:
                match = re.search(pattern, text)
                return int(match.group(1)) if match else 0
            
            # 필요 조건 추출 (여러 패턴 시도)
            conditions.posts_required = pick_number(r'게시글\s*수?\s*:?\s*(\d+)\s*개', txt)
            conditions.comments_required = pick_number(r'댓글\s*수?\s*:?\s*(\d+)\s*개', txt)  
            conditions.visits_required = pick_number(r'방문\s*수?\s*:?\s*(\d+)\s*회', txt)
            
            # 현재 활동 추출
            conditions.current_posts = pick_number(r'내?\s*게시글\s*:?\s*(\d+)\s*개', txt)
            conditions.current_comments = pick_number(r'내?\s*댓글\s*:?\s*(\d+)\s*개', txt)
            conditions.current_visits = pick_number(r'내?\s*방문\s*:?\s*(\d+)\s*회', txt)
            
            if conditions.posts_required > 0 or conditions.comments_required > 0 or conditions.visits_required > 0:
                self.logger.info(f"✅ 광역 파싱 성공: 게시글 {conditions.posts_required}개, 댓글 {conditions.comments_required}개, 방문 {conditions.visits_required}회")
                return conditions
            else:
                self.logger.warning("❌ 광역 파싱에서도 등급조건 추출 실패")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ 광역 파싱 실패: {str(e)}")
            return None
    
    def extract_cafe_numeric_id(self, cafe_info, driver: webdriver.Chrome) -> Optional[str]:
        """카페의 숫자 ID 추출"""
        try:
            cafe_url = f"https://cafe.naver.com/{cafe_info.cafe_id}"
            self.logger.info(f"🌐 카페 페이지로 이동: {cafe_url}")
            
            driver.get(cafe_url)
            time.sleep(3)
            
            # 페이지 로드 확인
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
                try:
                    match = re.search(pattern, page_source)
                    if match:
                        cafe_id = match.group(1)
                        self.logger.info(f"✅ 카페 숫자 ID 발견: {cafe_id}")
                        return cafe_id
                except Exception:
                    continue
            
            self.logger.warning("⚠️ 카페 숫자 ID를 찾을 수 없습니다.")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 카페 ID 추출 중 예외 발생: {str(e)}")
            return None


# 전역 등급 조건 추출기 인스턴스
levelup_extractor = LevelupExtractor()
