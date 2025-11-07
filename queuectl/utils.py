"""
Utility functions for QueueCTL

Common helpers and validation functions used across the system.
"""

import json
import re
import shlex
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from pathlib import Path


def generate_job_id() -> str:
    """
    Generate a unique job ID.
    
    Returns:
        Unique job identifier
    """
    return str(uuid.uuid4())


def validate_command(command: str) -> bool:
    """
    Validate a shell command for basic safety.
    
    Args:
        command: Command to validate
        
    Returns:
        True if command appears safe, False otherwise
    """
    if not command or not command.strip():
        return False
    
    # Basic safety checks - could be expanded
    dangerous_patterns = [
        r'rm\s+-rf\s+/',  # rm -rf /
        r':\(\)\{.*\}\;',  # Fork bomb pattern
        r'>\s*/dev/sd[a-z]',  # Direct disk write
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return False
    
    return True


def parse_command_safely(command: str) -> List[str]:
    """
    Parse command string into arguments safely.
    
    Args:
        command: Command string to parse
        
    Returns:
        List of command arguments
    """
    try:
        return shlex.split(command)
    except ValueError:
        # If parsing fails, return as single argument
        return [command]


def format_duration(seconds: Union[int, float]) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_timestamp(timestamp: str) -> str:
    """
    Format ISO timestamp to human-readable string.
    
    Args:
        timestamp: ISO timestamp string
        
    Returns:
        Formatted timestamp
    """
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except (ValueError, AttributeError):
        return timestamp or "Unknown"


def calculate_age(timestamp: str) -> str:
    """
    Calculate age from timestamp to now.
    
    Args:
        timestamp: ISO timestamp string
        
    Returns:
        Human-readable age string
    """
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        delta = now - dt
        
        seconds = delta.total_seconds()
        return format_duration(seconds)
    except (ValueError, AttributeError):
        return "Unknown"


def truncate_string(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate string to maximum length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    Safely parse JSON with default value on error.
    
    Args:
        text: JSON text to parse
        default: Default value if parsing fails
        
    Returns:
        Parsed JSON or default value
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(data: Any, default: str = "{}") -> str:
    """
    Safely serialize data to JSON with default on error.
    
    Args:
        data: Data to serialize
        default: Default value if serialization fails
        
    Returns:
        JSON string or default value
    """
    try:
        return json.dumps(data, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return default


def validate_job_id(job_id: str) -> bool:
    """
    Validate job ID format.
    
    Args:
        job_id: Job ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not job_id or not isinstance(job_id, str):
        return False
    
    # Check length and characters
    if len(job_id) < 1 or len(job_id) > 100:
        return False
    
    # Allow alphanumeric, hyphens, underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', job_id):
        return False
    
    return True


def ensure_directory_exists(path: Union[str, Path]) -> Path:
    """
    Ensure directory exists, creating it if necessary.
    
    Args:
        path: Directory path
        
    Returns:
        Path object for the directory
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def clean_command_output(output: str) -> str:
    """
    Clean command output for display.
    
    Args:
        output: Raw command output
        
    Returns:
        Cleaned output
    """
    if not output:
        return ""
    
    # Remove excessive whitespace
    lines = output.strip().split('\n')
    cleaned_lines = [line.rstrip() for line in lines]
    
    # Remove empty lines at start and end
    while cleaned_lines and not cleaned_lines[0]:
        cleaned_lines.pop(0)
    while cleaned_lines and not cleaned_lines[-1]:
        cleaned_lines.pop()
    
    return '\n'.join(cleaned_lines)


def format_table_row(columns: List[str], widths: List[int], separator: str = " | ") -> str:
    """
    Format a table row with specified column widths.
    
    Args:
        columns: Column values
        widths: Column widths
        separator: Column separator
        
    Returns:
        Formatted row string
    """
    formatted_columns = []
    
    for i, (col, width) in enumerate(zip(columns, widths)):
        col_str = str(col)
        if len(col_str) > width:
            col_str = truncate_string(col_str, width)
        formatted_columns.append(col_str.ljust(width))
    
    return separator.join(formatted_columns)


def create_table_header(headers: List[str], widths: List[int], separator: str = " | ") -> str:
    """
    Create a formatted table header with separator line.
    
    Args:
        headers: Header names
        widths: Column widths
        separator: Column separator
        
    Returns:
        Formatted header with separator line
    """
    header_row = format_table_row(headers, widths, separator)
    separator_row = separator.join(["-" * width for width in widths])
    
    return f"{header_row}\n{separator_row}"


def parse_key_value_args(args: List[str]) -> Dict[str, str]:
    """
    Parse key=value arguments from command line args.
    
    Args:
        args: Command line arguments
        
    Returns:
        Dictionary of key-value pairs
    """
    result = {}
    
    for arg in args:
        if '=' in arg:
            key, value = arg.split('=', 1)
            result[key.strip()] = value.strip()
    
    return result


def validate_timeout(timeout: Union[str, int]) -> Optional[int]:
    """
    Validate and convert timeout value.
    
    Args:
        timeout: Timeout value (string or int)
        
    Returns:
        Valid timeout in seconds or None if invalid
    """
    try:
        timeout_int = int(timeout)
        if 1 <= timeout_int <= 86400:  # 1 second to 24 hours
            return timeout_int
    except (ValueError, TypeError):
        pass
    
    return None


def validate_priority(priority: Union[str, int]) -> Optional[int]:
    """
    Validate and convert priority value.
    
    Args:
        priority: Priority value (string or int)
        
    Returns:
        Valid priority or None if invalid
    """
    try:
        priority_int = int(priority)
        if -100 <= priority_int <= 100:  # Reasonable priority range
            return priority_int
    except (ValueError, TypeError):
        pass
    
    return None


def get_system_info() -> Dict[str, Any]:
    """
    Get system information for debugging.
    
    Returns:
        Dictionary with system information
    """
    import platform
    import sys
    import os
    
    return {
        'platform': platform.platform(),
        'python_version': sys.version,
        'working_directory': os.getcwd(),
        'user': os.getenv('USER') or os.getenv('USERNAME', 'unknown'),
        'path': os.getenv('PATH', '').split(os.pathsep)[:5]  # First 5 PATH entries
    }


class ColorFormatter:
    """Simple color formatter for terminal output"""
    
    # ANSI color codes
    COLORS = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'reset': '\033[0m',
        'bold': '\033[1m'
    }
    
    @classmethod
    def colorize(cls, text: str, color: str) -> str:
        """
        Add color to text.
        
        Args:
            text: Text to colorize
            color: Color name
            
        Returns:
            Colorized text
        """
        if color in cls.COLORS:
            return f"{cls.COLORS[color]}{text}{cls.COLORS['reset']}"
        return text
    
    @classmethod
    def success(cls, text: str) -> str:
        """Format success message"""
        return cls.colorize(text, 'green')
    
    @classmethod
    def error(cls, text: str) -> str:
        """Format error message"""
        return cls.colorize(text, 'red')
    
    @classmethod
    def warning(cls, text: str) -> str:
        """Format warning message"""
        return cls.colorize(text, 'yellow')
    
    @classmethod
    def info(cls, text: str) -> str:
        """Format info message"""
        return cls.colorize(text, 'blue')
    
    @classmethod
    def bold(cls, text: str) -> str:
        """Format bold text"""
        return cls.colorize(text, 'bold')