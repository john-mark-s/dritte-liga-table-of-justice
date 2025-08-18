"""
Base scraper class with improved error handling and rate limiting
"""

import time
import random
import requests
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

from .config import config
from .logger import get_logger

class BaseScraper(ABC):
    """Base class for all scrapers with common functionality"""
    
    def __init__(self, source_name: str, delay_range: tuple = None):
        self.source_name = source_name
        self.delay_range = delay_range or (config.SCRAPING_DELAY_MIN, config.SCRAPING_DELAY_MAX)
        self.max_retries = config.SCRAPING_MAX_RETRIES
        self.timeout = config.SCRAPING_TIMEOUT
        
        self.session = requests.Session()
        self.logger = get_logger(f'scraper.{source_name}')
        
        # User agents for rotation
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0'
        ]
    
    def _get_headers(self) -> Dict[str, str]:
        """Get randomized headers for requests"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
    
    def _wait(self, attempt: int = 0):
        """Smart delay with exponential backoff"""
        if attempt == 0:
            # Normal delay
            delay = random.uniform(*self.delay_range)
        else:
            # Exponential backoff for retries
            base_delay = max(self.delay_range)
            delay = min(base_delay * (2 ** attempt), 300)  # Cap at 5 minutes
        
        self.logger.debug(f"Waiting {delay:.1f} seconds...")
        time.sleep(delay)
    
    def make_request(self, url: str, **kwargs) -> Optional[requests.Response]:
        """
        Make HTTP request with retries and error handling
        
        Args:
            url: URL to request
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object or None if failed
        """
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    self._wait(attempt)
                else:
                    self._wait()
                
                headers = self._get_headers()
                self.logger.info(f"Request attempt {attempt + 1}/{self.max_retries}: {url}")
                
                response = self.session.get(
                    url, 
                    headers=headers, 
                    timeout=self.timeout,
                    **kwargs
                )
                
                if response.status_code == 200:
                    self.logger.debug("✅ Request successful")
                    return response
                elif response.status_code == 429:
                    self.logger.warning("⚠️ Rate limited (429)")
                    time.sleep(60 * (attempt + 1))
                elif response.status_code == 403:
                    self.logger.warning("⚠️ Forbidden (403)")
                    time.sleep(120 * (attempt + 1))
                elif response.status_code == 404:
                    self.logger.error("❌ Not found (404)")
                    return None
                else:
                    self.logger.warning(f"⚠️ HTTP {response.status_code}")
                    
            except requests.exceptions.Timeout:
                self.logger.warning(f"⏰ Request timeout (attempt {attempt + 1})")
            except requests.exceptions.ConnectionError:
                self.logger.warning(f"🔌 Connection error (attempt {attempt + 1})")
            except Exception as e:
                self.logger.error(f"❌ Unexpected error: {e}")
                
            if attempt < self.max_retries - 1:
                wait_time = 30 * (attempt + 1)
                self.logger.info(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        self.logger.error(f"❌ Failed to fetch {url} after {self.max_retries} attempts")
        return None
    
    def normalize_team_names(self, fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize team names in fixture data"""
        for fixture in fixtures:
            for team_field in ['home_team', 'away_team']:
                if team_field in fixture:
                    original_name = fixture[team_field]
                    normalized_name = config.normalize_team_name(original_name)
                    if normalized_name != original_name:
                        self.logger.debug(f"Normalized '{original_name}' -> '{normalized_name}'")
                        fixture[team_field] = normalized_name
        return fixtures
    
    @abstractmethod
    def scrape_fixtures(self, target_spieltag: int) -> List[Dict[str, Any]]:
        """Scrape fixtures for a specific spieltag - must be implemented by subclasses"""
        pass
    
    def save_fixtures_to_csv(self, fixtures: List[Dict[str, Any]], spieltag: int) -> Optional[str]:
        """Save fixtures to CSV file"""
        if not fixtures:
            self.logger.warning(f"No fixtures to save for Spieltag {spieltag}")
            return None
        
        # Ensure directory exists
        output_dir = getattr(config, f"{self.source_name.upper()}_DIR")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get filename
        filename = config.get_output_filename(
            'fixtures', 
            source=self.source_name, 
            spieltag=spieltag
        )
        filepath = output_dir / filename
        
        try:
            import pandas as pd
            df = pd.DataFrame(fixtures)
            df.to_csv(filepath, index=False, encoding='utf-8')
            
            self.logger.info(f"✅ Saved {len(fixtures)} fixtures to {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"❌ Error saving fixtures: {e}")
            return None