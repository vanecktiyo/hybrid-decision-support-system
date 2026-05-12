"""
AHP - Analytic Hierarchy Process
Column normalization method (Saaty, exact as in paper Vaneck DAGAR 2026)
Steps:
  1. col_sums = sum(A, axis=0)
  2. R = A / col_sums  (column normalization)
  3. w = mean(R, axis=1)  (row averages = priority weights)
  4. lambda_max = mean((A @ w) / w)
  5. CI = (lambda_max - n) / (n - 1)
  6. CR = CI / RI
"""
import numpy as np
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

RI_TABLE = {
    1: 0.00, 2: 0.00, 3: 0.58, 4: 0.90, 5: 1.12,
    6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49,
    11: 1.51, 12: 1.54, 13: 1.56, 14: 1.57, 15: 1.58
}


class AHP:
    def __init__(self, consistency_threshold: float = 0.1):
        self.consistency_threshold = consistency_threshold

    def calculate(self, matrix: list, criteria_names: Optional[List[str]] = None) -> Dict:
        """
        Calculate AHP weights from pairwise comparison matrix.
        Uses column normalization + row average (matches paper methodology).

        Args:
            matrix: n×n pairwise comparison matrix (Saaty scale 1-9)
            criteria_names: optional list of criterion names

        Returns:
            dict with weights, lambda_max, CI, CR, is_consistent, normalized_matrix
        """
        A = np.array(matrix, dtype=float)
        n = len(A)

        if A.shape != (n, n):
            raise ValueError(f"Matrix must be square, got {A.shape}")
        if n < 2:
            raise ValueError("Matrix must be at least 2×2")
        if criteria_names is None:
            criteria_names = [f"C{i+1}" for i in range(n)]
        if len(criteria_names) != n:
            raise ValueError(f"Expected {n} criteria names, got {len(criteria_names)}")

        # Step 1-2: Column normalization
        col_sums = A.sum(axis=0)
        R = A / col_sums

        # Step 3: Priority weights = row averages
        w = R.mean(axis=1)
        w = w / w.sum()  # ensure exact sum = 1

        # Step 4: λmax
        Aw = A @ w
        lambda_vec = Aw / w
        lambda_max = float(lambda_vec.mean())

        # Step 5-6: CI and CR
        ci = float((lambda_max - n) / (n - 1)) if n > 1 else 0.0
        ri = RI_TABLE.get(n, 1.58)
        cr = float(ci / ri) if ri > 0 else 0.0
        is_consistent = cr < self.consistency_threshold

        if not is_consistent:
            logger.warning(f"CR={cr:.4f} exceeds threshold {self.consistency_threshold}. Revise comparisons.")

        return {
            "weights": {name: float(wi) for name, wi in zip(criteria_names, w)},
            "lambda_max": lambda_max,
            "consistency_index": ci,
            "consistency_ratio": cr,
            "is_consistent": is_consistent,
            "normalized_matrix": R.tolist(),
            "criteria_names": criteria_names,
        }

    def equal_weights(self, criteria_names: List[str]) -> Dict:
        """Generate equal weights using identity comparison matrix."""
        n = len(criteria_names)
        matrix = np.ones((n, n)).tolist()
        return self.calculate(matrix, criteria_names)
