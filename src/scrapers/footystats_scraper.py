"""
FootyStats fixtures
"""

import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import json

from ..utils.scraper_base import BaseScraper
from ..utils.config import config
from ..utils.logger import get_logger

class FootyStatsScraper(BaseScraper):
    
    def __init__(self):
        super().__init__('footystats')
        self.base_url = config.SOURCES.get('footystats', {}).get('base_url', 'https://footystats.org')
        self.fixtures_url = config.SOURCES.get('footystats', {}).get('fixtures_url', 
                                              'https://footystats.org/de/germany/3-liga/fixtures')
    
    def scrape_fixtures(self, target_spieltag: int) -> List[Dict[str, Any]]:
        """
        Scrape fixtures for a specific spieltag
        
        Args:
            target_spieltag: Spieltag number to scrape
            
        Returns:
            List of fixture dictionaries
        """
        self.logger.info(f"🏈 Scraping FootyStats fixtures for Spieltag {target_spieltag}")
        
        response = self.make_request(self.fixtures_url)
        if not response:
            self.logger.error("❌ Failed to get response from FootyStats")
            return []
        
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Save a small test sample instead of full HTML
            self._save_test_sample(soup, target_spieltag)
            
            # Find match tables using the correct selector from your HTML
            match_tables = soup.select('div.full-matches-table')
            
            if not match_tables:
                self.logger.error("❌ No match tables found with selector 'div.full-matches-table'")
                # Try alternative selectors
                alt_selectors = [
                    'div[class*="matches-table"]',
                    'table.matches-table',
                    'div[data-game-week]'
                ]
                for selector in alt_selectors:
                    match_tables = soup.select(selector)
                    if match_tables:
                        self.logger.info(f"✅ Found tables with alternative selector: {selector}")
                        break
                
                if not match_tables:
                    self.logger.error("❌ No match tables found with any selector")
                    return []
            
            fixtures = []
            self.logger.debug(f"Found {len(match_tables)} match tables")
            
            for table_div in match_tables:
                table_fixtures = self._extract_fixtures_from_table(table_div, target_spieltag)
                fixtures.extend(table_fixtures)
            
            # Normalize team names
            fixtures = self.normalize_team_names(fixtures)
            
            # Log detailed results
            self._log_scraping_results(fixtures, target_spieltag)
            
            return fixtures
            
        except Exception as e:
            self.logger.error(f"❌ Error parsing FootyStats response: {e}", exc_info=True)
            return []
    
    def _save_test_sample(self, soup: BeautifulSoup, spieltag: int):
        """Save a small test sample for debugging instead of full HTML"""
        try:
            # Find the first match table and extract just that section
            match_table = soup.select_one('div.full-matches-table')
            if match_table:
                # Get header info
                header = match_table.select_one('h2')
                header_text = header.get_text(strip=True) if header else "No header found"
                
                # Get first few matches
                matches = match_table.select('tr.match')[:3]  # Just first 3 matches
                
                sample_data = {
                    'timestamp': datetime.now().isoformat(),
                    'spieltag_target': spieltag,
                    'header_found': header_text,
                    'matches_found': len(match_table.select('tr.match')),
                    'sample_matches': []
                }
                
                for match in matches:
                    match_data = {
                        'html': str(match)[:500] + "..." if len(str(match)) > 500 else str(match),
                        'date_cell': match.select_one('td.date').get_text(strip=True) if match.select_one('td.date') else "No date",
                        'home_team': self._extract_team_name(match.select_one('td.team-home')),
                        'away_team': self._extract_team_name(match.select_one('td.team-away')),
                        'score': match.select_one('td.status .ft-score').get_text(strip=True) if match.select_one('td.status .ft-score') else "No score"
                    }
                    sample_data['sample_matches'].append(match_data)
                
                # Save to JSON file
                with open(f'footystats_test_sample_spieltag_{spieltag}.json', 'w', encoding='utf-8') as f:
                    json.dump(sample_data, f, indent=2, ensure_ascii=False)
                
                self.logger.info(f"📄 Saved test sample to footystats_test_sample_spieltag_{spieltag}.json")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Could not save test sample: {e}")
    
    def _extract_fixtures_from_table(self, table_div, target_spieltag: int) -> List[Dict[str, Any]]:
        """Extract fixtures from a table div - FIXED VERSION"""
        fixtures = []
        
        # Extract spieltag info from header
        header = table_div.select_one('.invisible-header h2')
        if not header:
            header = table_div.select_one('h2')
        
        spieltag_info = self._parse_header(header, target_spieltag)
        if not spieltag_info['matches_target']:
            return fixtures
        
        # Find match rows - use the correct selector from your HTML
        match_rows = table_div.select('tr.match.complete')
        
        self.logger.debug(f"Found {len(match_rows)} completed matches in table")
        
        for row in match_rows:
            fixture = self._parse_fixture_row(row, spieltag_info)
            if fixture:
                fixtures.append(fixture)
                self.logger.debug(f"✅ Parsed: {fixture['home_team']} vs {fixture['away_team']}")
            else:
                self.logger.debug("⚠️ Failed to parse fixture row")
        
        return fixtures
    
    def _parse_header(self, header, target_spieltag: int) -> Dict[str, Any]:
        """Parse header to extract spieltag information"""
        info = {
            'spieltag': "Unknown",
            'spieltag_date': "",
            'matches_target': False
        }
        
        if not header:
            self.logger.warning("⚠️ No header found in table")
            return info
        
        header_text = header.get_text(strip=True)
        self.logger.debug(f"Header text: '{header_text}'")
        
        # Parse "Spieltag 1 - 1/8/2025" format
        if ' - ' in header_text:
            parts = header_text.split(' - ')
            spieltag_part = parts[0].strip()
            date_part = parts[1].strip() if len(parts) > 1 else ""
            
            # Extract spieltag number
            match = re.search(r'Spieltag\s+(\d+)', spieltag_part, re.IGNORECASE)
            if match:
                spieltag_num = int(match.group(1))
                info['spieltag'] = str(spieltag_num)
                info['spieltag_date'] = date_part
                info['matches_target'] = (spieltag_num == target_spieltag)
                
                self.logger.debug(f"Parsed Spieltag {spieltag_num}, target: {target_spieltag}, matches: {info['matches_target']}")
            else:
                self.logger.warning(f"⚠️ Could not parse spieltag number from: '{spieltag_part}'")
        else:
            self.logger.warning(f"⚠️ Unexpected header format: '{header_text}'")
        
        return info
    
    def _parse_fixture_row(self, row, spieltag_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse a single fixture row - FIXED VERSION"""
        try:
            fixture = {
                'spieltag': spieltag_info['spieltag'],
                'spieltag_date': spieltag_info['spieltag_date'],
                'match_date': '',
                'match_time': '',
                'home_team': '',
                'away_team': '',
                'home_goals': '',
                'away_goals': '',
                'stats_link': ''
            }
            
            # Extract date and time using the specific structure from your HTML
            date_cell = row.select_one('td.date')
            if date_cell:
                # Look for the timezone span with the correct class
                date_span = date_cell.select_one('span.timezone-convert-match-month')
                if date_span:
                    date_text = date_span.get_text(strip=True)  # "1/8 19:00"
                    if ' ' in date_text:
                        date_part, time_part = date_text.split(' ', 1)
                        fixture['match_date'] = date_part
                        fixture['match_time'] = time_part
                    else:
                        fixture['match_date'] = date_text
            
            # Extract home team - CORRECTED based on your HTML structure
            home_cell = row.select_one('td.team-home')
            if home_cell:
                fixture['home_team'] = self._extract_team_name(home_cell)
            
            # Extract away team - CORRECTED based on your HTML structure  
            away_cell = row.select_one('td.team-away')
            if away_cell:
                fixture['away_team'] = self._extract_team_name(away_cell)
            
            # Extract score - using the specific structure from your HTML
            status_cell = row.select_one('td.status')
            if status_cell:
                score_elem = status_cell.select_one('span.ft-score')
                if score_elem:
                    score_text = score_elem.get_text(strip=True)  # "1 - 1"
                    if ' - ' in score_text:
                        home_score, away_score = score_text.split(' - ')
                        fixture['home_goals'] = home_score.strip()
                        fixture['away_goals'] = away_score.strip()
            
            # Extract stats link
            link_cell = row.select_one('td.link')
            if not link_cell:
                # Try alternative selector
                link_cell = row.select_one('a[href*="stats"]')
            
            if link_cell:
                link_elem = link_cell.select_one('a') if link_cell.name != 'a' else link_cell
                if link_elem and link_elem.get('href'):
                    href = link_elem.get('href')
                    if href.startswith('/'):
                        fixture['stats_link'] = urljoin(self.base_url, href)
                    elif href.startswith('http'):
                        fixture['stats_link'] = href
                    else:
                        fixture['stats_link'] = urljoin(self.base_url, '/' + href)
            
            # Validate fixture has required data
            if fixture['home_team'] and fixture['away_team']:
                if fixture['home_team'] != fixture['away_team']:
                    return fixture
                else:
                    self.logger.warning(f"⚠️ Same team for home and away: '{fixture['home_team']}'")
            else:
                self.logger.warning(f"⚠️ Missing team names - Home: '{fixture['home_team']}', Away: '{fixture['away_team']}'")
                
        except Exception as e:
            self.logger.error(f"❌ Error parsing fixture row: {e}", exc_info=True)
        
        return None
    
    def _extract_team_name(self, team_cell) -> str:
        """Extract team name from team cell - FIXED based on your HTML structure"""
        if not team_cell:
            return ""
        
        try:
            # Based on your HTML, team names are in <a> tags with <span> inside
            # <a class="ar" href="/de/clubs/rot-weiss-essen-6298"><span>Rot Weiss Essen</span></a>
            
            # First try to find the span inside the link
            team_span = team_cell.select_one('a span')
            if team_span:
                team_name = team_span.get_text(strip=True)
                if team_name:
                    return team_name
            
            # Fallback: try just the link text
            team_link = team_cell.select_one('a')
            if team_link:
                team_name = team_link.get_text(strip=True)
                if team_name:
                    return team_name
            
            # Final fallback: cell text
            team_name = team_cell.get_text(strip=True)
            # Clean up any extra text (like "Quoten" from your HTML)
            lines = team_name.split('\n')
            for line in lines:
                line = line.strip()
                if line and line != "Quoten" and not line.isdigit():
                    return line
                    
        except Exception as e:
            self.logger.warning(f"⚠️ Error extracting team name: {e}")
        
        return ""
    
    def _log_scraping_results(self, fixtures: List[Dict[str, Any]], target_spieltag: int):
        """Log detailed scraping results for monitoring"""
        self.logger.info(f"📊 SCRAPING RESULTS for Spieltag {target_spieltag}:")
        self.logger.info(f"  - Total fixtures found: {len(fixtures)}")
        
        if fixtures:
            # Log each fixture
            for i, fixture in enumerate(fixtures, 1):
                self.logger.info(f"  {i}. {fixture['home_team']} vs {fixture['away_team']} "
                               f"({fixture['home_goals']}-{fixture['away_goals']}) "
                               f"on {fixture['match_date']} {fixture['match_time']}")
            
            # Check for missing data
            missing_data = []
            for fixture in fixtures:
                missing = []
                if not fixture['home_team']:
                    missing.append('home_team')
                if not fixture['away_team']:
                    missing.append('away_team')
                if not fixture['match_date']:
                    missing.append('match_date')
                if not fixture['home_goals']:
                    missing.append('home_goals')
                if not fixture['away_goals']:
                    missing.append('away_goals')
                
                if missing:
                    missing_data.append({
                        'fixture': f"{fixture['home_team']} vs {fixture['away_team']}",
                        'missing': missing
                    })
            
            if missing_data:
                self.logger.warning(f"⚠️ {len(missing_data)} fixtures have missing data:")
                for item in missing_data:
                    self.logger.warning(f"  - {item['fixture']}: missing {', '.join(item['missing'])}")
            else:
                self.logger.info("✅ All fixtures have complete data")
        else:
            self.logger.warning("⚠️ No fixtures scraped!")
    
    def test_scraper(self, target_spieltag: int = 1) -> Dict[str, Any]:
        """Test the scraper and return diagnostic information"""
        self.logger.info(f"🧪 Testing FootyStats scraper for Spieltag {target_spieltag}")
        
        test_results = {
            'success': False,
            'fixtures_count': 0,
            'errors': [],
            'warnings': [],
            'sample_fixtures': [],
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            fixtures = self.scrape_fixtures(target_spieltag)
            test_results['fixtures_count'] = len(fixtures)
            test_results['sample_fixtures'] = fixtures[:3]  # First 3 fixtures
            test_results['success'] = len(fixtures) > 0
            
            if not fixtures:
                test_results['errors'].append("No fixtures scraped")
            
            # Validate fixture data
            for fixture in fixtures[:5]:  # Check first 5
                if not fixture['home_team']:
                    test_results['warnings'].append("Missing home team name")
                if not fixture['away_team']:
                    test_results['warnings'].append("Missing away team name")
                if fixture['home_team'] == fixture['away_team']:
                    test_results['warnings'].append("Home and away team names are identical")
                    
        except Exception as e:
            test_results['errors'].append(str(e))
        
        self.logger.info(f"🧪 Test complete: {test_results}")
        return test_results


class FootyStatsXGScraper:
    """Scraper for xG data from FootyStats match pages - Enhanced version"""
    
    def __init__(self):
        self.logger = get_logger('footystats.xg')
    
    def scrape_match_xg(self, url: str) -> Optional[Dict[str, str]]:
        """
        Scrape xG data from a FootyStats match page
        
        Args:
            url: Match stats URL
            
        Returns:
            Dictionary with team names and xG values or None if failed
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            import chromedriver_autoinstaller
            import time
            import random
        except ImportError as e:
            self.logger.error(f"❌ Missing required packages for xG scraping: {e}")
            return None
        
        # Setup Chrome driver
        try:
            chromedriver_autoinstaller.install()
        except Exception as e:
            self.logger.error(f"❌ Failed to install chromedriver: {e}")
            return None
            
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = None
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.logger.info(f"🎯 Scraping xG from: {url}")
            driver.get(url)
            
            # Wait for page load
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Random wait
            wait_time = random.uniform(2, 5)
            time.sleep(wait_time)
            
            # Close popups
            self._close_popups(driver)
            
            # Extract team names and xG values
            team_names = self._extract_team_names_from_url(url)
            if not team_names:
                team_names = self._extract_team_names_from_page(driver)
            
            xg_values = self._find_xg_values(driver)
            
            if len(xg_values) == 2 and team_names and len(team_names) == 2:
                result = {
                    'team_1_name': team_names[0],
                    'team_1_xG': xg_values[0],
                    'team_2_name': team_names[1],
                    'team_2_xG': xg_values[1]
                }
                self.logger.info(f"✅ xG extracted: {result}")
                return result
            else:
                self.logger.warning(f"⚠️ Incomplete xG data. Teams: {team_names}, xG: {xg_values}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error scraping xG: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def _close_popups(self, driver):
        """Close common popups"""
        popup_selectors = [
            "[class*='popup']", "[class*='modal']", "[class*='overlay']",
            "[id*='popup']", "[id*='modal']", ".cookie-banner", 
            ".gdpr-banner", "#cookieConsent", ".consent-banner",
            "[class*='cookie']", "[class*='privacy']"
        ]
        
        for selector in popup_selectors:
            try:
                popups = driver.find_elements(By.CSS_SELECTOR, selector)
                for popup in popups:
                    if popup.is_displayed():
                        close_buttons = popup.find_elements(By.CSS_SELECTOR, 
                                                          "[class*='close'], [class*='dismiss'], [class*='accept'], button")
                        for btn in close_buttons:
                            if btn.is_displayed():
                                btn.click()
                                time.sleep(1)
                                break
            except:
                continue
    
    def _extract_team_names_from_url(self, url: str) -> Optional[List[str]]:
        """Extract team names from URL"""
        try:
            url_lower = url.lower()
            
            if '-vs-' in url_lower:
                url_parts = url.split('/')[-1].split('-vs-')
                if len(url_parts) >= 2:
                    team_1 = url_parts[0].split('/')[-1].replace('-', ' ').title()
                    team_2 = url_parts[1].split('-h2h')[0].split('#')[0].replace('-', ' ').title()
                    return [team_1, team_2]
                    
        except Exception as e:
            self.logger.warning(f"⚠️ Could not extract team names from URL: {e}")
        return None
    
    def _extract_team_names_from_page(self, driver) -> Optional[List[str]]:
        """Extract team names from page content"""
        try:
            team_selectors = [
                '.team-name', '.team-title', '[class*="team-name"]',
                'h1 .team', 'h2 .team', '.match-teams .team',
                '.home-team', '.away-team'
            ]
            
            for selector in team_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                names = [elem.text.strip() for elem in elements if elem.text.strip()]
                if len(names) >= 2:
                    return names[:2]
                    
        except Exception as e:
            self.logger.warning(f"⚠️ Could not extract team names from page: {e}")
        return None
    
    def _find_xg_values(self, driver) -> List[str]:
        """Find xG values on the page"""
        xg_values = []
        
        # Multiple strategies to find xG values
        strategies = [
            self._strategy_table_xg,
            self._strategy_xpath_xg,
            self._strategy_css_xg
        ]
        
        for strategy in strategies:
            try:
                values = strategy(driver)
                if len(values) >= 2:
                    return values[:2]
            except Exception as e:
                self.logger.debug(f"Strategy failed: {e}")
                continue
        
        return []
    
    def _strategy_table_xg(self, driver) -> List[str]:
        """Strategy 1: Table-based xG extraction"""
        xg_elements = driver.find_elements(By.XPATH, 
            "//tr[td[contains(translate(text(), 'XG', 'xg'), 'xg')]]/td[@class='item stat average']")
        return [x.text.strip() for x in xg_elements if x.text.strip() and re.match(r'^\d+(\.\d+)?$', x.text.strip())]
    
    def _strategy_xpath_xg(self, driver) -> List[str]:
        """Strategy 2: XPath-based xG extraction"""
        xg_containers = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'XG', 'xg'), 'xg')]")
        
        for container in xg_containers:
            try:
                parent = container.find_element(By.XPATH, "./..")
                siblings = parent.find_elements(By.XPATH, "./*")
                
                numeric_values = []
                for sibling in siblings:
                    text = sibling.text.strip()
                    if re.match(r'^\d+(\.\d+)?$', text):
                        numeric_values.append(text)
                
                if len(numeric_values) >= 2:
                    return numeric_values[:2]
            except:
                continue
        return []
    
    def _strategy_css_xg(self, driver) -> List[str]:
        """Strategy 3: CSS selector-based xG extraction"""
        xg_selectors = [
            '[class*="xg"] .value', '[class*="xG"] .value',
            '.stat-xg', '.xg-value', '.expected-goals',
            '[data-stat="xg"]', '[data-value*="xg"]'
        ]
        
        for selector in xg_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            values = [elem.text.strip() for elem in elements 
                     if elem.text.strip() and re.match(r'^\d+(\.\d+)?$', elem.text.strip())]
            if len(values) >= 2:
                return values[:2]
        return []