"""Structured JSON logging for production observability."""
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional, Dict
from pathlib import Path


class StructuredLogger:
    """Production-grade JSON logger with structured fields."""
    
    def __init__(self, name: str, log_file: Optional[Path] = None):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # JSON formatter
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)
        
        # File handler if specified
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(JSONFormatter())
            self.logger.addHandler(file_handler)

    def log(self, 
            level: str,
            message: str,
            **fields: Any) -> None:
        """Log with structured fields."""
        log_func = getattr(self.logger, level.lower(), self.logger.info)
        
        # Inject logger name
        fields['logger'] = self.name
        fields['message'] = message
        
        # Convert to extra dict for logging
        log_func(json.dumps(fields), extra=fields)

    def info(self, message: str, **fields) -> None:
        """Log info level."""
        self.log('INFO', message, **fields)

    def warning(self, message: str, **fields) -> None:
        """Log warning level."""
        self.log('WARNING', message, **fields)

    def error(self, message: str, **fields) -> None:
        """Log error level."""
        self.log('ERROR', message, **fields)

    def debug(self, message: str, **fields) -> None:
        """Log debug level."""
        self.log('DEBUG', message, **fields)

    def event(self,
             event_type: str,
             event_name: str,
             duration_ms: Optional[float] = None,
             success: bool = True,
             **fields) -> None:
        """Log structured event."""
        self.log('INFO', f"event:{event_type}:{event_name}", 
                event_type=event_type,
                event_name=event_name,
                success=success,
                duration_ms=duration_ms,
                **fields)


class JSONFormatter(logging.Formatter):
    """JSON logging formatter for structured output."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ('name', 'msg', 'args', 'created', 'filename', 
                              'funcName', 'levelname', 'levelno', 'lineno', 
                              'module', 'msecs', 'message', 'pathname', 'process',
                              'processName', 'relativeCreated', 'thread', 
                              'threadName', 'getMessage'):
                    if not key.startswith('_'):
                        log_data[key] = value
        
        return json.dumps(log_data, default=str)


# Global structured loggers
def get_logger(name: str, log_file: Optional[Path] = None) -> StructuredLogger:
    """Get structured logger instance."""
    return StructuredLogger(name, log_file)


# Create app logger
app_logger = get_logger('traceys-sentinel', Path('logs/app.json'))
audit_logger = get_logger('audit', Path('logs/audit.json'))
api_logger = get_logger('api', Path('logs/api.json'))
