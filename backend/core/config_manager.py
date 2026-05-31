"""
Configuration Manager - Load and manage YAML methodological configuration.

`config.yaml` holds APP-WIDE methodological constants (test_size, AHP threshold,
fusion defaults, ...). Per-run settings (criteria, weights, ML target) come from
the UI via the API, NOT from here.

Usage (anywhere in the backend):
    from core.config_manager import get_settings
    get_settings().ml_test_size        # -> 0.2 (or YAML override)

Every accessor takes a built-in default, so a missing file or absent key never
breaks the pipeline — behaviour stays identical to the hard-coded constants.
"""

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# config.yaml lives at the project root: version_2/config.yaml
# config_manager.py is at version_2/backend/core/config_manager.py -> parents[2]
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


class ConfigManager:
    """Load and manage application configuration from YAML files."""

    def __init__(self, config_path=None):
        self.logger = logging.getLogger(__name__)
        self.config = {}
        if config_path:
            self.load(config_path)

    def load(self, config_path):
        """Load configuration from a YAML file. Never raises: logs and keeps {}."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
            self.logger.info(f"Configuration loaded from {config_path}")
        except FileNotFoundError:
            self.logger.warning(f"Config file not found at {config_path}; using built-in defaults")
            self.config = {}
        except Exception as e:
            self.logger.error(f"Error loading configuration ({e}); using built-in defaults")
            self.config = {}

    def get(self, key, default=None):
        """
        Get a configuration value using dot notation.
        Example: get('machine_learning.test_size', 0.2)
        """
        value = self.config
        try:
            for k in key.split("."):
                if isinstance(value, list):
                    value = value[int(k)]
                else:
                    value = value[k]
            return value if value is not None else default
        except (KeyError, IndexError, TypeError, ValueError):
            return default


class Settings:
    """
    Typed, defaulted accessors for the methodological constants.

    Each property reads from the loaded YAML but falls back to the historical
    hard-coded default, so the pipeline behaves identically if config.yaml is
    absent or partial.
    """

    def __init__(self, manager: ConfigManager):
        self._m = manager

    def _num(self, key, default, cast):
        try:
            return cast(self._m.get(key, default))
        except (TypeError, ValueError):
            logger.warning(f"Invalid value for '{key}'; using default {default}")
            return default

    # --- AHP ---
    @property
    def ahp_consistency_threshold(self) -> float:
        return self._num("ahp.consistency_threshold", 0.1, float)

    # --- Machine Learning ---
    @property
    def ml_test_size(self) -> float:
        return self._num("machine_learning.test_size", 0.2, float)

    @property
    def ml_min_samples(self) -> int:
        return self._num("machine_learning.min_samples", 8, int)

    @property
    def ml_cv_max_folds(self) -> int:
        return self._num("machine_learning.cv_max_folds", 5, int)

    @property
    def ml_tuning_iterations(self) -> int:
        return self._num("machine_learning.tuning_iterations", 20, int)

    @property
    def ml_max_permutation_samples(self) -> int:
        return self._num("machine_learning.max_permutation_samples", 500, int)

    # NOTE: hybrid fusion weights are a per-run UI choice, not a methodological
    # constant — intentionally not exposed here (see ranking.py / AHPMatrix.js).


_settings = None


def get_settings() -> Settings:
    """Return the process-wide Settings singleton (loads config.yaml once)."""
    global _settings
    if _settings is None:
        _settings = Settings(ConfigManager(DEFAULT_CONFIG_PATH))
    return _settings


def reload_settings(config_path=None) -> Settings:
    """Force a reload (useful for tests). Returns the fresh Settings."""
    global _settings
    _settings = Settings(ConfigManager(config_path or DEFAULT_CONFIG_PATH))
    return _settings
