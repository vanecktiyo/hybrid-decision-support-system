"""Tests for MLTrainer - classification 4-tier mode."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ml_trainer import TIER_LABELS, MIN_SAMPLES, MLTrainer


@pytest.fixture
def small_X():
    """20 samples × 3 features — enough to train (MIN_SAMPLES=8)."""
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        rng.uniform(0, 1, size=(20, 3)),
        columns=["feat_a", "feat_b", "feat_c"],
    )


@pytest.fixture
def continuous_y(small_X):
    """Continuous target correlated with features."""
    return pd.Series(
        small_X["feat_a"].values * 0.6
        + small_X["feat_b"].values * 0.4
        + np.random.default_rng(7).normal(0, 0.05, 20)
    )


@pytest.fixture
def trained_trainer(small_X, continuous_y):
    t = MLTrainer()
    t.train(small_X, continuous_y, y_is_continuous=True)
    return t


# ------------------------------------------------------------------ init
class TestMLTrainerInit:
    def test_not_trained_at_init(self):
        t = MLTrainer()
        assert not t.is_trained
        assert t.best_model is None

    def test_predict_before_train_raises(self, small_X):
        t = MLTrainer()
        with pytest.raises(ValueError):
            t.predict(small_X)

    def test_shap_before_train_returns_none(self, small_X):
        t = MLTrainer()
        assert t.compute_shap(small_X) is None


# ------------------------------------------------------------------ train
class TestMLTrainerTrain:
    def test_train_returns_enabled_true(self, small_X, continuous_y):
        t = MLTrainer()
        info = t.train(small_X, continuous_y, y_is_continuous=True)
        assert info["enabled"] is True

    def test_train_too_few_samples(self, small_X, continuous_y):
        t = MLTrainer()
        info = t.train(small_X.head(MIN_SAMPLES - 1), continuous_y.head(MIN_SAMPLES - 1))
        assert info["enabled"] is False

    def test_train_sets_is_trained(self, small_X, continuous_y):
        t = MLTrainer()
        t.train(small_X, continuous_y, y_is_continuous=True)
        assert t.is_trained

    def test_train_selects_best_model(self, trained_trainer):
        assert trained_trainer.best_model_name is not None
        assert trained_trainer.best_model is not None

    def test_train_info_has_expected_keys(self, small_X, continuous_y):
        t = MLTrainer()
        info = t.train(small_X, continuous_y, y_is_continuous=True)
        for key in ("best_model", "best_f1_macro", "model_results", "tier_labels", "class_distribution"):
            assert key in info

    def test_train_tier_labels_correct(self, small_X, continuous_y):
        t = MLTrainer()
        info = t.train(small_X, continuous_y, y_is_continuous=True)
        assert info["tier_labels"] == TIER_LABELS

    def test_train_f1_macro_in_valid_range(self, small_X, continuous_y):
        t = MLTrainer()
        info = t.train(small_X, continuous_y, y_is_continuous=True)
        assert 0.0 <= info["best_f1_macro"] <= 1.0

    def test_train_with_tier_labels_directly(self, small_X):
        tiers = pd.Series(TIER_LABELS * 5)
        t = MLTrainer()
        info = t.train(small_X, tiers, y_is_continuous=False)
        assert info["enabled"] is True


# ------------------------------------------------------------------ continuous_to_tiers
class TestContinuousToTiers:
    def test_four_tiers_produced(self):
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        tiers = MLTrainer._continuous_to_tiers(y)
        assert set(tiers).issubset({0, 1, 2, 3})

    def test_quartile_boundaries(self):
        y = np.arange(1, 101, dtype=float)
        tiers = MLTrainer._continuous_to_tiers(y)
        assert tiers[0] == 0   # lowest → Faible
        assert tiers[99] == 3  # highest → Excellent

    def test_output_length_matches_input(self):
        y = np.random.default_rng(0).uniform(0, 1, 50)
        tiers = MLTrainer._continuous_to_tiers(y)
        assert len(tiers) == 50


# ------------------------------------------------------------------ predict
class TestMLTrainerPredict:
    def test_predict_returns_three_arrays(self, trained_trainer, small_X):
        predicted_tiers, proba_exc, proba_full = trained_trainer.predict(small_X)
        assert predicted_tiers is not None
        assert proba_exc is not None
        assert proba_full is not None

    def test_predicted_tiers_valid_range(self, trained_trainer, small_X):
        predicted_tiers, _, _ = trained_trainer.predict(small_X)
        assert np.all((predicted_tiers >= 0) & (predicted_tiers <= 3))

    def test_proba_excellent_in_unit_interval(self, trained_trainer, small_X):
        _, proba_exc, _ = trained_trainer.predict(small_X)
        assert np.all((proba_exc >= 0) & (proba_exc <= 1))

    def test_proba_full_shape(self, trained_trainer, small_X):
        _, _, proba_full = trained_trainer.predict(small_X)
        assert proba_full.shape == (len(small_X), 4)

    def test_proba_full_rows_sum_to_one(self, trained_trainer, small_X):
        _, _, proba_full = trained_trainer.predict(small_X)
        row_sums = proba_full.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-6)

    def test_predict_output_length_matches_input(self, trained_trainer, small_X):
        predicted_tiers, proba_exc, _ = trained_trainer.predict(small_X)
        assert len(predicted_tiers) == len(small_X)
        assert len(proba_exc) == len(small_X)


# ------------------------------------------------------------------ SHAP
class TestMLTrainerSHAP:
    def test_compute_shap_returns_array_or_none(self, trained_trainer, small_X):
        result = trained_trainer.compute_shap(small_X)
        assert result is None or isinstance(result, np.ndarray)

    def test_shap_shape_when_available(self, trained_trainer, small_X):
        result = trained_trainer.compute_shap(small_X)
        if result is not None:
            assert result.shape == (len(small_X), small_X.shape[1])

    def test_format_shap_length_matches_samples(self, trained_trainer, small_X):
        shap_vals = trained_trainer.compute_shap(small_X)
        if shap_vals is None:
            pytest.skip("SHAP not available for this model")
        formatted = trained_trainer.format_shap_explanations(shap_vals, top_k=3)
        assert len(formatted) == len(small_X)

    def test_format_shap_entries_have_required_keys(self, trained_trainer, small_X):
        shap_vals = trained_trainer.compute_shap(small_X)
        if shap_vals is None:
            pytest.skip("SHAP not available for this model")
        formatted = trained_trainer.format_shap_explanations(shap_vals, top_k=2)
        for candidate_explanations in formatted:
            for entry in candidate_explanations:
                assert "feature" in entry
                assert "shap_value" in entry
                assert entry["direction"] in ("positive", "negative")

    def test_format_shap_top_k_respected(self, trained_trainer, small_X):
        shap_vals = trained_trainer.compute_shap(small_X)
        if shap_vals is None:
            pytest.skip("SHAP not available for this model")
        formatted = trained_trainer.format_shap_explanations(shap_vals, top_k=2)
        for entry in formatted:
            assert len(entry) <= 2


# ------------------------------------------------------------------ feature importance
class TestMLTrainerFeatureImportance:
    def test_feature_importance_keys_match_features(self, trained_trainer, small_X):
        imp = trained_trainer._get_feature_importance()
        if imp:
            assert set(imp.keys()) == set(small_X.columns)

    def test_feature_importance_sum_approx_one_for_tree(self, trained_trainer):
        imp = trained_trainer._get_feature_importance()
        if imp and trained_trainer.best_model_name in ("random_forest", "gradient_boosting", "decision_tree"):
            total = sum(imp.values())
            assert abs(total - 1.0) < 1e-5
