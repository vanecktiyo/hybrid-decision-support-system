"""
ML Trainer - Classification 4 tiers with SHAP explainability.
Tiers (ascending): Faible(0) | Moyen(1) | Bon(2) | Excellent(3)
Selection criterion: best cross-validated F1-macro.
SHAP: TreeExplainer for tree models, LinearExplainer for linear models.
Learns from current session (bootstrap via quartile binning) + historical validated rankings.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, RandomizedSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from core.config_manager import get_settings

try:
    from xgboost import XGBClassifier
    _XGBOOST_AVAILABLE = True
except ImportError:
    _XGBOOST_AVAILABLE = False

logger = logging.getLogger(__name__)

TIER_LABELS = ["Faible", "Moyen", "Bon", "Excellent"]
EXCELLENT_IDX = 3  # index of the "Excellent" class in TIER_LABELS

def _build_candidate_models() -> Dict[str, Any]:
    models = {
        "random_forest": RandomForestClassifier(
            n_estimators=100, max_depth=10, min_samples_split=5,
            class_weight="balanced", random_state=42
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
        ),
        "decision_tree": DecisionTreeClassifier(
            max_depth=8, min_samples_split=5,
            class_weight="balanced", random_state=42
        ),
        "logistic_regression": LogisticRegression(
            max_iter=1000, C=1.0, solver="lbfgs",
            class_weight="balanced", random_state=42
        ),
        "svm": SVC(
            probability=True, kernel="rbf", C=1.0,
            class_weight="balanced", random_state=42
        ),
    }
    if _XGBOOST_AVAILABLE:
        models["xgboost"] = XGBClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1,
            use_label_encoder=False, eval_metric="mlogloss",
            random_state=42, verbosity=0
        )
    return models

CANDIDATE_MODELS: Dict[str, Any] = _build_candidate_models()

PARAM_GRIDS: Dict[str, Any] = {
    "random_forest": {
        "n_estimators": [50, 100, 200, 300],
        "max_depth": [5, 8, 10, 15, None],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 2, 4],
    },
    "gradient_boosting": {
        "n_estimators": [50, 100, 200],
        "max_depth": [3, 5, 7],
        "learning_rate": [0.05, 0.1, 0.2],
        "min_samples_split": [2, 5],
    },
    "decision_tree": {
        "max_depth": [3, 5, 8, 12, None],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 2, 4],
        "criterion": ["gini", "entropy"],
    },
    "logistic_regression": {
        "C": [0.01, 0.1, 1.0, 10.0, 100.0],
        "max_iter": [500, 1000, 2000],
    },
    "svm": {
        "C": [0.1, 1.0, 10.0, 100.0],
        "kernel": ["rbf", "linear"],
        "gamma": ["scale", "auto"],
    },
    "xgboost": {
        "n_estimators": [50, 100, 200],
        "max_depth": [3, 5, 7],
        "learning_rate": [0.05, 0.1, 0.2],
        "subsample": [0.8, 1.0],
        "colsample_bytree": [0.8, 1.0],
    },
}

MODEL_DISPLAY_NAMES = {
    "random_forest": "Random Forest",
    "gradient_boosting": "Gradient Boosting",
    "decision_tree": "Decision Tree",
    "logistic_regression": "Logistic Regression",
    "svm": "SVM (RBF)",
    "xgboost": "XGBoost",
}

# Built-in fallback defaults. The live values are read from config.yaml via
# get_settings() at call time; these constants are used only if a key is absent.
MIN_SAMPLES = 8
MAX_PERMUTATION_SAMPLES = 500  # cap PermutationExplainer for very large datasets
TEST_SIZE = 0.2  # fraction held out for honest evaluation


class MLTrainer:
    def __init__(self):
        self.best_model = None
        self.best_model_name: Optional[str] = None
        self.scaler = MinMaxScaler()
        self._pipeline: Optional[Pipeline] = None
        self.model_results: Dict[str, Any] = {}
        self.feature_names: List[str] = []
        self.is_trained = False
        self._X_scaled_train: Optional[np.ndarray] = None
        self.excellent_idx: int = EXCELLENT_IDX  # highest class = best tier

    # ------------------------------------------------------------------ public

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        historical_store=None,
        tier_labels: Optional[List[str]] = None,
        test_size: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Train all candidate classifiers, select best by cross-validated score.

        Methodology (leak-free):
          - Scaling is done INSIDE a Pipeline so the scaler is fit on each CV
            training fold only (never on validation rows).
          - When enough data is available, a stratified hold-out (test_size) gives
            an honest generalization estimate of the finally selected model.
          - The model finally deployed is then refit on ALL data (standard practice:
            evaluate on a split, deploy on everything) so predictions use max data.

        Args:
            X: normalized criteria values (current session, DataFrame)
            y: target — pre-encoded integer tiers, or categorical tier labels
            historical_store: HistoricalStore instance (optional, loads past sessions)
            tier_labels: ordered class labels (index = class id). Used to encode
                string labels CONSISTENTLY across current session and history.
                Defaults to TIER_LABELS.
            test_size: fraction held out for honest evaluation (0 disables hold-out).
                If None, read from config.yaml (machine_learning.test_size).
        """
        settings = get_settings()
        if test_size is None:
            test_size = settings.ml_test_size
        min_samples = settings.ml_min_samples
        cv_max_folds = settings.ml_cv_max_folds

        if len(X) < min_samples:
            logger.warning(f"Too few samples ({len(X)} < {min_samples}). Skipping ML.")
            return {
                "enabled": False,
                "reason": f"Too few samples (minimum {min_samples} required)",
            }

        label_order = tier_labels if tier_labels else TIER_LABELS
        self.feature_names = X.columns.tolist()
        X_all, y_all = self._build_training_data(X, y, historical_store, label_order)

        if X_all is None or len(X_all) == 0:
            return {"enabled": False, "reason": "Failed to build training data"}

        # Set excellent_idx dynamically based on actual classes in training data
        self.excellent_idx = int(np.max(y_all))
        logger.info(
            f"Training on {len(X_all)} samples ({len(self.feature_names)} features), "
            f"excellent_idx={self.excellent_idx}"
        )

        # Missing values were already imputed upstream by DataProcessor (default
        # strategy 'zero' = constant 0, which leaks nothing; mean/median impute on
        # the full set — a negligible, accepted micro-leak). This .fillna is only a
        # defensive guard for residual NaN (e.g. an all-NaN column).
        # NOTE: NORMALIZATION, the real leakage risk, is NOT done here — it lives in
        # the per-fold Pipeline (MinMaxScaler) so the scaler never sees validation rows.
        X_all = X_all.fillna(X_all.mean(numeric_only=True)).fillna(0.0)
        X_mat = X_all.values.astype(float)

        unique, counts = np.unique(y_all, return_counts=True)
        # Use raw class indices as keys — caller maps them to actual labels
        class_dist = {str(int(c)): int(cnt) for c, cnt in zip(unique, counts)}
        logger.info(f"Class distribution: {class_dist}")

        if len(unique) < 2:
            return {"enabled": False, "reason": "Only one class in training data"}

        min_class = int(counts.min())
        n_folds = min(cv_max_folds, max(2, min_class))
        n_classes = len(unique)

        # Adapt primary metric to number of classes
        is_binary = n_classes == 2
        primary_scoring = "roc_auc" if is_binary else "f1_macro"
        metric_label = "ROC-AUC" if is_binary else "F1-macro"
        logger.info(f"Primary metric: {metric_label} ({'binary' if is_binary else 'multiclass'})")

        # Optional stratified hold-out for an honest generalization estimate.
        # Requires at least 2 samples per class AND at least one test sample per class.
        X_fit, y_fit = X_mat, y_all
        X_holdout = y_holdout = None
        if 0.0 < test_size < 1.0 and min_class >= 2 and int(np.floor(min_class * test_size)) >= 1:
            try:
                X_fit, X_holdout, y_fit, y_holdout = train_test_split(
                    X_mat, y_all, test_size=test_size, random_state=42, stratify=y_all
                )
                # Recompute folds on the (smaller) training split
                _, fit_counts = np.unique(y_fit, return_counts=True)
                n_folds = min(cv_max_folds, max(2, int(fit_counts.min())))
                logger.info(f"Hold-out: {len(X_holdout)} test / {len(X_fit)} train samples")
            except ValueError as exc:
                logger.info(f"Hold-out split not feasible ({exc}); evaluating with CV only")
                X_fit, y_fit, X_holdout, y_holdout = X_mat, y_all, None, None

        results: Dict[str, Any] = {}
        best_score = -1.0
        best_name: Optional[str] = None

        # Phase 1: model selection by leak-free CV (scaler fit per fold via Pipeline)
        for name, template in CANDIDATE_MODELS.items():
            try:
                pipe = self._make_pipeline(template)
                primary_scores = cross_val_score(
                    pipe, X_fit, y_fit, cv=n_folds, scoring=primary_scoring
                )
                acc_scores = cross_val_score(
                    self._make_pipeline(template), X_fit, y_fit, cv=n_folds, scoring="accuracy"
                )
                score = float(primary_scores.mean())
                acc = float(acc_scores.mean())

                results[name] = {
                    "display_name": MODEL_DISPLAY_NAMES[name],
                    "f1_macro": round(score, 4),
                    "f1_std": round(float(primary_scores.std()), 4),
                    "accuracy": round(acc, 4),
                    "cv_folds": n_folds,
                    "metric": metric_label,
                    "status": "success",
                }
                logger.info(f"  {name}: {metric_label}={score:.4f}  accuracy={acc:.4f}")

                if score > best_score:
                    best_score = score
                    best_name = name

            except Exception as exc:
                logger.warning(f"  {name} failed: {exc}")
                results[name] = {
                    "display_name": MODEL_DISPLAY_NAMES[name],
                    "status": "failed",
                    "error": str(exc),
                }

        if best_name is None:
            return {"enabled": False, "reason": "All models failed during training"}

        # Phase 2: tune the winner. Keep the tuned config ONLY if it beats defaults;
        # otherwise fall back to the default pipeline so the deployed model always
        # matches the reported score (no tuned-but-worse model sneaking in).
        default_pipe = self._make_pipeline(CANDIDATE_MODELS[best_name])
        tuned_pipe, tuned_score, best_params = self._tune_model(
            best_name, X_fit, y_fit, n_folds, scoring=primary_scoring
        )
        if tuned_pipe is not None and tuned_score > best_score:
            logger.info(
                f"Tuning improved {metric_label}: {best_score:.4f} → {tuned_score:.4f}  params={best_params}"
            )
            best_score = tuned_score
            chosen_pipe = tuned_pipe
            results[best_name]["f1_macro"] = round(tuned_score, 4)
            results[best_name]["tuned_params"] = best_params
        else:
            logger.info(
                f"Tuning did not improve {metric_label} "
                f"({tuned_score:.4f} <= {best_score:.4f}); keeping default params"
            )
            chosen_pipe = default_pipe

        # Honest hold-out evaluation of the chosen configuration (before final refit)
        holdout_metrics = None
        if X_holdout is not None:
            try:
                from sklearn.base import clone
                from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
                eval_pipe = clone(chosen_pipe).fit(X_fit, y_fit)
                y_pred = eval_pipe.predict(X_holdout)
                holdout_metrics = {
                    "accuracy": round(float(accuracy_score(y_holdout, y_pred)), 4),
                    "f1_macro": round(float(f1_score(y_holdout, y_pred, average="macro")), 4),
                    "n_test": int(len(y_holdout)),
                }
                if is_binary:
                    try:
                        proba = eval_pipe.predict_proba(X_holdout)[:, 1]
                        holdout_metrics["roc_auc"] = round(float(roc_auc_score(y_holdout, proba)), 4)
                    except Exception:
                        pass
                logger.info(f"Hold-out {metric_label}: {holdout_metrics}")
            except Exception as exc:
                logger.warning(f"Hold-out evaluation failed: {exc}")

        # Final deployment: refit chosen pipeline on ALL data (train + hold-out)
        self._pipeline = chosen_pipe.fit(X_mat, y_all)
        self.scaler = self._pipeline.named_steps["scaler"]
        self.best_model = self._pipeline.named_steps["model"]
        self._X_scaled_train = self.scaler.transform(X_mat)
        self.best_model_name = best_name
        self.model_results = results
        self.is_trained = True

        logger.info(f"Best model: {best_name}  CV {metric_label}={best_score:.4f}")

        return {
            "enabled": True,
            "best_model": best_name,
            "best_model_display": MODEL_DISPLAY_NAMES[best_name],
            "best_f1_macro": round(best_score, 4),
            "cv_score": round(best_score, 4),
            "holdout_metrics": holdout_metrics,
            "metric_label": metric_label,
            "is_binary": is_binary,
            "model_results": results,
            "feature_importance": self._get_feature_importance(),
            "class_distribution": class_dist,
            "n_samples": len(X_all),
            "n_features": len(self.feature_names),
            "tier_labels": TIER_LABELS,
        }

    @staticmethod
    def _make_pipeline(template) -> Pipeline:
        """Wrap an estimator with its own MinMaxScaler so CV scales per fold."""
        fresh = template.__class__(**template.get_params())
        return Pipeline([("scaler", MinMaxScaler()), ("model", fresh)])

    def predict(
        self, X: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Predict tiers and probabilities for new data.

        Returns:
            predicted_tiers   – int array (0-3) aligned with X rows
            proba_excellent   – float array, P(Excellent) per sample, in [0,1]
            proba_full        – (n, 4) float array, P(tier) for all 4 tiers
        """
        if not self.is_trained or self.best_model is None:
            raise ValueError("No model trained. Call train() first.")

        X_input = X[self.feature_names].copy().fillna(
            X[self.feature_names].mean(numeric_only=True)
        ).fillna(0.0)
        X_scaled = self.scaler.transform(X_input.values.astype(float))
        raw_proba = self.best_model.predict_proba(X_scaled)

        # Map model classes to full probability array
        n_classes = self.excellent_idx + 1
        proba_full = np.zeros((len(X), n_classes))
        for i, cls in enumerate(self.best_model.classes_):
            if i < raw_proba.shape[1] and int(cls) < n_classes:
                proba_full[:, int(cls)] = raw_proba[:, i]

        # Predicted class = highest probability class (consistent with ML_Score)
        predicted_classes = np.argmax(proba_full, axis=1)

        proba_excellent = proba_full[:, min(self.excellent_idx, proba_full.shape[1] - 1)]
        return predicted_classes, proba_excellent, proba_full

    def compute_shap(self, X: pd.DataFrame) -> Optional[np.ndarray]:
        """
        Compute SHAP values targeting the Excellent class.

        Strategy:
          1. Tree models → shap.TreeExplainer (fast, exact)
          2. Linear models → shap.LinearExplainer
          3. Any failure → shap.Explainer with predict_proba wrapper (Permutation, slower)
          4. ImportError or total failure → None

        Returns:
            (n_samples, n_features) array of SHAP values, or None.
        """
        if not self.is_trained or self.best_model is None:
            return None
        try:
            import shap
        except ImportError:
            logger.warning("SHAP not installed. Run: pip install shap")
            return None

        X_scaled = self.scaler.transform(
            X[self.feature_names].values.astype(float)
        )
        background = self._X_scaled_train if self._X_scaled_train is not None else X_scaled
        bg = background[: min(100, len(background))]

        is_tree = hasattr(self.best_model, "feature_importances_")
        is_linear = hasattr(self.best_model, "coef_") and not is_tree

        # ── Attempt 1: TreeExplainer in raw/margin space (log-odds)
        # model_output="raw" gives log-odds contributions which have real variance
        # even when P(Excellent)≈1 — avoids the near-zero collapse in probability space
        try:
            if is_tree:
                explainer = shap.TreeExplainer(self.best_model, model_output="raw")
                raw = explainer.shap_values(X_scaled)
                sv = self._extract_excellent_slice(raw)
                if np.max(np.abs(sv)) > 1e-8:
                    return sv
                raise ValueError("near-zero SHAP values even in raw space")
            elif is_linear:
                explainer = shap.LinearExplainer(self.best_model, bg)
                raw = explainer.shap_values(X_scaled)
                return self._extract_excellent_slice(raw)
            else:
                raise ValueError("no fast explainer for this model type")
        except Exception as exc:
            logger.info(f"Fast SHAP failed ({exc}); trying unified shap.Explainer")

        # ── Attempt 1b: unified shap.Explainer
        try:
            explainer = shap.Explainer(self.best_model, bg)
            result = explainer(X_scaled)
            raw = result.values
            sv = self._extract_excellent_slice(raw)
            if np.max(np.abs(sv)) > 1e-8:
                return sv
            raise ValueError("near-zero SHAP values from unified Explainer")
        except Exception as exc1b:
            logger.info(f"Unified SHAP Explainer failed ({exc1b}); trying PermutationExplainer")

        # ── Attempt 2: PermutationExplainer on P(Excellent) directly
        try:
            model = self.best_model
            excellent_idx = self.excellent_idx

            def _proba_excellent(X_arr: np.ndarray) -> np.ndarray:
                proba = model.predict_proba(X_arr)
                n_cls = max(excellent_idx + 1, proba.shape[1])
                full = np.zeros((len(X_arr), n_cls))
                for i, cls in enumerate(model.classes_):
                    if i < proba.shape[1]:
                        full[:, int(cls)] = proba[:, i]
                return full[:, min(excellent_idx, full.shape[1] - 1)]

            n_total = len(X_scaled)
            max_perm = get_settings().ml_max_permutation_samples
            # Cap only for very large datasets to avoid extreme timeouts
            if n_total > max_perm:
                logger.info(f"  PermutationExplainer: capping to {max_perm}/{n_total} samples")
                compute_indices = np.arange(max_perm, dtype=int)
                X_subset = X_scaled[compute_indices]
            else:
                compute_indices = None
                X_subset = X_scaled

            n_feats = X_subset.shape[1]
            explainer = shap.PermutationExplainer(
                _proba_excellent, bg, max_evals=2 * n_feats + 1
            )
            result = explainer(X_subset)
            sv_subset = result.values
            if sv_subset.ndim == 1:
                sv_subset = sv_subset.reshape(len(X_subset), -1)

            if compute_indices is not None:
                # Fill remaining rows by nearest computed neighbor (same background approx)
                sv = np.zeros((n_total, sv_subset.shape[1]))
                sv[compute_indices] = sv_subset
                # Compute remaining candidates in batches
                remaining = np.arange(max_perm, n_total, dtype=int)
                if len(remaining) > 0:
                    result2 = explainer(X_scaled[remaining])
                    sv2 = result2.values
                    if sv2.ndim == 1:
                        sv2 = sv2.reshape(len(remaining), -1)
                    sv[remaining] = sv2
                return sv
            return sv_subset

        except Exception as exc2:
            logger.warning(f"SHAP PermutationExplainer also failed: {exc2}")
            return None

    def _extract_excellent_slice(self, raw) -> np.ndarray:
        """Normalise shap output to (n_samples, n_features) for the best (Excellent) class."""
        idx = self.excellent_idx
        if isinstance(raw, list):
            return np.array(raw[min(idx, len(raw) - 1)])
        if isinstance(raw, np.ndarray) and raw.ndim == 3:
            return raw[:, :, min(idx, raw.shape[2] - 1)]
        return np.array(raw)

    def format_shap_explanations(
        self, shap_values: np.ndarray, top_k: int = None
    ) -> List[List[dict]]:
        """Convert SHAP matrix to per-candidate top-k explanations."""
        k = top_k if top_k is not None else len(self.feature_names)
        explanations = []
        for row in shap_values:
            top_idx = np.argsort(np.abs(row))[::-1][:k]
            explanations.append(
                [
                    {
                        "feature": self.feature_names[j],
                        "shap_value": round(float(row[j]), 6),
                        "direction": "positive" if row[j] >= 0 else "negative",
                    }
                    for j in top_idx
                ]
            )
        return explanations

    # ------------------------------------------------------------------ private

    def _tune_model(
        self,
        model_name: str,
        X: np.ndarray,
        y: np.ndarray,
        n_folds: int,
        n_iter: Optional[int] = None,
        scoring: str = "f1_macro",
    ) -> Tuple[Optional[Pipeline], float, dict]:
        """
        Run RandomizedSearchCV on a (scaler, model) Pipeline for the selected model.
        Scaling stays inside the pipeline, so each CV fold scales independently.

        Returns (best_pipeline, best_cv_score, best_params), or (None, -1, {}) when
        there is no grid or tuning fails — the caller then keeps the default config.
        """
        param_grid = PARAM_GRIDS.get(model_name, {})
        if not param_grid:
            return None, -1.0, {}

        if n_iter is None:
            n_iter = get_settings().ml_tuning_iterations

        # Prefix params for the "model" step of the pipeline (e.g. n_estimators -> model__n_estimators)
        pipe = self._make_pipeline(CANDIDATE_MODELS[model_name])
        pipe_grid = {f"model__{k}": v for k, v in param_grid.items()}

        try:
            search = RandomizedSearchCV(
                estimator=pipe,
                param_distributions=pipe_grid,
                n_iter=n_iter,
                scoring=scoring,
                cv=n_folds,
                random_state=42,
                n_jobs=-1,
            )
            search.fit(X, y)
            logger.info(
                f"  RandomizedSearchCV ({model_name}): best {scoring}={search.best_score_:.4f}  "
                f"params={search.best_params_}"
            )
            return search.best_estimator_, float(search.best_score_), search.best_params_
        except Exception as exc:
            logger.warning(f"  Tuning failed for {model_name}: {exc}. Keeping defaults.")
            return None, -1.0, {}

    def _build_training_data(
        self,
        X_current: pd.DataFrame,
        y_current: pd.Series,
        historical_store,
        label_order: List[str],
    ) -> Tuple[Optional[pd.DataFrame], Optional[np.ndarray]]:
        """
        Assemble (X, y) from the current session + compatible historical sessions.

        Label encoding: both sources use the SAME `label_order` so class ids are
        consistent (e.g. Admis/Refusé encoded identically across sessions).

        Feature matching (option C): criteria are NOT standard — the user picks
        them per session — so a historical session is only merged when its feature
        set EXACTLY matches the current run's criteria. Sessions with different
        criteria are skipped, never zero-filled (a missing criterion is genuinely
        absent, not a worst-case 0 value). This keeps every merged row on the same
        feature space and avoids injecting fake signal.
        """
        def encode(labels) -> np.ndarray:
            # Default fallback index = "neutral" middle class, clamped to range
            fallback = min(1, len(label_order) - 1)
            return np.array(
                [label_order.index(t) if t in label_order else fallback for t in labels]
            )

        current_features = set(self.feature_names)
        X_parts: List[pd.DataFrame] = []
        y_parts: List[np.ndarray] = []

        # Current session — y is either pre-encoded integers or categorical labels
        if pd.api.types.is_numeric_dtype(y_current):
            y_tiers = y_current.values.astype(int)
        else:
            y_tiers = encode(y_current.values)
        X_parts.append(X_current[self.feature_names].copy())
        y_parts.append(y_tiers)

        # Historical sessions — merged ONLY if their criteria match exactly
        if historical_store is not None and hasattr(historical_store, "load_sessions"):
            merged, skipped = 0, 0
            for X_hist, y_hist in historical_store.load_sessions():
                if X_hist is None or y_hist is None or len(X_hist) == 0:
                    continue
                # Exact feature-set match required (ignoring column order)
                if set(X_hist.columns) != current_features:
                    skipped += 1
                    continue
                X_h = X_hist[self.feature_names].copy()  # reorder to current order
                y_h = encode(y_hist.values)
                X_parts.append(X_h)
                y_parts.append(y_h)
                merged += len(X_h)
            if merged:
                logger.info(f"  + {merged} historical records merged (same criteria)")
            if skipped:
                logger.info(f"  {skipped} historical session(s) skipped (different criteria)")

        if not X_parts:
            return None, None

        X_all = pd.concat(X_parts, ignore_index=True)
        y_all = np.concatenate(y_parts)
        return X_all, y_all

    def _get_feature_importance(self) -> Dict[str, float]:
        if self.best_model is None:
            return {}
        if hasattr(self.best_model, "feature_importances_"):
            imp = self.best_model.feature_importances_
            total = imp.sum()
            if total > 0:
                imp = imp / total
            return {n: round(float(v), 6) for n, v in zip(self.feature_names, imp)}
        if hasattr(self.best_model, "coef_"):
            # Multi-class: coef_ is (n_classes, n_features) — average absolute values
            coef = np.abs(self.best_model.coef_).mean(axis=0)
            total = coef.sum()
            if total > 0:
                coef = coef / total
            return {n: round(float(v), 6) for n, v in zip(self.feature_names, coef)}
        return {}
