"""
Hybrid Ranker - Combine TOPSIS and ML classification scores.
Formula: FinalScore_i = alpha * Ci + (1 - alpha) * P(Excellent)_i
  Ci             = TOPSIS closeness coefficient (in [0,1])
  P(Excellent)_i = classifier probability of Excellent tier (in [0,1])
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TIER_LABELS = ["Faible", "Moyen", "Bon", "Excellent"]


class HybridRanker:
    def __init__(self, topsis_weight: float = 0.6, ml_weight: float = 0.4):
        if abs(topsis_weight + ml_weight - 1.0) > 0.01:
            raise ValueError("topsis_weight + ml_weight must equal 1.0")
        self.topsis_weight = topsis_weight
        self.ml_weight = ml_weight

    def combine(
        self,
        topsis_df: pd.DataFrame,
        ml_proba_excellent: np.ndarray = None,
        ml_predicted_tiers: np.ndarray = None,
    ) -> pd.DataFrame:
        """
        Merge TOPSIS scores with ML classification output.

        Args:
            topsis_df:          DataFrame with TOPSIS_Score and TOPSIS_Rank columns
            ml_proba_excellent: 1-D array of P(Excellent), already in [0,1]
            ml_predicted_tiers: 1-D int array (0-3) of predicted tier indices
        """
        result = topsis_df.copy()

        if ml_proba_excellent is None or len(ml_proba_excellent) == 0:
            result["Final_Score"] = result["TOPSIS_Score"]
            result["Final_Rank"] = (
                result["TOPSIS_Score"].rank(ascending=False, method="min").astype(int)
            )
            result["ML_Score"] = None
            result["Predicted_Tier"] = None
            return result

        # P(Excellent) is already in [0,1] — no normalisation needed
        result["ML_Score"] = np.round(ml_proba_excellent, 6)
        result["Final_Score"] = np.round(
            self.topsis_weight * result["TOPSIS_Score"].values
            + self.ml_weight * ml_proba_excellent,
            6,
        )
        result["Final_Rank"] = (
            result["Final_Score"].rank(ascending=False, method="min").astype(int)
        )

        if ml_predicted_tiers is not None:
            result["Predicted_Tier"] = [
                TIER_LABELS[int(t)] if 0 <= int(t) < 4 else "Moyen"
                for t in ml_predicted_tiers
            ]
        else:
            result["Predicted_Tier"] = None

        return result
