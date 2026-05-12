"""
Data Processor - Extract, encode, and normalize criteria data.

Handles:
- Numeric criteria: min-max normalization, benefit/cost direction
- Categorical criteria: ordinal encoding (user-defined mapping) then normalization
- Missing values: mean / median / zero imputation, or row exclusion
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DataProcessor:
    def __init__(self):
        self.raw_data: Optional[pd.DataFrame] = None
        self.normalized_data: Optional[pd.DataFrame] = None
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
        missing_strategy: str = "mean",
    ) -> pd.DataFrame:
        """
        Extract, encode, and normalize criteria columns.

        Args:
            criteria: list of criterion dicts:
                Numeric:      {"name", "source_column", "type": "benefit"|"cost"}
                Categorical:  {"name", "source_column", "type", "encoding": {"Low": 1, "High": 3}}
            id_column: name of the ID column
            missing_strategy: "mean" | "median" | "zero" | "exclude"

        Returns:
            DataFrame [id_column, crit1, crit2, ...] all normalized to [0, 1]
            where higher is always better (cost criteria are inverted).
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

        # --- Step 2: collect criterion column names and handle missing values ---
        crit_cols = []
        for crit in criteria:
            col = crit.get("source_column", crit.get("column", crit["name"]))
            if col in df.columns:
                crit_cols.append(col)

        # Convert all criterion columns to numeric first (handles string dtype from pandas 2.x)
        for col in crit_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        if missing_strategy == "exclude":
            before = len(df)
            df = df.dropna(subset=crit_cols)
            logger.info(f"  Excluded {before - len(df)} rows with missing values")
        else:
            for col in crit_cols:
                if df[col].isna().any():
                    if missing_strategy == "median":
                        fill_val = float(df[col].median())
                    elif missing_strategy == "zero":
                        fill_val = 0.0
                    else:  # mean (default)
                        fill_val = float(df[col].mean())
                    n_missing = df[col].isna().sum()
                    df[col] = df[col].fillna(fill_val)
                    logger.info(f"  Imputed {n_missing} missing in '{col}' with {missing_strategy}={fill_val:.4f}")

        # --- Step 3: normalize ---
        result = {}
        if id_column in df.columns:
            result[id_column] = df[id_column].values
        else:
            result[id_column] = range(1, len(df) + 1)

        for crit in criteria:
            source_col = crit.get("source_column", crit.get("column", crit["name"]))
            crit_type = crit.get("type", "benefit")

            if source_col not in df.columns:
                logger.warning(f"Column '{source_col}' not found in data — skipped")
                continue

            col_data = df[source_col].astype(float)
            col_min = col_data.min()
            col_max = col_data.max()

            if col_max == col_min:
                normalized = np.full(len(col_data), 0.5)
            elif crit_type == "cost":
                normalized = (col_max - col_data) / (col_max - col_min)
            else:
                normalized = (col_data - col_min) / (col_max - col_min)

            result[source_col] = np.asarray(normalized)

        self.normalized_data = pd.DataFrame(result)
        logger.info(f"Normalized {len(criteria)} criteria for {len(self.normalized_data)} candidates")
        return self.normalized_data
