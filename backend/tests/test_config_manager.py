"""Tests for ConfigManager / Settings — YAML methodological config with safe fallbacks."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_manager import ConfigManager, Settings, reload_settings


def _write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    return str(p)


class TestConfigManagerGet:
    def test_dot_notation(self, tmp_path):
        cm = ConfigManager(_write(tmp_path, "machine_learning:\n  test_size: 0.3\n"))
        assert cm.get("machine_learning.test_size") == 0.3

    def test_missing_key_returns_default(self, tmp_path):
        cm = ConfigManager(_write(tmp_path, "a: 1\n"))
        assert cm.get("does.not.exist", 42) == 42

    def test_missing_file_does_not_raise(self):
        cm = ConfigManager("/no/such/file.yaml")
        assert cm.config == {}
        assert cm.get("anything", "fallback") == "fallback"

    def test_null_value_uses_default(self, tmp_path):
        cm = ConfigManager(_write(tmp_path, "machine_learning:\n  test_size: null\n"))
        assert cm.get("machine_learning.test_size", 0.2) == 0.2


class TestSettingsDefaults:
    def test_all_defaults_when_empty(self):
        s = Settings(ConfigManager())  # no file loaded
        assert s.ml_test_size == 0.2
        assert s.ml_min_samples == 8
        assert s.ml_cv_max_folds == 5
        assert s.ml_tuning_iterations == 20
        assert s.ml_max_permutation_samples == 500
        assert s.ahp_consistency_threshold == 0.1

    def test_yaml_overrides(self, tmp_path):
        cfg = _write(tmp_path,
            "machine_learning:\n  test_size: 0.25\n  min_samples: 12\n"
            "ahp:\n  consistency_threshold: 0.08\n")
        s = Settings(ConfigManager(cfg))
        assert s.ml_test_size == 0.25
        assert s.ml_min_samples == 12
        assert s.ahp_consistency_threshold == 0.08
        # untouched keys keep defaults
        assert s.ml_cv_max_folds == 5

    def test_invalid_value_falls_back(self, tmp_path):
        cfg = _write(tmp_path, "machine_learning:\n  min_samples: not_a_number\n")
        s = Settings(ConfigManager(cfg))
        assert s.ml_min_samples == 8  # cast fails -> default

    def test_reload_settings_returns_settings(self):
        s = reload_settings()  # loads the real project config.yaml
        assert isinstance(s, Settings)
        assert 0.0 < s.ml_test_size < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
