"""
Soccerway fixtures and xG scraper with improved error handling
"""

import re
import csv
import time
import random
import chromedriver_autoinstaller
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

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

            # self._load_previous_matches(driver)
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
            self.logger.debug("Attempting to open game week dropdown")  
            dropdown_button = WebDriverWait(driver, 10).until(  
                EC.element_to_be_clickable((By.ID, "unique_flyout_transfer_custom_week_button"))  
            )  
            dropdown_button.click()  
            self.logger.info("✅ Opened Game week dropdown")
            driver.save_screenshot('data/soccerway/opened_game_week_dropdown.png')  
            
            self.logger.debug(f"Attempting to select Game week {target_spieltag}")  
            option_xpath = f"//div[@id='dropdown_picker_unique_flyout_transfer_custom_week_button']//div[span//span[contains(text(), 'Game week {target_spieltag}')]]"  
            option = WebDriverWait(driver, 10).until(  
                EC.element_to_be_clickable((By.XPATH, option_xpath))  
            )  
            option.click()  
            self.logger.info(f"✅ Selected Game week {target_spieltag}")
            driver.save_screenshot(f'data/soccerway/selected_game_week{target_spieltag}.png')
            
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
            consent_button = WebDriverWait(driver, 15).until(
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
    
    def _extract_fixtures(self, driver, target_spieltag: int) -> List[Dict[str, Any]]:  
        """Extract fixtures from the page"""  
        fixtures = []  
        
        try:  
            # Save the entire page source to a file for debugging  
            page_source = driver.page_source

            html_path = f"data/soccerway/soccerway_spieltag_{target_spieltag}_page.html"
            with open(html_path, "w", encoding="utf-8") as file:  
                file.write(page_source)  
            self.logger.info(f"Page source saved to soccerway_spieltag_{target_spieltag}_page.html")  
    
            html_content = page_source
            print(f"Soccerway Spieltag {target_spieltag} stored")

            soup = BeautifulSoup(html_content, 'html.parser')
            fixtures = []
            
            # Find all fixture containers
            fixture_containers = soup.find_all('div', class_='sc-f6b773a5-3')
            
            for container in fixture_containers:
                try:
                    fixture_data = {}
                    
                    fixture_data['spieltag'] = target_spieltag
                    
                    # Extract team names
                    team_container = container.find('span', class_='sc-1718759c-5 hCWYeZ')

                    if team_container:
                        team_spans = team_container.find_all('span', class_='sc-1718759c-0 hCWqQ')
                        if len(team_spans) >= 2:
                            # First team is home, second is away
                            home_team_elem = team_spans[0].find('span', class_=re.compile(r'sc-1718759c-3'))
                            away_team_elem = team_spans[1].find('span', class_=re.compile(r'sc-1718759c-3'))
                            
                            if home_team_elem and away_team_elem:
                                fixture_data['home_team'] = home_team_elem.get_text(strip=True)
                                fixture_data['away_team'] = away_team_elem.get_text(strip=True)
                            else:
                                continue  # Skip if team names not found
                        else:
                            continue  # Skip if not enough team containers
                    else:
                        continue  # Skip if no team container found
                    
                    # Extract scores
                    score_container = container.find('span', class_='sc-cc2791f0-1 fflVkg')
                    if score_container:
                        score_divs = score_container.find_all('div', class_='sc-cc2791f0-0 hyvmlQ default')
                        if len(score_divs) >= 2:
                            # First score is home, second is away
                            home_score_elem = score_divs[0].find('span', class_='sc-4e4c9eab-2 jnsOHd label score')
                            away_score_elem = score_divs[1].find('span', class_='sc-4e4c9eab-2 jnsOHd label score')
                            
                            if home_score_elem and away_score_elem:
                                try:
                                    fixture_data['home_goals'] = int(home_score_elem.get_text(strip=True))
                                    fixture_data['away_goals'] = int(away_score_elem.get_text(strip=True))
                                except ValueError:
                                    # If scores can't be converted to int, set as None (match not played yet)
                                    fixture_data['home_goals'] = None
                                    fixture_data['away_goals'] = None
                            else:
                                fixture_data['home_goals'] = None
                                fixture_data['away_goals'] = None
                        else:
                            fixture_data['home_goals'] = None
                            fixture_data['away_goals'] = None
                    else:
                        fixture_data['home_goals'] = None
                        fixture_data['away_goals'] = None 
                    
                    # Extract URL
                    url_link = container.find('a', class_='sc-22ef6ec-0 sc-f6b773a5-2 boVFdS ZfONG')

                    if url_link and url_link.get('href'):
                        fixture_data['url'] = url_link['href']
                        fixture_data['url'] = self.base_url + fixture_data['url']
                        print(f"Fixture URL found: {fixture_data['url']}")
                    else:
                        continue  # Skip if no URL found
                    
                    fixtures.append(fixture_data)
                    
                except Exception as e:
                    # Skip problematic fixtures and continue
                    print(f"Error processing fixture: {e}")
                    continue

            return fixtures

        except Exception as e:  
            self.logger.error(f"❌ Error extracting fixtures: {e}")  
            return []
    
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
            driver.save_screenshot('data/soccerway/clicked_consent_button.png')  
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