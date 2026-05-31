"""
TOPSIS - Technique for Order Preference by Similarity to Ideal Solution
Formula (from paper Vaneck DAGAR 2026):
  V matrix: vij = (wj * xij) / sqrt(sum(xij^2))
  PIS: v+j = max(vij)   NIS: v-j = min(vij)   (for every criterion)
  S+i = sqrt(sum((vij - v+j)^2))
  S-i = sqrt(sum((vij - v-j)^2))
  Ci = S-i / (S+i + S-i)
  Rank by descending Ci

NOTE: all criteria are benefit (higher = better), so PIS is the per-column max
and NIS the per-column min. Input is RAW (DataProcessor no longer normalizes);
TOPSIS does its own vector normalization, which is scale-invariant per column.
"""
import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class TOPSIS:
    def rank(
        self,
        data: pd.DataFrame,
        weights: Dict[str, float],
        criteria: List[Dict],
        id_column: str = "ID"
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Rank alternatives using TOPSIS.

        Args:
            data: DataFrame with RAW (non-normalized) criteria values. TOPSIS
                  applies its own vector normalization internally. All criteria
                  are benefit (higher = better), so PIS=max / NIS=min per column.
            weights: {criterion_name: weight}
            criteria: list of {"name": str, "source_column": str}
            id_column: name of the ID column

        Returns:
            Tuple (ranking_df, details_dict)
        """
        col_names = [c.get("source_column", c.get("column", c["name"])) for c in criteria]
        crit_names = [c["name"] for c in criteria]

        n_alt = len(data)
        n_crit = len(criteria)

        # Decision matrix X — RAW criterion values (DataProcessor no longer
        # normalizes). TOPSIS applies its own vector normalization below, so raw
        # input is correct: vector norm is scale-invariant per column.
        X = data[col_names].values.astype(float)

        # Weighted normalized matrix V: vij = (wj * xij) / sqrt(sum(xij^2))
        V = np.zeros((n_alt, n_crit))
        for j in range(n_crit):
            col = X[:, j]
            denom = np.sqrt(np.sum(col ** 2))
            w = weights.get(crit_names[j], 1.0 / n_crit)
            V[:, j] = (w * col) / (denom if denom > 0 else 1.0)

        # Ideal solutions — input is pre-oriented (higher = better) for every
        # criterion, so PIS is always the column max and NIS the column min.
        pis = V.max(axis=0)
        nis = V.min(axis=0)

        # Euclidean distances
        s_plus = np.sqrt(np.sum((V - pis) ** 2, axis=1))
        s_minus = np.sqrt(np.sum((V - nis) ** 2, axis=1))

        # Closeness coefficient
        denom = s_plus + s_minus
        ci = np.divide(s_minus, denom, where=denom > 0, out=np.zeros(n_alt))

        # Build ranking DataFrame
        if id_column in data.columns:
            ranking = data[[id_column]].copy()
        else:
            ranking = pd.DataFrame({"ID": range(1, n_alt + 1)})

        ranking["TOPSIS_Score"] = ci
        ranking["TOPSIS_Rank"] = ranking["TOPSIS_Score"].rank(ascending=False, method="min").astype(int)
        ranking = ranking.sort_values("TOPSIS_Rank").reset_index(drop=True)

        details = {
            "weighted_matrix": V.tolist(),
            "pis": pis.tolist(),
            "nis": nis.tolist(),
            "s_plus": s_plus.tolist(),
            "s_minus": s_minus.tolist(),
        }

        return ranking, details
