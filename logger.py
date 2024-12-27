import logging
import os
from typing import Optional
from logging import Logger, FileHandler, StreamHandler, Formatter

class LogConfig:
    """Configuration constants for logging"""
    DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    CONSOLE_FORMAT = '%(levelname)s: %(message)s'
    LOG_DIR = 'logs'
    LOG_FILE = 'wake.log'
    FILE_LEVEL = logging.DEBUG
    CONSOLE_LEVEL = logging.INFO

def create_log_directory(log_dir: str = LogConfig.LOG_DIR) -> None:
    """
    Create logging directory if it doesn't exist
    
    Args:
        log_dir: Directory path for log files
        
    Raises:
        OSError: If directory creation fails
    """
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception as e:
        raise OSError(f"Failed to create log directory: {e}")

def create_file_handler(
    log_file: str = LogConfig.LOG_FILE,
    log_dir: str = LogConfig.LOG_DIR,
    level: int = LogConfig.FILE_LEVEL,
    format_str: str = LogConfig.DEFAULT_FORMAT
) -> FileHandler:
    """
    Create and configure a file handler for logging
    
    Args:
        log_file: Name of the log file
        log_dir: Directory path for log files
        level: Logging level for file handler
        format_str: Format string for log messages
        
    Returns:
        FileHandler: Configured file handler
    """
    file_handler = FileHandler(os.path.join(log_dir, log_file))
    file_handler.setLevel(level)
    file_formatter = Formatter(format_str)
    file_handler.setFormatter(file_formatter)
    return file_handler

def create_console_handler(
    level: int = LogConfig.CONSOLE_LEVEL,
    format_str: str = LogConfig.CONSOLE_FORMAT
) -> StreamHandler:
    """
    Create and configure a console handler for logging
    
    Args:
        level: Logging level for console handler
        format_str: Format string for console messages
        
    Returns:
        StreamHandler: Configured console handler
    """
    console_handler = StreamHandler()
    console_handler.setLevel(level)
    console_formatter = Formatter(format_str)
    console_handler.setFormatter(console_formatter)
    return console_handler

def setup_logger(
    name: str,
    log_dir: str = LogConfig.LOG_DIR,
    log_file: str = LogConfig.LOG_FILE,
    file_level: int = LogConfig.FILE_LEVEL,
    console_level: int = LogConfig.CONSOLE_LEVEL,
    file_format: str = LogConfig.DEFAULT_FORMAT,
    console_format: str = LogConfig.CONSOLE_FORMAT
) -> Logger:
    """
    Configure and return a logger instance with both file and console handlers
    
    Args:
        name: Logger name (typically __name__)
        log_dir: Directory path for log files
        log_file: Name of the log file
        file_level: Logging level for file handler
        console_level: Logging level for console handler
        file_format: Format string for file logs
        console_format: Format string for console logs
        
    Returns:
        Logger: Configured logger instance
        
    Example:
        >>> logger = setup_logger(__name__)
        >>> logger.info("Application started")
        >>> logger.debug("Debug information")
    """
    # Get or create logger
    logger = logging.getLogger(name)
    logger.setLevel(min(file_level, console_level))  # Set to lowest level
    logger.propagate = False  # Prevent propagation to root logger

    # Only add handlers if they haven't been added yet
    if not logger.handlers:
        try:
            # Create log directory
            create_log_directory(log_dir)

            # Add handlers
            logger.addHandler(create_file_handler(
                log_file, log_dir, file_level, file_format
            ))
            logger.addHandler(create_console_handler(
                console_level, console_format
            ))

        except Exception as e:
            # Fallback to basic configuration if setup fails
            logging.basicConfig(
                level=logging.INFO,
                format=LogConfig.CONSOLE_FORMAT
            )
            logger.error(f"Failed to setup logger: {e}")
            logger.warning("Falling back to basic logging configuration")

    return logger
