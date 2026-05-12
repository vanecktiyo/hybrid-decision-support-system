"""
Utility to read CSV/Excel files with automatic encoding fallback.
Centralises file reading so all routes use the same logic.
"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

CSV_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]


def _promote_numeric_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Promote non-numeric columns whose values are >= 90% valid numeric strings
    (e.g. '0'/'1' stored as StringDtype) to float64.
    This normalises dtypes regardless of pandas version / CSV backend."""
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        # Normalise to plain Python strings first
        cleaned = (
            df[col].astype(str)
            .str.replace('\xa0', '', regex=False)
            .str.strip()
            .replace({'': np.nan, 'nan': np.nan, 'None': np.nan})
        )
        non_null_mask = cleaned.notna()
        non_null_count = int(non_null_mask.sum())
        if non_null_count == 0:
            continue
        coerced = pd.to_numeric(cleaned, errors='coerce')
        converted_count = int(coerced[non_null_mask].notna().sum())
        if converted_count / non_null_count >= 0.90:
            df[col] = coerced
            logger.info(f"  Promoted '{col}' from text to float64 ({converted_count}/{non_null_count} values)")
    return df


def read_dataframe(filepath: str) -> pd.DataFrame:
    """
    Read a CSV or Excel file into a DataFrame.
    For CSV: tries multiple encodings automatically.
    After reading, promotes string columns that contain numeric values to float64.
    Raises ValueError with a clear message if nothing works.
    """
    filepath = str(filepath)

    if filepath.lower().endswith(".csv"):
        for enc in CSV_ENCODINGS:
            try:
                df = pd.read_csv(filepath, encoding=enc)
                logger.info(f"Read CSV with encoding={enc}: {df.shape}")
                return _promote_numeric_strings(df)
            except UnicodeDecodeError:
                continue
            except Exception as e:
                raise ValueError(f"Cannot read CSV file: {e}") from e
        raise ValueError(
            "Impossible de lire le fichier CSV. "
            "Veuillez le sauvegarder en UTF-8 depuis Excel : "
            "Fichier → Enregistrer sous → CSV UTF-8."
        )

    if filepath.lower().endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(filepath)
            logger.info(f"Read Excel: {df.shape}")
            return _promote_numeric_strings(df)
        except Exception as e:
            raise ValueError(f"Cannot read Excel file: {e}") from e

    raise ValueError("Format non supporté. Utilisez CSV, XLSX ou XLS.")
