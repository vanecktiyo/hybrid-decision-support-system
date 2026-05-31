"""
AHP - Analytic Hierarchy Process
Principal eigenvector method (Saaty's exact priority derivation).
Steps:
  1. Solve A·w = lambda_max·w  (eigen-decomposition)
  2. w = principal eigenvector (largest real eigenvalue), normalized to sum 1
  3. lambda_max = largest real eigenvalue
  4. CI = (lambda_max - n) / (n - 1)
  5. CR = CI / RI

The eigenvector is Saaty's theoretically exact priority vector. For a perfectly
consistent matrix it coincides with the column-normalization (row-average)
approximation; for inconsistent matrices it is the recommended estimator.
The column-normalized matrix R is still returned for display/diagnostics.
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
    def __init__(self, consistency_threshold: Optional[float] = None):
        # Default consistency threshold comes from config.yaml (ahp.consistency_threshold),
        # falling back to the classic 0.1 if unset.
        if consistency_threshold is None:
            from core.config_manager import get_settings
            consistency_threshold = get_settings().ahp_consistency_threshold
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

        # Column-normalized matrix R — kept for display/diagnostics only
        col_sums = A.sum(axis=0)
        R = A / col_sums

        # Step 1-3: Priority weights = principal eigenvector of A
        eigenvalues, eigenvectors = np.linalg.eig(A)
        principal_idx = int(np.argmax(eigenvalues.real))
        lambda_max = float(eigenvalues[principal_idx].real)

        # Take the corresponding eigenvector, drop tiny imaginary parts, force sign,
        # and normalize to sum = 1 so the entries are interpretable as weights.
        w = np.abs(eigenvectors[:, principal_idx].real)  # principal eigenvector is sign-consistent
        w = w / w.sum()

        # Step 5-6: CI and CR
        # max(0, .) guards against tiny negative values (~ -1e-16) that the
        # eigenvector method can produce for a perfectly consistent matrix.
        ci = max(0.0, float((lambda_max - n) / (n - 1))) if n > 1 else 0.0
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
