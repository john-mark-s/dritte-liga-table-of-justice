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
            List of fixture dictionaries
        """
        self.logger.info(f"⚽ Scraping Soccerway fixtures for Spieltag {target_spieltag}")
        
        driver = self._create_driver()
        if not driver:
            return []
        
        try:
            # Navigate to fixtures page
            self.logger.debug(f"Loading: {self.fixtures_url}")
            driver.get(self.fixtures_url)
            time.sleep(3)
            
            # Handle consent popup
            self._handle_consent_popup(driver)
            
            # Click load previous button if needed
            self._load_previous_matches(driver)
            
            # Scrape fixtures
            fixtures = self._extract_fixtures(driver, target_spieltag)
            
            # Normalize team names
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
        current_gameweek = None
        
        try:
            items = driver.find_elements(By.CSS_SELECTOR, "div[data-known-size]")
            self.logger.debug(f"Found {len(items)} page items")
            
            for item in items:
                text = item.text.strip()
                
                # Check if this is a gameweek header
                if text.startswith("Game week"):
                    current_gameweek = text
                    continue
                
                # Extract match URL
                try:
                    link_elem = item.find_element(By.TAG_NAME, "a")
                    match_url = link_elem.get_attribute("href")
                except:
                    match_url = None
                
                # Process match if URL exists and gameweek matches
                if match_url and current_gameweek:
                    try:
                        gw_number = int(current_gameweek.split()[-1])
                    except:
                        gw_number = None
                    
                    if gw_number == target_spieltag:
                        fixture = self._parse_fixture_text(text, current_gameweek, match_url)
                        if fixture:
                            fixtures.append(fixture)
            
            return fixtures
            
        except Exception as e:
            self.logger.error(f"❌ Error extracting fixtures: {e}")
            return []
    
    def _parse_fixture_text(self, text: str, gameweek: str, url: str) -> Optional[Dict[str, Any]]:
        """Parse fixture text into structured data - handles the new line-separated format"""
        try:
            # The new format appears to be line-separated:
            # Team1
            # Score1
            # Team2  
            # Score2
            # Index (sometimes)
            # Bet1
            # Bet2
            # Bet3
            
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            if len(lines) < 7:  # Need at least: team1, score1, team2, score2, bet1, bet2, bet3
                self.logger.warning(f"⚠️ Unexpected fixture format: {text}")
                return None

            # Try to identify the pattern
            # Look for two consecutive numeric values (scores)
            score_indices = []
            for i, line in enumerate(lines):
                if line.isdigit():
                    score_indices.append(i)

            if len(score_indices) < 2:
                self.logger.warning(f"⚠️ Could not find two scores in: {text}")
                return None

            # Assume first two numeric values are scores
            score1_idx = score_indices[0]
            score2_idx = score_indices[1]

            # Team names should be before scores
            if score1_idx == 0 or score2_idx <= score1_idx:
                self.logger.warning(f"⚠️ Invalid score positions in: {text}")
                return None

            team1 = lines[score1_idx - 1]
            score1 = lines[score1_idx]
            team2 = lines[score2_idx - 1] 
            score2 = lines[score2_idx]

            # Find betting odds (should be 3 decimal numbers after scores)
            bet_lines = []
            for i in range(score2_idx + 1, len(lines)):
                line = lines[i]
                try:
                    float(line)
                    bet_lines.append(line)
                    if len(bet_lines) == 3:
                        break
                except ValueError:
                    continue

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