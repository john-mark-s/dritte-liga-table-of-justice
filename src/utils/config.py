"""
Configuration management for 3. Liga Table of Justice
Handles environment variables, YAML config, and provides centralized settings
"""

import os
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Centralized configuration management"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or os.getenv('CONFIG_FILE', 'config/config.yaml')
        self._config_data = self._load_config()
        
    def _load_config(self) -> Dict:
        """Load configuration from YAML file"""
        config_path = Path(self.config_file)
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: Could not load config file {config_path}: {e}")
                return {}
        else:
            print(f"Warning: Config file {config_path} not found")
            return {}
    
    # Directory paths
    @property
    def BASE_DIR(self) -> Path:
        return Path(os.getenv('BASE_DIR', './data'))
    
    @property
    def LOGS_DIR(self) -> Path:
        return Path(os.getenv('LOGS_DIR', './logs'))
    
    @property
    def CONFIG_DIR(self) -> Path:
        return Path(os.getenv('CONFIG_DIR', './config'))
    
    @property
    def FOOTYSTATS_DIR(self) -> Path:
        return self.BASE_DIR / "footystats"
    
    @property
    def SOCCERWAY_DIR(self) -> Path:
        return self.BASE_DIR / "soccerway"
    
    # Scraping settings
    @property
    def SCRAPING_DELAY_MIN(self) -> int:
        return int(os.getenv('SCRAPING_DELAY_MIN', 2))
    
    @property
    def SCRAPING_DELAY_MAX(self) -> int:
        return int(os.getenv('SCRAPING_DELAY_MAX', 8))
    
    @property
    def SCRAPING_MAX_RETRIES(self) -> int:
        return int(os.getenv('SCRAPING_MAX_RETRIES', 3))
    
    @property
    def SCRAPING_TIMEOUT(self) -> int:
        return int(os.getenv('SCRAPING_TIMEOUT', 30))
    
    # Dashboard settings
    @property
    def DASHBOARD_HOST(self) -> str:
        return os.getenv('DASHBOARD_HOST', '127.0.0.1')
    
    @property
    def DASHBOARD_PORT(self) -> int:
        return int(os.getenv('DASHBOARD_PORT', 8050))
    
    @property
    def DASHBOARD_DEBUG(self) -> bool:
        return os.getenv('DASHBOARD_DEBUG', 'false').lower() == 'true'
    
    # Logging
    @property
    def LOG_LEVEL(self) -> str:
        return os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Data sources
    @property
    def ENABLED_SOURCES(self) -> List[str]:
        sources = os.getenv('ENABLED_SOURCES', 'footystats,soccerway')
        return [s.strip() for s in sources.split(',')]
    
    # Team mappings
    @property
    def TEAMS(self) -> Dict[str, List[str]]:
        return self._config_data.get('teams', {})
    
    # Spieltag mappings
    @property
    def SPIELTAG_MAP(self) -> Dict[int, Tuple[str, str]]:
        spieltag_data = self._config_data.get('spieltag_map', {})
        return {int(k): tuple(v) for k, v in spieltag_data.items()}
    
    # Data sources configuration
    @property
    def SOURCES(self) -> Dict[str, Dict]:
        return self._config_data.get('sources', {})
    
    # Output file patterns
    @property
    def OUTPUT_FILES(self) -> Dict[str, str]:
        return self._config_data.get('output_files', {})
    
    def get_output_filename(self, file_type: str, **kwargs) -> str:
        """Get formatted output filename"""
        pattern = self.OUTPUT_FILES.get(file_type, f"{file_type}.csv")
        return pattern.format(**kwargs)
    
    def ensure_directories(self):
        """Create necessary directories if they don't exist"""
        dirs = [
            self.BASE_DIR,
            self.LOGS_DIR,
            self.FOOTYSTATS_DIR,
            self.SOCCERWAY_DIR
        ]
        
        for directory in dirs:
            directory.mkdir(parents=True, exist_ok=True)
    
    def normalize_team_name(self, team_name: str) -> str:
        """Normalize team name using the team mappings"""
        for correct_name, aliases in self.TEAMS.items():
            if team_name in aliases or team_name == correct_name:
                return correct_name
        return team_name

# Global config instance
config = Config()