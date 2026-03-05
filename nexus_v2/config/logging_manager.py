"""
NEXUS Logging Manager
Centralized logging system with configurable output
"""

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
try:
    from config.config_manager import config
except ImportError:
    config = None

class NexusLogger:
    """Enhanced logging manager for NEXUS application"""
    
    def __init__(self, name="nexus"):
        self.logger = logging.getLogger(name)
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging configuration"""
        # Get configuration
        if config:
            log_config = config.get_logging_config()
            log_level = log_config.get('level', 'INFO')
            log_file = log_config.get('file_path', './logs/nexus.log')
            max_size_mb = log_config.get('max_file_size_mb', 10)
            backup_count = log_config.get('backup_count', 5)
            console_logging = log_config.get('console_logging', True)
        else:
            # Defaults if no config
            log_level = 'INFO'
            log_file = './logs/nexus.log'
            max_size_mb = 10
            backup_count = 5
            console_logging = True
        
        # Set logging level
        level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger.setLevel(level)
        
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler with rotation
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_size_mb * 1024 * 1024,  # Convert MB to bytes
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")
        
        # Console handler
        if console_logging:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # Log startup message
        self.logger.info("NEXUS Logging System Initialized")
    
    def get_logger(self):
        """Get the configured logger instance"""
        return self.logger
    
    def info(self, message):
        """Log info message"""
        self.logger.info(message)
    
    def debug(self, message):
        """Log debug message"""
        self.logger.debug(message)
    
    def warning(self, message):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message, exc_info=False):
        """Log error message"""
        self.logger.error(message, exc_info=exc_info)
    
    def critical(self, message):
        """Log critical message"""
        self.logger.critical(message)
    
    def log_function_call(self, func_name, *args, **kwargs):
        """Log function calls for debugging"""
        args_str = ", ".join([str(arg) for arg in args])
        kwargs_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        params = ", ".join(filter(None, [args_str, kwargs_str]))
        self.debug(f"Calling {func_name}({params})")
    
    def log_performance(self, operation, duration_seconds):
        """Log performance metrics"""
        self.info(f"PERFORMANCE: {operation} completed in {duration_seconds:.3f}s")
    
    def log_scanner_event(self, event_type, details=None):
        """Log scanner-specific events"""
        msg = f"SCANNER: {event_type}"
        if details:
            msg += f" - {details}"
        self.info(msg)
    
    def log_ai_event(self, event_type, details=None):
        """Log AI/ML specific events"""
        msg = f"AI: {event_type}"
        if details:
            msg += f" - {details}"
        self.info(msg)
    
    def log_database_event(self, operation, table=None, records=None):
        """Log database operations"""
        msg = f"DATABASE: {operation}"
        if table:
            msg += f" on {table}"
        if records:
            msg += f" ({records} records)"
        self.info(msg)

# Global logger instance
nexus_logger = NexusLogger()

# Convenience functions for easy importing
def get_logger():
    return nexus_logger.get_logger()

def log_info(message):
    nexus_logger.info(message)

def log_debug(message):
    nexus_logger.debug(message)

def log_warning(message):
    nexus_logger.warning(message)

def log_error(message, exc_info=False):
    nexus_logger.error(message, exc_info=exc_info)

def log_critical(message):
    nexus_logger.critical(message)

def log_scanner_event(event_type, details=None):
    nexus_logger.log_scanner_event(event_type, details)

def log_ai_event(event_type, details=None):
    nexus_logger.log_ai_event(event_type, details)

def log_database_event(operation, table=None, records=None):
    nexus_logger.log_database_event(operation, table, records)