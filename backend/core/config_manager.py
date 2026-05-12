"""
Configuration Manager - Load and manage YAML configuration
"""

import yaml
import logging
from pathlib import Path


class ConfigManager:
    """Load and manage application configuration from YAML files"""
    
    def __init__(self, config_path=None):
        """Initialize ConfigManager"""
        self.logger = logging.getLogger(__name__)
        self.config = {}
        
        if config_path:
            self.load(config_path)
    
    def load(self, config_path):
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}
            self.logger.info(f"Configuration loaded from {config_path}")
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            raise
    
    def get(self, key, default=None):
        """
        Get configuration value using dot notation
        Example: config.get('criteria.0.name')
        """
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                if isinstance(value, list):
                    value = value[int(k)]
                else:
                    value = value[k]
            return value
        except (KeyError, IndexError, TypeError, ValueError):
            return default
    
    def validate(self):
        """Validate configuration structure"""
        required_sections = ['data_source', 'criteria']
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        if not isinstance(self.config.get('criteria'), list) or len(self.config['criteria']) == 0:
            raise ValueError("Criteria must be a non-empty list")
        
        self.logger.info("Configuration validation successful")
        return True

