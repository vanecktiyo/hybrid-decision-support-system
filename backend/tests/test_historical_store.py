"""Tests for HistoricalStore."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.historical_store import TIER_LABELS, HistoricalStore


@pytest.fixture
def store(tmp_path):
    return HistoricalStore(str(tmp_path / "historical"))


@pytest.fixture
def sample_features():
    return pd.DataFrame({"feat_a": [0.1, 0.5, 0.9, 0.3], "feat_b": [0.8, 0.2, 0.6, 0.4]})


@pytest.fixture
def sample_tiers():
    return pd.Series(["Faible", "Moyen", "Bon", "Excellent"])


# ------------------------------------------------------------------ write
class TestHistoricalStoreWrite:
    def test_save_creates_file(self, store, sample_features, sample_tiers, tmp_path):
        store.save(sample_features, sample_tiers, "s001")
        assert (tmp_path / "historical" / "s001.csv").exists()

    def test_save_returns_filepath(self, store, sample_features, sample_tiers):
        path = store.save(sample_features, sample_tiers, "s001")
        assert "s001.csv" in path

    def test_save_includes_validated_tier_column(self, store, sample_features, sample_tiers, tmp_path):
        store.save(sample_features, sample_tiers, "s001")
        df = pd.read_csv(tmp_path / "historical" / "s001.csv")
        assert "Validated_Tier" in df.columns

    def test_save_preserves_feature_values(self, store, sample_features, sample_tiers, tmp_path):
        store.save(sample_features, sample_tiers, "s001")
        df = pd.read_csv(tmp_path / "historical" / "s001.csv")
        assert list(df["feat_a"]) == list(sample_features["feat_a"])

    def test_save_multiple_sessions(self, store, sample_features, sample_tiers):
        store.save(sample_features, sample_tiers, "s001")
        store.save(sample_features, sample_tiers, "s002")
        assert store.n_sessions() == 2


# ------------------------------------------------------------------ read
class TestHistoricalStoreRead:
    def test_load_empty_store_returns_none_pair(self, store):
        X, y = store.load_all()
        assert X is None
        assert y is None

    def test_load_after_save_returns_dataframe(self, store, sample_features, sample_tiers):
        store.save(sample_features, sample_tiers, "s001")
        X, y = store.load_all()
        assert X is not None
        assert y is not None

    def test_load_row_count_matches(self, store, sample_features, sample_tiers):
        store.save(sample_features, sample_tiers, "s001")
        X, y = store.load_all()
        assert len(X) == len(sample_features)
        assert len(y) == len(sample_tiers)

    def test_load_tier_values_match(self, store, sample_features, sample_tiers):
        store.save(sample_features, sample_tiers, "s001")
        _, y = store.load_all()
        assert sorted(y.tolist()) == sorted(sample_tiers.tolist())

    def test_load_concatenates_multiple_sessions(self, store, sample_features, sample_tiers):
        store.save(sample_features, sample_tiers, "s001")
        store.save(sample_features, sample_tiers, "s002")
        X, y = store.load_all()
        assert len(X) == 2 * len(sample_features)

    def test_load_skips_file_without_validated_tier(self, store, tmp_path):
        bad_csv = tmp_path / "historical" / "bad.csv"
        bad_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"feat_a": [0.1]}).to_csv(bad_csv, index=False)
        X, y = store.load_all()
        assert X is None

    def test_load_feature_columns_do_not_include_validated_tier(self, store, sample_features, sample_tiers):
        store.save(sample_features, sample_tiers, "s001")
        X, _ = store.load_all()
        assert "Validated_Tier" not in X.columns


# ------------------------------------------------------------------ meta
class TestHistoricalStoreMeta:
    def test_list_sessions_empty(self, store):
        assert store.list_sessions() == []

    def test_list_sessions_shows_saved(self, store, sample_features, sample_tiers):
        store.save(sample_features, sample_tiers, "s001")
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "s001"

    def test_list_sessions_tier_distribution(self, store, sample_features, sample_tiers):
        store.save(sample_features, sample_tiers, "s001")
        sessions = store.list_sessions()
        dist = sessions[0]["tier_distribution"]
        for tier in TIER_LABELS:
            assert tier in dist

    def test_delete_existing_returns_true(self, store, sample_features, sample_tiers):
        store.save(sample_features, sample_tiers, "s001")
        result = store.delete_session("s001")
        assert result is True

    def test_delete_nonexistent_returns_false(self, store):
        assert store.delete_session("ghost") is False

    def test_delete_removes_file(self, store, sample_features, sample_tiers, tmp_path):
        store.save(sample_features, sample_tiers, "s001")
        store.delete_session("s001")
        assert not (tmp_path / "historical" / "s001.csv").exists()

    def test_n_sessions_zero_initially(self, store):
        assert store.n_sessions() == 0

    def test_n_sessions_increments(self, store, sample_features, sample_tiers):
        store.save(sample_features, sample_tiers, "s001")
        store.save(sample_features, sample_tiers, "s002")
        assert store.n_sessions() == 2

    def test_total_records_zero_initially(self, store):
        assert store.total_records() == 0

    def test_total_records_sums_all_sessions(self, store, sample_features, sample_tiers):
        store.save(sample_features, sample_tiers, "s001")
        store.save(sample_features, sample_tiers, "s002")
        assert store.total_records() == 2 * len(sample_features)
