"""
Centralized logging configuration for 3. Liga Table of Justice
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import config

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green  
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Add color to levelname
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        
        return super().format(record)

def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    console_level: str = None,
    file_level: str = None
) -> logging.Logger:
    """
    Set up a logger with both console and file handlers
    
    Args:
        name: Logger name (usually __name__)
        log_file: Optional specific log file name
        console_level: Console logging level (defaults to config.LOG_LEVEL)
        file_level: File logging level (defaults to DEBUG)
    
    Returns:
        Configured logger instance
    """
    
    # Ensure logs directory exists
    config.ensure_directories()
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Set levels
    console_level = console_level or config.LOG_LEVEL
    file_level = file_level or 'DEBUG'
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level))
    
    console_format = ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = f"3liga_table_of_justice_{timestamp}.log"
    
    file_path = config.LOGS_DIR / log_file
    file_handler = logging.FileHandler(file_path, encoding='utf-8')
    file_handler.setLevel(getattr(logging, file_level))
    
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-15s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """Get or create a logger for the given name"""
    return setup_logger(name)

# Create main application logger
main_logger = get_logger('3liga-table-of-justice')