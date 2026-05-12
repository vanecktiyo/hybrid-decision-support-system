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
from sklearn.metrics import accuracy_score
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import MinMaxScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

logger = logging.getLogger(__name__)

TIER_LABELS = ["Faible", "Moyen", "Bon", "Excellent"]
EXCELLENT_IDX = 3  # index of the "Excellent" class in TIER_LABELS

CANDIDATE_MODELS: Dict[str, Any] = {
    "random_forest": RandomForestClassifier(
        n_estimators=100, max_depth=10, min_samples_split=5, random_state=42
    ),
    "gradient_boosting": GradientBoostingClassifier(
        n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
    ),
    "decision_tree": DecisionTreeClassifier(
        max_depth=8, min_samples_split=5, random_state=42
    ),
    "logistic_regression": LogisticRegression(
        max_iter=1000, C=1.0, solver="lbfgs", random_state=42
    ),
    "svm": SVC(probability=True, kernel="rbf", C=1.0, random_state=42),
}

MODEL_DISPLAY_NAMES = {
    "random_forest": "Random Forest",
    "gradient_boosting": "Gradient Boosting",
    "decision_tree": "Decision Tree",
    "logistic_regression": "Logistic Regression",
    "svm": "SVM (RBF)",
}

MIN_SAMPLES = 8
MAX_PERMUTATION_SAMPLES = 50  # cap PermutationExplainer to avoid timeouts on large datasets


class MLTrainer:
    def __init__(self):
        self.best_model = None
        self.best_model_name: Optional[str] = None
        self.scaler = MinMaxScaler()
        self.model_results: Dict[str, Any] = {}
        self.feature_names: List[str] = []
        self.is_trained = False
        self._X_scaled_train: Optional[np.ndarray] = None

    # ------------------------------------------------------------------ public

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        historical_store=None,
        y_is_continuous: bool = True,
    ) -> Dict[str, Any]:
        """
        Train all candidate classifiers, select best by F1-macro.

        Args:
            X: normalized criteria values (current session, DataFrame)
            y: target – continuous score if y_is_continuous=True (quartile-binned
               into tiers), or TIER_LABELS strings if y_is_continuous=False
            historical_store: HistoricalStore instance (optional, loads past sessions)
            y_is_continuous: whether y contains numeric scores to bin into tiers
        """
        if len(X) < MIN_SAMPLES:
            logger.warning(f"Too few samples ({len(X)} < {MIN_SAMPLES}). Skipping ML.")
            return {
                "enabled": False,
                "reason": f"Too few samples (minimum {MIN_SAMPLES} required)",
            }

        self.feature_names = X.columns.tolist()
        X_all, y_all = self._build_training_data(X, y, historical_store, y_is_continuous)

        if X_all is None or len(X_all) == 0:
            return {"enabled": False, "reason": "Failed to build training data"}

        logger.info(
            f"Training on {len(X_all)} samples ({len(self.feature_names)} features)"
        )

        # Fill any residual NaN with column mean then 0 (defensive — handles all-NaN cols)
        X_all = X_all.fillna(X_all.mean(numeric_only=True)).fillna(0.0)

        X_scaled = self.scaler.fit_transform(X_all.values.astype(float))
        self._X_scaled_train = X_scaled

        unique, counts = np.unique(y_all, return_counts=True)
        class_dist = {TIER_LABELS[int(c)]: int(cnt) for c, cnt in zip(unique, counts)}
        logger.info(f"Class distribution: {class_dist}")

        if len(unique) < 2:
            return {"enabled": False, "reason": "Only one class in training data"}

        n_folds = min(5, max(2, int(counts.min())))

        results: Dict[str, Any] = {}
        best_f1 = -1.0
        best_name: Optional[str] = None

        for name, template in CANDIDATE_MODELS.items():
            try:
                model = template.__class__(**template.get_params())
                f1_scores = cross_val_score(
                    model, X_scaled, y_all, cv=n_folds, scoring="f1_macro"
                )
                acc_scores = cross_val_score(
                    model, X_scaled, y_all, cv=n_folds, scoring="accuracy"
                )
                f1 = float(f1_scores.mean())
                acc = float(acc_scores.mean())

                results[name] = {
                    "display_name": MODEL_DISPLAY_NAMES[name],
                    "f1_macro": round(f1, 4),
                    "f1_std": round(float(f1_scores.std()), 4),
                    "accuracy": round(acc, 4),
                    "cv_folds": n_folds,
                    "status": "success",
                }
                logger.info(f"  {name}: F1-macro={f1:.4f}  accuracy={acc:.4f}")

                if f1 > best_f1:
                    best_f1 = f1
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

        self.best_model = CANDIDATE_MODELS[best_name].__class__(
            **CANDIDATE_MODELS[best_name].get_params()
        )
        self.best_model.fit(X_scaled, y_all)
        self.best_model_name = best_name
        self.model_results = results
        self.is_trained = True

        logger.info(f"Best model: {best_name}  F1-macro={best_f1:.4f}")

        return {
            "enabled": True,
            "best_model": best_name,
            "best_model_display": MODEL_DISPLAY_NAMES[best_name],
            "best_f1_macro": round(best_f1, 4),
            "model_results": results,
            "feature_importance": self._get_feature_importance(),
            "class_distribution": class_dist,
            "n_samples": len(X_all),
            "n_features": len(self.feature_names),
            "tier_labels": TIER_LABELS,
        }

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
        predicted_classes = self.best_model.predict(X_scaled)
        raw_proba = self.best_model.predict_proba(X_scaled)  # (n, k)

        # Map model classes to full 4-tier probability array
        proba_full = np.zeros((len(X), 4))
        for i, cls in enumerate(self.best_model.classes_):
            proba_full[:, int(cls)] = raw_proba[:, i]

        proba_excellent = proba_full[:, EXCELLENT_IDX]
        return predicted_classes, proba_excellent, proba_full

    def compute_shap(self, X: pd.DataFrame, priority_indices: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
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

        # ── Attempt 1: native fast explainer ─────────────────────────────────
        try:
            if is_tree:
                explainer = shap.TreeExplainer(self.best_model)
                raw = explainer.shap_values(X_scaled)
            elif is_linear:
                explainer = shap.LinearExplainer(self.best_model, bg)
                raw = explainer.shap_values(X_scaled)
            else:
                raise ValueError("no fast explainer for this model type")

            return self._extract_excellent_slice(raw)

        except Exception as exc:
            logger.info(f"Fast SHAP failed ({exc}); trying unified shap.Explainer")

        # ── Attempt 1b: unified shap.Explainer (handles multiclass GB in SHAP ≥ 0.41)
        try:
            explainer = shap.Explainer(self.best_model, bg)
            result = explainer(X_scaled)
            raw = result.values
            return self._extract_excellent_slice(raw)
        except Exception as exc1b:
            logger.info(f"Unified SHAP Explainer failed ({exc1b}); trying PermutationExplainer")

        # ── Attempt 2: PermutationExplainer (universal fallback, shap ≥ 0.40)
        try:
            model = self.best_model

            def _proba_excellent(X_arr: np.ndarray) -> np.ndarray:
                proba = model.predict_proba(X_arr)
                full = np.zeros((len(X_arr), 4))
                for i, cls in enumerate(model.classes_):
                    full[:, int(cls)] = proba[:, i]
                return full[:, EXCELLENT_IDX]

            n_total = len(X_scaled)
            if priority_indices is not None and len(priority_indices) > 0:
                # Always include priority rows (top-ranked candidates)
                prio = priority_indices[:MAX_PERMUTATION_SAMPLES]
                extra = [i for i in range(n_total) if i not in set(prio)]
                extra = extra[:max(0, MAX_PERMUTATION_SAMPLES - len(prio))]
                compute_indices = np.array(list(prio) + extra, dtype=int)
            else:
                compute_indices = np.arange(min(MAX_PERMUTATION_SAMPLES, n_total), dtype=int)
            n_compute = len(compute_indices)
            if n_total > MAX_PERMUTATION_SAMPLES:
                logger.info(
                    f"  PermutationExplainer: capping to {n_compute}/{n_total} samples"
                )
            X_subset = X_scaled[compute_indices]

            n_feats = X_subset.shape[1]
            explainer = shap.PermutationExplainer(
                _proba_excellent, bg, max_evals=2 * n_feats + 1
            )
            result = explainer(X_subset)
            sv_subset = result.values
            if sv_subset.ndim == 1:
                sv_subset = sv_subset.reshape(n_compute, -1)

            # Place computed SHAP values at their original positions; zeros for uncomputed rows
            sv = np.zeros((n_total, sv_subset.shape[1]))
            sv[compute_indices] = sv_subset
            return sv

        except Exception as exc2:
            logger.warning(f"SHAP PermutationExplainer also failed: {exc2}")
            return None

    @staticmethod
    def _extract_excellent_slice(raw) -> np.ndarray:
        """Normalise shap output to (n_samples, n_features) for the Excellent class."""
        if isinstance(raw, list):
            idx = min(EXCELLENT_IDX, len(raw) - 1)
            return np.array(raw[idx])
        if isinstance(raw, np.ndarray) and raw.ndim == 3:
            return raw[:, :, min(EXCELLENT_IDX, raw.shape[2] - 1)]
        return np.array(raw)

    def format_shap_explanations(
        self, shap_values: np.ndarray, top_k: int = 3
    ) -> List[List[dict]]:
        """Convert SHAP matrix to per-candidate top-k explanations."""
        explanations = []
        for row in shap_values:
            top_idx = np.argsort(np.abs(row))[::-1][:top_k]
            explanations.append(
                [
                    {
                        "feature": self.feature_names[j],
                        "shap_value": round(float(row[j]), 4),
                        "direction": "positive" if row[j] >= 0 else "negative",
                    }
                    for j in top_idx
                ]
            )
        return explanations

    # ------------------------------------------------------------------ private

    def _build_training_data(
        self,
        X_current: pd.DataFrame,
        y_current: pd.Series,
        historical_store,
        y_is_continuous: bool,
    ) -> Tuple[Optional[pd.DataFrame], Optional[np.ndarray]]:
        X_parts: List[pd.DataFrame] = []
        y_parts: List[np.ndarray] = []

        # Current session
        if y_is_continuous:
            y_tiers = self._continuous_to_tiers(y_current.values.astype(float))
        else:
            y_tiers = np.array(
                [TIER_LABELS.index(t) if t in TIER_LABELS else 1 for t in y_current.values]
            )
        X_parts.append(X_current[self.feature_names].copy())
        y_parts.append(y_tiers)

        # Historical sessions
        if historical_store is not None:
            X_hist, y_hist = historical_store.load_all()
            if X_hist is not None and y_hist is not None and len(X_hist) > 0:
                common = [c for c in self.feature_names if c in X_hist.columns]
                if common:
                    X_h = X_hist[common].copy()
                    for col in self.feature_names:
                        if col not in X_h.columns:
                            X_h[col] = 0.0
                    X_h = X_h[self.feature_names]
                    y_h = np.array(
                        [
                            TIER_LABELS.index(t) if t in TIER_LABELS else 1
                            for t in y_hist.values
                        ]
                    )
                    X_parts.append(X_h)
                    y_parts.append(y_h)
                    logger.info(f"  + {len(X_hist)} historical records")

        if not X_parts:
            return None, None

        X_all = pd.concat(X_parts, ignore_index=True)
        y_all = np.concatenate(y_parts)
        return X_all, y_all

    @staticmethod
    def _continuous_to_tiers(y: np.ndarray) -> np.ndarray:
        """Bin a continuous target into 4 equal-frequency tiers (quartiles)."""
        q25, q50, q75 = np.percentile(y, [25, 50, 75])
        tiers = np.zeros(len(y), dtype=int)
        tiers[y >= q25] = 1  # Moyen
        tiers[y >= q50] = 2  # Bon
        tiers[y >= q75] = 3  # Excellent
        return tiers

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
