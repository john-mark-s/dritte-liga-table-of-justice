"""
Soccerway fixtures and xG scraper with improved error handling
"""

import re
import time
import random
from typing import Dict, List, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import chromedriver_autoinstaller

from ..utils.scraper_base import BaseScraper
from ..utils.config import config
from ..utils.logger import get_logger

class SoccerwayFixturesScraper(BaseScraper):
    """Scraper for Soccerway fixtures"""
    
    def __init__(self):
        super().__init__('soccerway')
        self.base_url = config.SOURCES.get('soccerway', {}).get('base_url', 'https://int.soccerway.com')
        self.fixtures_url = config.SOURCES.get('soccerway', {}).get('fixtures_url')
    
    def scrape_fixtures(self, target_spieltag: int) -> List[Dict[str, Any]]:
        """
        Scrape fixtures for a specific spieltag using Selenium
        
        Args:
            target_spieltag: Spieltag number to scrape
        Returns:
            List of fixture dictionaries (with normalized team names)
        """
        self.logger.info(f"⚽ Scraping Soccerway fixtures for Spieltag {target_spieltag}")

        # Check if spieltag date is in the future
        spieltag_map = getattr(config, 'SPIELTAG_MAP', {})
        if target_spieltag in spieltag_map:
            date_str = spieltag_map[target_spieltag][1]
            from datetime import datetime
            match_datetime = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            if match_datetime > now:
                self.logger.info(f"⏩ Skipping Spieltag {target_spieltag}: date {date_str} is in the future.")
                return []

        driver = self._create_driver()
        if not driver:
            return []
        try:
            self.logger.debug(f"Loading: {self.fixtures_url}")
            driver.get(self.fixtures_url)
            time.sleep(3)
            self._handle_consent_popup(driver)

            # Select the correct Spielwoche from dropdown
            self._select_spielwoche(driver, target_spieltag)

            self._load_previous_matches(driver)
            fixtures = self._extract_fixtures(driver, target_spieltag)
            fixtures = self.normalize_team_names(fixtures)
            self.logger.info(f"✅ Scraped {len(fixtures)} fixtures for Spieltag {target_spieltag}")
            return fixtures
        except Exception as e:
            self.logger.error(f"❌ Error scraping Soccerway: {e}")
            return []
        finally:
            try:
                driver.quit()
            except:
                pass

    def _select_spielwoche(self, driver, target_spieltag: int) -> None:  
        """Select the correct Spielwoche/Game week/Spieltag from the picker."""  
        try:  
            # Open the dropdown  
            dropdown_button = WebDriverWait(driver, 10).until(  
                EC.element_to_be_clickable((By.ID, "unique_flyout_transfer_custom_week_button"))  
            )  
            dropdown_button.click()  
            self.logger.info("✅ Opened Game week dropdown")  
    
            # Select the target Game week  
            option_xpath = f"//div[@id='dropdown_picker_unique_flyout_transfer_custom_week_button']//div[span//span[contains(text(), 'Game week {target_spieltag}')]]"  
            option = WebDriverWait(driver, 10).until(  
                EC.element_to_be_clickable((By.XPATH, option_xpath))  
            )  
            option.click()  
            self.logger.info(f"✅ Selected Game week {target_spieltag}")  
            
            time.sleep(6)  # Wait for the page to update  
    
        except Exception as e:  
            self.logger.warning(f"⚠️ Error selecting Spielwoche: {e}")  
    
    def _create_driver(self) -> Optional[webdriver.Chrome]:
        """Create and configure Chrome driver"""
        try:
            chromedriver_autoinstaller.install()
            
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            return driver
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create Chrome driver: {e}")
            return None
    
    def _handle_consent_popup(self, driver) -> None:
        """Handle consent popup if present"""
        try:
            consent_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 
                    "button.fc-button.fc-cta-consent.fc-primary-button"))
            )
            consent_button.click()
            self.logger.debug("✅ Clicked consent button")
            time.sleep(2)
        except TimeoutException:
            self.logger.debug("ℹ️ No consent popup found")
        except Exception as e:
            self.logger.warning(f"⚠️ Error handling consent: {e}")
    
    def _load_previous_matches(self, driver) -> None:
        """Click load previous button if available"""
        try:
            button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 
                    "button.sc-41ba8c7a-0.dGqIGb.undefined"))
            )
            button.click()
            self.logger.debug("✅ Clicked load previous button")
            time.sleep(3)
        except TimeoutException:
            self.logger.debug("ℹ️ No load previous button found")
        except Exception as e:
            self.logger.warning(f"⚠️ Error clicking load previous: {e}")
    
    def _extract_fixtures(self, driver, target_spieltag: int) -> List[Dict[str, Any]]:
        """Extract fixtures from the page"""
        fixtures = []
        
        try:
            fixture_divs = driver.find_elements(By.CSS_SELECTOR, "div.sc-4e66d108-3")  
            for fixture in fixture_divs:
                
                try:
                    # Match URL
                    link = fixture.find_element(By.TAG_NAME, "a").get_attribute("href")  
                    
                    # Teams
                    team_spans = fixture.find_elements(By.XPATH, ".//span[contains(@class, 'label') and contains(@class, 'dDQFLa')]")  
                    team_names = [t.text.strip() for t in team_spans if t.text.strip()]  
                
                    if len(team_names) < 2:  
                        name_spans = fixture.find_elements(By.XPATH, ".//div[contains(@class, 'label')]//span[@class='name']")  
                        team_names = [n.text.strip() for n in name_spans if n.text.strip()]  

                    # Try to extract team names using multiple strategies
                    team_names = []
                    
                                    # 1. All <span> with class 'label' inside the fixture, but not 'score'
                    label_spans = fixture.find_elements(By.XPATH, ".//span[contains(@class, 'label') and not(contains(@class, 'score'))]")
                    for span in label_spans:
                        txt = span.text.strip()
                        # Filter out empty, odds, dates, and other non-team labels
                        if txt and re.match(r"^[A-Za-z0-9ÄÖÜäöüß \-\.]+$", txt) and len(txt) > 2:
                            team_names.append(txt)

                    # 2. If not found, look for <span class="name">
                    if len(team_names) < 2:
                        name_spans = fixture.find_elements(By.XPATH, ".//span[@class='name']")
                        for n in name_spans:
                            txt = n.text.strip()
                            if txt and len(txt) > 2:
                                team_names.append(txt)

                    # Remove duplicates
                    team_names = list(dict.fromkeys(team_names))
                    
                    
                    if len(team_names) < 2:  
                        continue  
  
                    home_team = team_names[0]  
                    away_team = team_names[1]
                    
                    score_spans = fixture.find_elements(By.XPATH, ".//span[contains(@class, 'label') and contains(@class, 'score') and string-length(normalize-space(text())) > 0]")  
                    score_texts = [s.text.strip() for s in score_spans if s.text.strip().isdigit()]  
    
                    score_home = score_texts[0] if len(score_texts) > 0 else None  
                    score_away = score_texts[1] if len(score_texts) > 1 else None  
    
                    fixtures.append({  
                        "spieltag": target_spieltag,  
                        "home": home_team,  
                        "away": away_team,  
                        "score_home": score_home,  
                        "score_away": score_away,  
                        "url": link  
                    })  
                    
                except Exception as e:  
                    self.logger.warning(f"⚠️ Skipped fixture: {e}")                    
            
        except Exception as e:
            self.logger.error(f"❌ Error extracting fixtures: {e}")
            
        return fixtures
    
    def _parse_fixture_text(self, text: str, gameweek: str, url: str) -> Optional[Dict[str, Any]]:
        """Parse fixture text into structured data - robust team/score extraction"""
        try:
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            self.logger.debug(f"Parsing fixture text lines: {lines}")

            # Separate team names (non-numeric) and scores (numeric)
            team_names = [line for line in lines if not line.isdigit()]
            scores = [line for line in lines if line.isdigit()]

            self.logger.debug(f"Extracted team names: {team_names}")
            self.logger.debug(f"Extracted scores: {scores}")

            if len(team_names) < 2 or len(scores) < 2:
                self.logger.warning(f"⚠️ Could not find two team names and two scores in: {text}")
                return None

            team1 = team_names[0]
            team2 = team_names[1]
            score1 = scores[0]
            score2 = scores[1]

            self.logger.debug(f"Parsed teams: team1='{team1}', team2='{team2}', scores: {score1}-{score2}")

            # Find betting odds (should be 3 decimal numbers after scores)
            bet_lines = []
            for line in lines:
                try:
                    val = float(line)
                    # Only add if not already in scores (to avoid adding scores as odds)
                    if line not in scores:
                        bet_lines.append(line)
                    if len(bet_lines) == 3:
                        break
                except ValueError:
                    continue

            self.logger.debug(f"Betting odds found: {bet_lines}")

            if len(bet_lines) < 3:
                self.logger.warning(f"⚠️ Could not find 3 betting odds in: {text}")
                return None

            return {
                "gameweek": gameweek,
                "home_team": team1,
                "away_team": team2,
                "home_goals": score1,
                "away_goals": score2,
                "bet1": bet_lines[0],
                "bet2": bet_lines[1],
                "bet3": bet_lines[2],
                "url": url
            }

        except Exception as e:
            self.logger.error(f"❌ Error parsing fixture text: {e}")
            return None


class SoccerwayXGScraper:
    """Scraper for xG data from Soccerway match pages"""
    
    NUMERIC_RE = re.compile(r'^\d+(?:[.,]\d+)?$')
    
    def __init__(self):
        self.logger = get_logger('soccerway.xg')
    
    def scrape_match_xg(self, url: str) -> Optional[Dict[str, str]]:
        """
        Scrape xG data from a Soccerway match page
        
        Args:
            url: Match URL
            
        Returns:
            Dictionary with xG values or None if failed
        """
        driver = self._create_driver()
        if not driver:
            return None
        
        try:
            self.logger.info(f"🎯 Scraping xG from: {url}")
            driver.get(url)
            
            # Handle consent
            self._handle_consent(driver)
            
            # Find xG values
            home_xg, away_xg = self._find_xg_values(driver, url)
            
            if home_xg and away_xg:
                result = {
                    'home_xG': home_xg,
                    'away_xG': away_xg
                }
                self.logger.info(f"✅ xG extracted: {result}")
                return result
            else:
                self.logger.warning("⚠️ Could not extract xG values")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error scraping xG: {e}")
            return None
        finally:
            try:
                driver.quit()
            except:
                pass
    
    def _create_driver(self) -> Optional[webdriver.Chrome]:
        """Create Chrome driver"""
        try:
            chromedriver_autoinstaller.install()
            
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            driver = webdriver.Chrome(options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.set_page_load_timeout(40)
            
            return driver
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create driver: {e}")
            return None
    
    def _handle_consent(self, driver, timeout: int = 6) -> None:
        """Handle consent popup"""
        try:
            WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 
                    "button.fc-button.fc-cta-consent.fc-primary-button"))
            )
            
            btn = driver.find_element(By.CSS_SELECTOR, 
                "button.fc-button.fc-cta-consent.fc-primary-button")
            btn.click()
            self.logger.debug("✅ Clicked consent button")
            time.sleep(0.8)
            
        except TimeoutException:
            self.logger.debug("ℹ️ No consent popup found")
        except Exception as e:
            self.logger.warning(f"⚠️ Consent error: {e}")
    
    def _find_xg_values(self, driver, url: str, wait_timeout: int = 12) -> tuple:
        """Find xG values on the page"""
        xpath_label = "//span[contains(text(),'Expected goals')]"
        
        try:
            # Wait for xG labels to appear
            WebDriverWait(driver, wait_timeout).until(
                lambda d: len(d.find_elements(By.XPATH, xpath_label)) >= 1
            )
        except TimeoutException:
            self.logger.warning("⚠️ Timeout waiting for 'Expected goals' labels")
            return None, None
        
        labels = driver.find_elements(By.XPATH, xpath_label)
        self.logger.debug(f"Found {len(labels)} xG labels")
        
        # Choose second occurrence when available, otherwise first
        chosen_idx = 1 if len(labels) >= 2 else 0
        
        # Try chosen label first, then fallback to others
        for idx in ([chosen_idx] + [i for i in range(len(labels)) if i != chosen_idx]):
            label = labels[idx]
            
            # Try different ancestor levels to find container with numbers
            for level in range(1, 7):
                try:
                    container = label.find_element(By.XPATH, f"./ancestor::div[{level}]")
                    numeric_values = self._extract_numeric_from_container(container)
                    
                    if len(numeric_values) >= 2:
                        # Split into home/away values
                        half = len(numeric_values) // 2
                        home_xg = numeric_values[0]
                        away_xg = numeric_values[half]
                        
                        return home_xg, away_xg
                        
                except:
                    continue
        
        return None, None
    
    def _extract_numeric_from_container(self, container) -> List[str]:
        """Extract numeric values from container element"""
        numeric_values = []
        
        try:
            descendants = container.find_elements(By.XPATH, ".//*")
            
            for elem in descendants:
                text = elem.text.strip()
                if text and self.NUMERIC_RE.match(text):
                    # Normalize comma to dot
                    normalized = text.replace(',', '.')
                    numeric_values.append(normalized)
                    
        except Exception as e:
            self.logger.debug(f"Error extracting numeric values: {e}")
        
        return numeric_values