"""
FootyStats fixtures
"""

import os
import re
import csv
import time
import random
import chromedriver_autoinstaller
from pathlib import Path  
from datetime import datetime
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from ..utils.scraper_base import BaseScraper
from ..utils.config import config
from ..utils.logger import get_logger

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

class FootyStatsScraper(BaseScraper):
    def __init__(self):
        super().__init__('footystats')
        self.base_url = config.SOURCES.get('footystats', {}).get('base_url', 'https://footystats.org')
        self.fixtures_url = config.SOURCES.get('footystats', {}).get('fixtures_url', 
                                              'https://footystats.org/germany/3-liga/fixtures')
    
    def soccerway_to_footystats_spieltag(self, soccerway_spieltag):
        """
        Maps Soccerway Spieltag (1-37) to Footystats Spieltag (37-1).
        """
        return 38 - soccerway_spieltag
    
    def get_selenium_html_content(self, url):
        """Get HTML content as string (in-memory) with error handling"""
        driver = None
        try:
            chromedriver_autoinstaller.install()
            
            # Detect if running in GitHub Actions or similar CI environment
            is_ci = any(env in os.environ for env in ['GITHUB_ACTIONS', 'CI', 'BUILD_NUMBER'])
            
            user_agent = random.choice(USER_AGENTS)
            chrome_options = Options()
            
            if is_ci:
                # GitHub Actions / CI specific options
                self.logger.info("🤖 Detected CI environment - using enhanced headless configuration")
                chrome_options.add_argument('--headless=new')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--disable-web-security')
                chrome_options.add_argument('--disable-features=VizDisplayCompositor')
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-plugins')
                chrome_options.add_argument('--single-process')
                chrome_options.add_argument('--disable-background-timer-throttling')
                chrome_options.add_argument('--disable-renderer-backgrounding')
                chrome_options.add_argument('--disable-backgrounding-occluded-windows')
                chrome_options.add_argument('--memory-pressure-off')
                chrome_options.add_argument('--max_old_space_size=4096')
            else:
                # Local development
                self.logger.info("💻 Local development mode")
                chrome_options.add_argument('--headless')
            
            # Common options for both environments
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(f'user-agent={user_agent}')
            
            # Anti-detection options
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            driver = webdriver.Chrome(options=chrome_options)
            
            # Set timeouts based on environment
            timeout = 60 if is_ci else 30
            driver.set_page_load_timeout(timeout)
            driver.implicitly_wait(10)
            
            # Anti-detection script
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Set headers (might fail in CI, so wrap in try/catch)
            try:
                driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
                    'headers': {
                        'Referer': 'https://www.google.com/',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'DNT': '1'
                    }
                })
            except Exception as e:
                self.logger.warning(f"⚠️ Could not set extra headers (CI environment limitation): {e}")
            
            self.logger.info(f"Loading URL: {url}")
            driver.get(url)
            
            # Longer wait time in CI environments
            wait_time = 5 if is_ci else 3
            time.sleep(wait_time)
            
            # Get HTML content directly
            html_content = driver.page_source
            self.logger.info(f"✅ Retrieved HTML content ({len(html_content)} characters)")
            
            # Save HTML for debugging (but don't depend on it)
            try:
                html_debug_path = 'data/footystats/footystats_fixtures.html'
                os.makedirs(os.path.dirname(html_debug_path), exist_ok=True)
                with open(html_debug_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                self.logger.info(f"Debug: HTML saved to {html_debug_path}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not save debug HTML: {e}")
            
            return html_content

        except Exception as e:
            self.logger.error(f"❌ Error getting HTML with Selenium: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
    
    def parse_matches_from_html_content(self, html_content: str, footystats_spieltag: int, soccerway_spieltag: int):
        """
        Parse matches for a given Footystats Spieltag from HTML content string.
        Modified version of your existing parse_matches_from_html method.
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            week_div = soup.find('div', {'data-game-week': str(footystats_spieltag)})
            if not week_div:
                self.logger.warning(f'No game week {footystats_spieltag} found in HTML!')
                return []
                
            matches = []
            match_elements = week_div.select('ul.match.row')
            self.logger.info(f"Found {len(match_elements)} match elements for game week {footystats_spieltag}")
            
            for i, match_ul in enumerate(match_elements):
                try:
                    # Extract home team
                    home_team = None
                    home_a = match_ul.select_one('a.team.home')
                    if home_a:
                        home_span = home_a.select_one('span.hover-modal-parent')
                        if home_span:
                            home_team = home_span.get_text(strip=True)
                            # Normalize team name using config
                            home_team = config.normalize_team_name(home_team)
                        
                    # Extract away team
                    away_team = None
                    away_a = match_ul.select_one('a.team.away')
                    if away_a:
                        away_span = away_a.select_one('span.hover-modal-parent')
                        if away_span:
                            away_team = away_span.get_text(strip=True)
                            # Normalize team name using config
                            away_team = config.normalize_team_name(away_team)
                    
                    # Extract scores and URL
                    score_home = None
                    score_away = None
                    url = None
                    h2h_a = match_ul.select_one('a.h2h-link')
                    if h2h_a:
                        score_span = h2h_a.select_one('span.ft-score')
                        if score_span:
                            score_text = score_span.get_text(strip=True)
                            if score_text and '-' in score_text:
                                parts = score_text.split('-')
                                if len(parts) == 2:
                                    score_home = parts[0].strip()
                                    score_away = parts[1].strip()
                        url = 'https://footystats.org' + h2h_a.get('href', '')
                    
                    match_data = {
                        'spieltag': soccerway_spieltag,
                        'home_team': home_team,
                        'away_team': away_team,
                        'score_home': score_home,
                        'score_away': score_away,
                        'url': url
                    }
                    matches.append(match_data)
                    
                except Exception as e:
                    self.logger.warning(f"Error parsing match {i+1}: {e}")
                    continue
                    
            self.logger.info(f"Successfully parsed {len(matches)} matches")
            return matches
            
        except Exception as e:
            self.logger.error(f"Error parsing HTML content: {e}")
            return []
    
    def export_matches_to_csv(self, matches, soccerway_spieltag):
        """
        Export matches to a CSV file named by the Soccerway Spieltag.
        """
        csv_path = f'footystats_3liga-fixtures_spieltag-{soccerway_spieltag}.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['spieltag', 'home_team', 'away_team', 'score_home', 'score_away', 'url']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for match in matches:
                writer.writerow(match)
        print(f"Matches exported to {csv_path}")
        return csv_path
    
    def scrape_fixtures(self, target_spieltag: int) -> List[Dict[str, Any]]:
        """Scrape fixtures using in-memory HTML processing"""
        self.logger.info(f"🏈 Scraping FootyStats fixtures for Spieltag {target_spieltag}")

        # Check if spieltag date is in the future
        spieltag_map = getattr(config, 'SPIELTAG_MAP', {})
        if target_spieltag in spieltag_map:
            date_str = spieltag_map[target_spieltag][1]
            match_datetime = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            if match_datetime > now:
                self.logger.info(f"⏩ Skipping Spieltag {target_spieltag}: date {date_str} is in the future.")
                return []
        
        # Convert Soccerway spieltag to Footystats spieltag
        footystats_spieltag = self.soccerway_to_footystats_spieltag(target_spieltag)
        
        # Get HTML content in memory instead of saving to file
        html_content = self.get_selenium_html_content(self.fixtures_url)
        
        if not html_content:
            self.logger.error("❌ Failed to retrieve HTML content")
            return []
        
        # Parse matches from HTML content (modified to accept string)
        matches = self.parse_matches_from_html_content(html_content, footystats_spieltag, target_spieltag)
        
        # Convert matches to the expected fixture format
        fixtures = []
        for match in matches:
            fixtures.append({
                'home_team': match['home_team'],
                'away_team': match['away_team'],
                'home_goals': match['score_home'],
                'away_goals': match['score_away'],
                'match_date': '',  # You can extract this if needed
                'match_time': '',  # You can extract this if needed
                'stats_link': match['url']  # Use stats_link instead of url for consistency
            })
            
            # Log each fixture as it's processed
            self.logger.info(f"Saving fixture idx={len(fixtures)-1}: home='{match['home_team']}', away='{match['away_team']}', url='{match['url']}'")
        
        if fixtures:
            self.logger.info(f"✅ Successfully parsed {len(fixtures)} matches")
        else:
            self.logger.warning(f"⚠️ No fixtures found for Spieltag {target_spieltag}")
            
        return fixtures
    
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
            
            # Reset DOM-extracted data
            self.dom_extracted_team_names = None
            self.dom_extracted_xg_values = None
            
            # Extract xG values (this will also extract team names from DOM)
            xg_values = self._find_xg_values(driver)
            
            # Check if we got team names from DOM (preferred method)
            if (hasattr(self, 'dom_extracted_team_names') and 
                self.dom_extracted_team_names and 
                len(self.dom_extracted_team_names) == 2 and
                len(xg_values) >= 2):
                
                team_names = self.dom_extracted_team_names
                self.logger.info(f"✅ Using DOM-extracted team names: {team_names}")
                
                result = {
                    'team_1_name': team_names[0],
                    'team_1_xG': xg_values[0],
                    'team_2_name': team_names[1],  
                    'team_2_xG': xg_values[1]
                }
                self.logger.info(f"✅ xG extracted from DOM with perfect alignment: {result}")
                return result
            
            # Fallback to URL/page extraction if DOM extraction didn't work
            self.logger.warning("⚠️ DOM team name extraction failed, falling back to URL/page extraction")
            team_names = self._extract_team_names_from_url(url)
            if not team_names:
                team_names = self._extract_team_names_from_page(driver)
            
            if len(xg_values) == 2 and team_names and len(team_names) == 2:
                result = {
                    'team_1_name': team_names[0],
                    'team_1_xG': xg_values[0],
                    'team_2_name': team_names[1],
                    'team_2_xG': xg_values[1]
                }
                self.logger.info(f"✅ xG extracted (fallback method): {result}")
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
                self.logger.debug(f"Trying strategy: {strategy.__name__}")  
                values = strategy(driver)  
                self.logger.debug(f"Strategy {strategy.__name__} found values: {values}")  
                if len(values) >= 2:  
                    self.logger.info(f"Strategy {strategy.__name__} succeeded with values: {values}")  
                    return values[:2]  
                else:  
                    self.logger.debug(f"Strategy {strategy.__name__} returned insufficient values: {values}")  
            except Exception as e:  
                self.logger.debug(f"Strategy {strategy.__name__} failed: {e}")  
                continue  
    
        self.logger.warning("No strategy succeeded in extracting xG values.")  
        return []
    
    def _strategy_table_xg(self, driver) -> List[str]:
        """Strategy 1: Table-based xG extraction"""
        self.logger.debug("Executing _strategy_table_xg")
        xg_elements = driver.find_elements(By.XPATH, 
            "//tr[td[contains(translate(text(), 'XG', 'xg'), 'xg')]]/td[@class='item stat average']")
        xg_values = [x.text.strip() for x in xg_elements if x.text.strip() and re.match(r'^\d+(\.\d+)?$', x.text.strip())]

        self.logger.debug(f"_strategy_table_xg found xG values: {xg_values}")  

        return xg_values

    def _strategy_xpath_xg(self, driver) -> List[str]:
        """Strategy 2: XPath-based xG extraction with team name context from DOM"""
        self.logger.debug("Executing _strategy_xpath_xg")
        xg_containers = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'XG', 'xg'), 'xg')]")
        
        for container in xg_containers:  
            try:  
                # Look for table structure first - this is most reliable
                table_row = container.find_element(By.XPATH, "./ancestor-or-self::tr")
                table = table_row.find_element(By.XPATH, "./ancestor::table")
                
                # Extract team names from table headers
                team_headers = table.find_elements(By.XPATH, ".//thead//th[position()>1]")  # Skip first column (Stats)
                team_names = []
                
                for header in team_headers:
                    # Look for team name links within headers
                    team_links = header.find_elements(By.TAG_NAME, "a")
                    if team_links:
                        team_text = team_links[0].text.strip()
                        normalized_name = config.normalize_team_name(team_text)
                        if normalized_name:
                            team_names.append(normalized_name)
                            self.logger.debug(f"Found team in table header: '{team_text}' -> '{normalized_name}'")
                
                # Extract xG values from the current row
                xg_cells = table_row.find_elements(By.XPATH, ".//td[position()>1]")  # Skip first column (Stats)
                xg_values = []
                
                for cell in xg_cells:
                    cell_text = cell.text.strip()
                    if re.match(r'^\d+(\.\d+)?$', cell_text):
                        xg_values.append(cell_text)
                        self.logger.debug(f"Found xG value in table cell: {cell_text}")
                
                # Check if we have a perfect match
                if len(team_names) >= 2 and len(xg_values) >= 2:
                    self.logger.info(f"Perfect table match found! {team_names[0]}={xg_values[0]}, {team_names[1]}={xg_values[1]}")
                    
                    # Store the team names from DOM for use in scrape_match_xg
                    self.dom_extracted_team_names = team_names[:2]
                    self.dom_extracted_xg_values = xg_values[:2]
                    
                    # Return xG values in team order
                    return xg_values[:2]
                    
            except Exception as e:
                self.logger.debug(f"Table extraction failed, trying fallback: {e}")
                
                # Fallback to original sibling-based approach
                try:
                    parent = container.find_element(By.XPATH, "./..")  
                    siblings = parent.find_elements(By.XPATH, "./*")  

                    # More focused debugging for fallback
                    container_texts = [s.text.strip() for s in siblings if s.text.strip()]
                    if any(re.match(r'^\d+(\.\d+)?$', text) for text in container_texts):
                        self.logger.debug(f"xG container (fallback) found with texts: {container_texts[:5]}...")  # Limit output

                    # Extract numeric values only for fallback
                    numeric_values = []
                    for sibling in siblings:  
                        text = sibling.text.strip()
                        if re.match(r'^\d+(\.\d+)?$', text):  
                            numeric_values.append(text)
                            self.logger.debug(f"Found xG value (fallback): {text}")

                    if len(numeric_values) >= 2:
                        self.logger.debug(f"Fallback found xG values: {numeric_values[:2]}")
                        return numeric_values[:2]
                        
                except Exception as fallback_e:
                    self.logger.debug(f"Fallback also failed: {fallback_e}")
                    continue
        
        # If no xG values found at all
        self.logger.debug("No xG values found in any containers")
        return []
    
    def _strategy_css_xg(self, driver) -> List[str]:
        """Strategy 3: CSS selector-based xG extraction"""
        self.logger.debug("Executing _strategy_css_xg")
  
        xg_values = []

        xg_selectors = [
            '[class*="xg"] .value', '[class*="xG"] .value',
            '.stat-xg', '.xg-value', '.expected-goals',
            '[data-stat="xg"]', '[data-value*="xg"]'
        ]
        
        for selector in xg_selectors:  
            try:  
                self.logger.debug(f"Trying CSS selector: {selector}")  
                elements = driver.find_elements(By.CSS_SELECTOR, selector)  
                values = [elem.text.strip() for elem in elements  
                        if elem.text.strip() and re.match(r'^\d+(\.\d+)?$', elem.text.strip())]  
                if values:  
                    self.logger.debug(f"Found xG values with selector '{selector}': {values}")  
                    xg_values.extend(values)  
            except Exception as e:  
                self.logger.debug(f"Error using selector '{selector}': {e}")  
        
        # Ensure we return only the first two values if more than two are found  
        if len(xg_values) >= 2:  
            self.logger.info(f"_strategy_css_xg succeeded with xG values: {xg_values[:2]}")  
            return xg_values[:2]  
        else:  
            self.logger.debug(f"_strategy_css_xg found insufficient xG values: {xg_values}")  
    
        return []