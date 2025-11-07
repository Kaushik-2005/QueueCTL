"""
Configuration management for QueueCTL

Handles system configuration with defaults and validation.
"""

from typing import Dict, Any, Optional
import os
from pathlib import Path


class Config:
    """
    Configuration management class for QueueCTL system.
    
    Provides default configuration values and methods to get/set configuration.
    """
    
    DEFAULT_CONFIG = {
        'max_retries': 3,
        'backoff_base': 2.0,
        'worker_timeout': 300,  # 5 minutes
        'cleanup_completed_after_hours': 24,
        'job_lock_timeout': 300,  # 5 minutes
        'storage_dir': None,  # Will be set to ~/.queuectl if None
        'log_level': 'INFO',
        'max_workers': 10
    }
    
    def __init__(self, storage_dir: Optional[str] = None, config_dict: Optional[Dict[str, Any]] = None):
        """
        Initialize configuration.
        
        Args:
            storage_dir: Directory for configuration storage
            config_dict: Optional configuration dictionary to use
        """
        if storage_dir is None:
            storage_dir = os.path.expanduser("~/.queuectl")
        
        self.storage_dir = storage_dir
        self.config_file = Path(storage_dir) / "config.json"
        
        # Initialize with defaults
        self._config = self.DEFAULT_CONFIG.copy()
        self._config['storage_dir'] = storage_dir
        
        # Override with provided config
        if config_dict:
            self._config.update(config_dict)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """
        Set configuration value with validation.
        
        Args:
            key: Configuration key
            value: Configuration value
            
        Returns:
            True if value was set, False if validation failed
        """
        # Validate the value
        if not self._validate_config_value(key, value):
            return False
        
        self._config[key] = value
        return True
    
    def update(self, config_dict: Dict[str, Any]) -> Dict[str, bool]:
        """
        Update multiple configuration values.
        
        Args:
            config_dict: Dictionary of configuration updates
            
        Returns:
            Dictionary mapping keys to success status
        """
        results = {}
        
        for key, value in config_dict.items():
            results[key] = self.set(key, value)
        
        return results
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration values.
        
        Returns:
            Complete configuration dictionary
        """
        return self._config.copy()
    
    def reset_to_defaults(self):
        """Reset configuration to default values"""
        self._config = self.DEFAULT_CONFIG.copy()
        self._config['storage_dir'] = self.storage_dir
    
    def _validate_config_value(self, key: str, value: Any) -> bool:
        """
        Validate configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
            
        Returns:
            True if valid, False otherwise
        """
        # Type and range validations
        validations = {
            'max_retries': lambda v: isinstance(v, int) and 0 <= v <= 100,
            'backoff_base': lambda v: isinstance(v, (int, float)) and 1.0 <= v <= 10.0,
            'worker_timeout': lambda v: isinstance(v, int) and 1 <= v <= 3600,
            'cleanup_completed_after_hours': lambda v: isinstance(v, int) and v >= 0,
            'job_lock_timeout': lambda v: isinstance(v, int) and 1 <= v <= 3600,
            'storage_dir': lambda v: isinstance(v, str) or v is None,
            'log_level': lambda v: v in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            'max_workers': lambda v: isinstance(v, int) and 1 <= v <= 100
        }
        
        if key in validations:
            return validations[key](value)
        
        # Unknown keys are allowed
        return True
    
    def get_validation_info(self) -> Dict[str, str]:
        """
        Get validation information for configuration keys.
        
        Returns:
            Dictionary mapping keys to validation descriptions
        """
        return {
            'max_retries': 'Integer between 0 and 100',
            'backoff_base': 'Number between 1.0 and 10.0',
            'worker_timeout': 'Integer between 1 and 3600 seconds',
            'cleanup_completed_after_hours': 'Non-negative integer',
            'job_lock_timeout': 'Integer between 1 and 3600 seconds',
            'storage_dir': 'String path or None',
            'log_level': 'One of: DEBUG, INFO, WARNING, ERROR, CRITICAL',
            'max_workers': 'Integer between 1 and 100'
        }
    
    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access"""
        return self._config[key]
    
    def __setitem__(self, key: str, value: Any):
        """Allow dictionary-style assignment"""
        self.set(key, value)
    
    def __contains__(self, key: str) -> bool:
        """Allow 'in' operator"""
        return key in self._config
    
    def __str__(self) -> str:
        """String representation"""
        return f"Config({dict(self._config)})"