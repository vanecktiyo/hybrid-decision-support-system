"""
Data Processor - Base cleaning of criteria data (NO normalization).

Single responsibility: turn the raw uploaded file into a clean numeric matrix.
Normalization is intentionally NOT done here — each consumer normalizes on its
own terms:
  - TOPSIS normalizes over the whole (closed) candidate set (vector norm).
  - The ML module normalizes INSIDE a per-fold Pipeline to avoid data leakage.

Handles:
- Numeric criteria: numeric coercion
- Categorical criteria: ordinal encoding (user-defined mapping)
- Missing values: mean / median / zero imputation (no candidate is ever dropped)

All criteria are treated as 'benefit' (higher = better); there are no cost criteria.
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DataProcessor:
    def __init__(self):
        self.raw_data: Optional[pd.DataFrame] = None
        self.cleaned_data: Optional[pd.DataFrame] = None
        self.id_column: str = "ID"
        self.criteria: List[Dict] = []

    def load(self, filepath: str) -> pd.DataFrame:
        from core.file_reader import read_dataframe
        self.raw_data = read_dataframe(filepath)
        logger.info(f"Loaded {len(self.raw_data)} rows, {len(self.raw_data.columns)} columns")
        return self.raw_data

    def process(
        self,
        criteria: List[Dict],
        id_column: str = "ID",
        missing_strategy: str = "zero",
    ) -> pd.DataFrame:
        """
        Extract, encode and clean criteria columns. Does NOT normalize.

        Args:
            criteria: list of criterion dicts:
                Numeric:      {"name", "source_column"}
                Categorical:  {"name", "source_column", "encoding": {"Low": 1, "High": 3}}
            id_column: name of the ID column
            missing_strategy: "zero" (default) | "mean" | "median"
                - zero: missing -> 0 (a real, displayed value chosen by the user;
                  since all criteria are benefit, 0 = lowest = penalised). 0 is a
                  constant, so it introduces no leakage even if applied upstream.
                - mean/median: impute with the column statistic.
                No candidate is ever dropped — every candidate must be ranked.

        Returns:
            DataFrame [id_column, crit1, crit2, ...] with RAW (non-normalized)
            values, missing entries filled per `missing_strategy`.
        """
        if self.raw_data is None:
            raise ValueError("No data loaded. Call load() first.")

        self.id_column = id_column
        self.criteria = criteria

        df = self.raw_data.copy()

        # --- Step 1: ordinal encoding for categorical criteria ---
        for crit in criteria:
            source_col = crit.get("source_column", crit.get("column", crit["name"]))
            encoding = crit.get("encoding")
            if encoding and source_col in df.columns:
                df[source_col] = df[source_col].map(encoding)
                logger.info(f"  Encoded '{source_col}' with mapping {encoding}")

        # --- Step 2: collect criterion columns and coerce to numeric ---
        crit_cols = []
        for crit in criteria:
            col = crit.get("source_column", crit.get("column", crit["name"]))
            if col in df.columns:
                crit_cols.append(col)

        for col in crit_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # --- Step 3: fill missing values (no row is ever dropped) ---
        for col in crit_cols:
            if not df[col].isna().any():
                continue
            n_missing = int(df[col].isna().sum())
            if missing_strategy == "median":
                fill_val = float(df[col].median())
            elif missing_strategy == "mean":
                fill_val = float(df[col].mean())
            else:  # "zero" (default) — constant fill, displayed as-is
                fill_val = 0.0
            df[col] = df[col].fillna(fill_val)
            logger.info(f"  Imputed {n_missing} missing in '{col}' with {missing_strategy}={fill_val:.4f}")

        # --- Step 4: assemble cleaned (raw, non-normalized) output ---
        result = {}
        if id_column in df.columns:
            result[id_column] = df[id_column].values
        else:
            result[id_column] = range(1, len(df) + 1)

        for crit in criteria:
            source_col = crit.get("source_column", crit.get("column", crit["name"]))
            if source_col not in df.columns:
                logger.warning(f"Column '{source_col}' not found in data — skipped")
                continue
            result[source_col] = df[source_col].astype(float).values

        self.cleaned_data = pd.DataFrame(result)
        logger.info(f"Cleaned {len(crit_cols)} criteria for {len(self.cleaned_data)} candidates (no normalization)")
        return self.cleaned_data
