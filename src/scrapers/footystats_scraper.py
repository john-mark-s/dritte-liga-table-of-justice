"""
FootyStats fixtures
"""

import os
import re
import csv
import json
import time
import random
import chromedriver_autoinstaller
from pathlib import Path  
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

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
    
    def get_selenium_html(self, url):
        """Get HTML content using Selenium with error handling"""
        driver = None
        try:
            chromedriver_autoinstaller.install()
            user_agent = random.choice(USER_AGENTS)
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument(f'user-agent={user_agent}')

            # Mask referer and other headers via Chrome arguments
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
                'headers': {
                    'Referer': 'https://www.google.com/',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'DNT': '1'
                }
            })
            
            self.logger.info(f"Loading URL: {url}")
            driver.get(url)
            time.sleep(3)  # Wait for page to load
            
            # Save HTML
            html_path = 'data/footystats/footystats_fixtures.html'
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            self.logger.info(f"Selenium HTML saved to {html_path}")

            return html_path
            
        except Exception as e:
            self.logger.error(f"Error getting HTML with Selenium: {e}")
            raise
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    self.logger.warning(f"Error closing driver: {e}")
    
    def parse_matches_from_html(self, html_path, footystats_spieltag, soccerway_spieltag):
        """
        Parse matches for a given Footystats Spieltag from the HTML file.
        Returns a list of match dicts with error handling.
        """
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html = f.read()
        except Exception as e:
            self.logger.error(f"Error reading HTML file {html_path}: {e}")
            return []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
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
            self.logger.error(f"Error parsing HTML: {e}")
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
    
        csv_path = Path(f'data/footystats/footystats_3liga-fixtures_spieltag-{target_spieltag}.csv')
        
        # Check if the CSV already exists  
        if csv_path.exists():  
            self.logger.info(f"⏩ Skipping Spieltag {target_spieltag}: CSV already exists at {csv_path}")  
            return []  
    
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
        
        # Get HTML using Selenium
        html_path = self.get_selenium_html(self.fixtures_url)
        
        # Parse matches from HTML
        matches = self.parse_matches_from_html(html_path, footystats_spieltag, target_spieltag)
        
        # Convert matches to the expected format for return value
        fixtures = []
        for match in matches:
            fixtures.append({
                'home_team': match['home_team'],
                'away_team': match['away_team'],
                'home_goals': match['score_home'],  # Map to expected field name
                'away_goals': match['score_away'],  # Map to expected field name
                'match_date': '',  # You'll need to extract this from the HTML
                'match_time': '',  # You'll need to extract this from the HTML
                'url': match['url']
            })
            
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