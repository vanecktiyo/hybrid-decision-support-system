"""Tests for MLTrainer - classification mode (current API: train(X, y, historical_store, tier_labels, test_size))."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ml_trainer import TIER_LABELS, MIN_SAMPLES, MLTrainer


@pytest.fixture
def sep_X():
    """40 samples x 3 features, well separated into 4 tiers (10 each)."""
    rng = np.random.default_rng(42)
    blocks = []
    for centre in (0.1, 0.4, 0.6, 0.9):
        blocks.append(rng.normal(centre, 0.04, size=(10, 3)).clip(0, 1))
    return pd.DataFrame(np.vstack(blocks), columns=["feat_a", "feat_b", "feat_c"])


@pytest.fixture
def tier_y():
    """Tier labels aligned with sep_X blocks."""
    labels = []
    for t in TIER_LABELS:  # Faible, Moyen, Bon, Excellent
        labels += [t] * 10
    return pd.Series(labels)


@pytest.fixture
def trained_trainer(sep_X, tier_y):
    t = MLTrainer()
    t.train(sep_X, tier_y)
    return t


# ------------------------------------------------------------------ init
class TestMLTrainerInit:
    def test_not_trained_at_init(self):
        t = MLTrainer()
        assert not t.is_trained
        assert t.best_model is None

    def test_predict_before_train_raises(self, sep_X):
        t = MLTrainer()
        with pytest.raises(ValueError):
            t.predict(sep_X)

    def test_shap_before_train_returns_none(self, sep_X):
        t = MLTrainer()
        assert t.compute_shap(sep_X) is None


# ------------------------------------------------------------------ train
class TestMLTrainerTrain:
    def test_train_returns_enabled_true(self, sep_X, tier_y):
        info = MLTrainer().train(sep_X, tier_y)
        assert info["enabled"] is True

    def test_train_too_few_samples(self, sep_X, tier_y):
        info = MLTrainer().train(sep_X.head(MIN_SAMPLES - 1), tier_y.head(MIN_SAMPLES - 1))
        assert info["enabled"] is False

    def test_train_sets_is_trained(self, trained_trainer):
        assert trained_trainer.is_trained

    def test_train_selects_best_model(self, trained_trainer):
        assert trained_trainer.best_model_name is not None
        assert trained_trainer.best_model is not None

    def test_train_info_has_expected_keys(self, sep_X, tier_y):
        info = MLTrainer().train(sep_X, tier_y)
        for key in ("best_model", "best_f1_macro", "cv_score", "model_results",
                    "tier_labels", "class_distribution", "holdout_metrics"):
            assert key in info

    def test_train_score_in_valid_range(self, sep_X, tier_y):
        info = MLTrainer().train(sep_X, tier_y)
        assert 0.0 <= info["best_f1_macro"] <= 1.0

    def test_holdout_metrics_present_with_enough_data(self, sep_X, tier_y):
        # 10 samples/class, test_size 0.25 -> hold-out is feasible
        info = MLTrainer().train(sep_X, tier_y, test_size=0.25)
        assert info["holdout_metrics"] is not None
        assert "accuracy" in info["holdout_metrics"]
        assert 0.0 <= info["holdout_metrics"]["accuracy"] <= 1.0

    def test_holdout_disabled_when_test_size_zero(self, sep_X, tier_y):
        info = MLTrainer().train(sep_X, tier_y, test_size=0.0)
        assert info["holdout_metrics"] is None

    def test_deployed_model_matches_pipeline(self, trained_trainer):
        # The deployed model/scaler must come from the same fitted pipeline
        assert trained_trainer._pipeline is not None
        assert trained_trainer.best_model is trained_trainer._pipeline.named_steps["model"]
        assert trained_trainer.scaler is trained_trainer._pipeline.named_steps["scaler"]


# ------------------------------------------------------------------ consistent label encoding (fix #4)
class TestConsistentLabelEncoding:
    def test_custom_labels_train(self, sep_X):
        # Binary custom labels (e.g. Admis/Refusé) must train fine
        y = pd.Series((["Refuse"] * 20) + (["Admis"] * 20))
        info = MLTrainer().train(sep_X, y, tier_labels=["Refuse", "Admis"])
        assert info["enabled"] is True

    def test_history_uses_same_label_order(self, sep_X):
        # History labels must be encoded with label_order, not hard-coded TIER_LABELS.
        class FakeStore:
            def __init__(self, sessions):
                self._sessions = sessions
            def load_sessions(self):
                return self._sessions

        order = ["Refuse", "Admis"]
        y_cur = pd.Series((["Refuse"] * 10) + (["Admis"] * 10))
        hist_X = sep_X.head(10).reset_index(drop=True)              # same 3 features
        hist_y = pd.Series((["Admis"] * 5) + (["Refuse"] * 5))
        store = FakeStore([(hist_X, hist_y)])

        t = MLTrainer()
        t.feature_names = sep_X.columns.tolist()
        X_all, y_all = t._build_training_data(sep_X.head(20).reset_index(drop=True),
                                              y_cur, store, order)
        # Only class ids 0 and 1 may appear (never a stray index from TIER_LABELS)
        assert set(np.unique(y_all)).issubset({0, 1})
        assert len(y_all) == 30  # 20 current + 10 history (criteria match)


# ------------------------------------------------------------------ option C: feature-set matching
class TestHistoryFeatureMatching:
    class _Store:
        def __init__(self, sessions):
            self._sessions = sessions
        def load_sessions(self):
            return self._sessions

    def _trainer(self, sep_X):
        t = MLTrainer()
        t.feature_names = sep_X.columns.tolist()  # feat_a, feat_b, feat_c
        return t

    def test_matching_session_is_merged(self, sep_X):
        order = list(TIER_LABELS)
        y_cur = pd.Series(TIER_LABELS * 10)  # sep_X has 40 rows
        hist_X = sep_X.head(8).reset_index(drop=True)        # exact same columns
        hist_y = pd.Series(TIER_LABELS * 2)
        store = self._Store([(hist_X, hist_y)])
        t = self._trainer(sep_X)
        X_all, y_all = t._build_training_data(sep_X.reset_index(drop=True), y_cur, store, order)
        assert len(X_all) == 40 + 8  # merged

    def test_different_criteria_session_is_skipped(self, sep_X):
        order = list(TIER_LABELS)
        y_cur = pd.Series(TIER_LABELS * 10)
        # Historical session with DIFFERENT criteria (extra/renamed column)
        hist_X = pd.DataFrame({
            "feat_a": [0.1] * 8, "feat_b": [0.2] * 8, "Niveau_Math": [0.3] * 8,
        })
        hist_y = pd.Series(TIER_LABELS * 2)
        store = self._Store([(hist_X, hist_y)])
        t = self._trainer(sep_X)
        X_all, y_all = t._build_training_data(sep_X.reset_index(drop=True), y_cur, store, order)
        # Skipped entirely -> only the 40 current rows remain, never zero-filled
        assert len(X_all) == 40
        assert list(X_all.columns) == t.feature_names

    def test_mixed_sessions_only_matching_merged(self, sep_X):
        order = list(TIER_LABELS)
        y_cur = pd.Series(TIER_LABELS * 10)
        good = (sep_X.head(8).reset_index(drop=True), pd.Series(TIER_LABELS * 2))
        bad = (pd.DataFrame({"x": [0.1] * 8, "y": [0.2] * 8}), pd.Series(TIER_LABELS * 2))
        store = self._Store([good, bad])
        t = self._trainer(sep_X)
        X_all, _ = t._build_training_data(sep_X.reset_index(drop=True), y_cur, store, order)
        assert len(X_all) == 40 + 8  # only the matching session merged


# ------------------------------------------------------------------ predict
class TestMLTrainerPredict:
    def test_predict_returns_three_arrays(self, trained_trainer, sep_X):
        predicted_tiers, proba_exc, proba_full = trained_trainer.predict(sep_X)
        assert predicted_tiers is not None and proba_exc is not None and proba_full is not None

    def test_predicted_tiers_valid_range(self, trained_trainer, sep_X):
        predicted_tiers, _, _ = trained_trainer.predict(sep_X)
        assert np.all((predicted_tiers >= 0) & (predicted_tiers <= 3))

    def test_proba_excellent_in_unit_interval(self, trained_trainer, sep_X):
        _, proba_exc, _ = trained_trainer.predict(sep_X)
        assert np.all((proba_exc >= 0) & (proba_exc <= 1))

    def test_proba_full_shape(self, trained_trainer, sep_X):
        _, _, proba_full = trained_trainer.predict(sep_X)
        assert proba_full.shape == (len(sep_X), 4)

    def test_proba_full_rows_sum_to_one(self, trained_trainer, sep_X):
        _, _, proba_full = trained_trainer.predict(sep_X)
        np.testing.assert_allclose(proba_full.sum(axis=1), 1.0, atol=1e-6)

    def test_predict_output_length_matches_input(self, trained_trainer, sep_X):
        predicted_tiers, proba_exc, _ = trained_trainer.predict(sep_X)
        assert len(predicted_tiers) == len(sep_X)
        assert len(proba_exc) == len(sep_X)


# ------------------------------------------------------------------ SHAP
class TestMLTrainerSHAP:
    def test_compute_shap_returns_array_or_none(self, trained_trainer, sep_X):
        result = trained_trainer.compute_shap(sep_X)
        assert result is None or isinstance(result, np.ndarray)

    def test_shap_shape_when_available(self, trained_trainer, sep_X):
        result = trained_trainer.compute_shap(sep_X)
        if result is not None:
            assert result.shape == (len(sep_X), sep_X.shape[1])

    def test_format_shap_length_matches_samples(self, trained_trainer, sep_X):
        shap_vals = trained_trainer.compute_shap(sep_X)
        if shap_vals is None:
            pytest.skip("SHAP not available for this model")
        formatted = trained_trainer.format_shap_explanations(shap_vals, top_k=3)
        assert len(formatted) == len(sep_X)

    def test_format_shap_entries_have_required_keys(self, trained_trainer, sep_X):
        shap_vals = trained_trainer.compute_shap(sep_X)
        if shap_vals is None:
            pytest.skip("SHAP not available for this model")
        formatted = trained_trainer.format_shap_explanations(shap_vals, top_k=2)
        for candidate_explanations in formatted:
            for entry in candidate_explanations:
                assert "feature" in entry
                assert "shap_value" in entry
                assert entry["direction"] in ("positive", "negative")

    def test_format_shap_top_k_respected(self, trained_trainer, sep_X):
        shap_vals = trained_trainer.compute_shap(sep_X)
        if shap_vals is None:
            pytest.skip("SHAP not available for this model")
        formatted = trained_trainer.format_shap_explanations(shap_vals, top_k=2)
        for entry in formatted:
            assert len(entry) <= 2


# ------------------------------------------------------------------ feature importance
class TestMLTrainerFeatureImportance:
    def test_feature_importance_keys_match_features(self, trained_trainer, sep_X):
        imp = trained_trainer._get_feature_importance()
        if imp:
            assert set(imp.keys()) == set(sep_X.columns)

    def test_feature_importance_sum_approx_one_for_tree(self, trained_trainer):
        imp = trained_trainer._get_feature_importance()
        if imp and trained_trainer.best_model_name in ("random_forest", "gradient_boosting", "decision_tree"):
            assert abs(sum(imp.values()) - 1.0) < 1e-5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
