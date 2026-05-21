"""
Data Preprocessing Pipeline
Handles data cleaning, validation, and transformation for generic candidate ranking
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any
import re

logger = logging.getLogger(__name__)


class DataPreprocessor:
    """
    Comprehensive data preprocessing for candidate ranking data
    Handles text→numbers conversion, missing values, outliers, normalization
    """
    
    def __init__(self, df: pd.DataFrame):
        """
        Initialize preprocessor with raw dataframe
        
        Args:
            df: Raw pandas DataFrame from CSV
        """
        self.original_df = df.copy()
        self.df = df.copy()
        self.validation_report = {
            'status': 'pending',
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'numeric_columns': [],
            'converted_columns': [],
            'missing_data': {},
            'outliers_detected': {},
            'critical_issues': [],
            'warnings': [],
            'errors': [],
            'quality_score': 0.0
        }
    
    def preprocess(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Execute full preprocessing pipeline

        Returns:
            Tuple of (cleaned_dataframe, validation_report)
        """
        try:
            logger.info("Starting preprocessing pipeline...")

            # Step 0: Clean non-breaking spaces and strip whitespace
            self._clean_whitespace()

            # Step 1: Detect and validate ID column
            self._validate_id_column()

            # Step 2: Detect numeric columns
            self._detect_columns()

            # Step 3: Convert text to numeric
            self._convert_text_to_numeric()

            # Step 4: Handle missing values
            self._handle_missing_values()

            # Step 5: Detect outliers
            self._detect_outliers()

            # Step 6: Calculate quality score
            self._calculate_quality_score()
            
            self.validation_report['status'] = 'success'
            logger.info(f"Preprocessing complete. Quality: {self.validation_report['quality_score']:.1%}")
            
            return self.df, self.validation_report
            
        except Exception as e:
            logger.error(f"Preprocessing failed: {str(e)}")
            self.validation_report['status'] = 'error'
            self.validation_report['errors'].append(str(e))
            raise
    
    def _clean_whitespace(self):
        """Replace non-breaking spaces and strip whitespace in all object columns.
        Then coerce columns whose non-null values are all numeric strings (e.g. '0'/'1')
        so they are recognised as native numeric by _detect_columns."""
        for col in self.df.columns:
            if not pd.api.types.is_numeric_dtype(self.df[col]):
                self.df[col] = (
                    self.df[col]
                    .astype(str)
                    .str.replace('\xa0', '', regex=False)
                    .str.strip()
                    .replace({'': np.nan, 'nan': np.nan})
                )
                # Promote columns whose values are mostly numeric strings (e.g. "0"/"1")
                # to float64. file_reader already does this on load, but run again here
                # because _clean_whitespace may have changed values (stripped \xa0, etc.).
                non_null_mask = self.df[col].notna()
                non_null_count = int(non_null_mask.sum())
                if non_null_count > 0:
                    coerced = pd.to_numeric(self.df[col], errors='coerce')
                    converted_count = int(coerced[non_null_mask].notna().sum())
                    if converted_count / non_null_count >= 0.90:
                        self.df[col] = coerced

    def _validate_id_column(self):
        """Validate and ensure ID column exists"""
        # Try common ID column names
        id_candidates = ['ID', 'id', 'Id', 'Référence', 'Reference', 'Ref']
        
        id_column = None
        for candidate in id_candidates:
            if candidate in self.df.columns:
                id_column = candidate
                break
        
        if id_column is None:
            logger.warning("No ID column found, creating default ID column")
            self.df.insert(0, 'ID', range(1, len(self.df) + 1))
            self.validation_report['critical_issues'].append(
                "Aucune colonne identifiant (ID) n'a été détectée dans le fichier. "
                "Ajoutez une colonne nommée 'ID' contenant un identifiant unique par candidat."
            )
        else:
            # Move ID column to first position
            if id_column != 'ID':
                self.df.rename(columns={id_column: 'ID'}, inplace=True)
            
            cols = self.df.columns.tolist()
            cols.remove('ID')
            self.df = self.df[['ID'] + cols]
            
            # Check for duplicate IDs
            if self.df['ID'].duplicated().any():
                logger.warning(f"Found {self.df['ID'].duplicated().sum()} duplicate IDs")
                self.validation_report['warnings'].append(
                    f"{self.df['ID'].duplicated().sum()} duplicate IDs found"
                )
    
    def _detect_columns(self):
        """Detect native numeric columns (consistent with criteria-suggestions endpoint).
        Text columns that could be converted are tracked separately in _convertible_columns."""
        numeric_cols = []    # natively numeric dtype
        convertible_cols = []  # text columns convertible to numeric

        for col in self.df.columns:
            if col == 'ID':
                continue
            if self.df[col].isna().all():
                continue

            if pd.api.types.is_numeric_dtype(self.df[col]):
                numeric_cols.append(col)
            elif self._can_convert_to_numeric(col):
                convertible_cols.append(col)

        # Report only native numeric (matches what step 3 shows as "numeric")
        self.validation_report['numeric_columns'] = numeric_cols
        # Internal list used by missing-value and outlier steps — grows after text conversion
        self._all_numeric_cols = list(numeric_cols)
        self._convertible_columns = convertible_cols
        logger.info(f"Detected {len(numeric_cols)} native numeric + {len(convertible_cols)} convertible text columns")

    def _can_convert_to_numeric(self, col: str) -> bool:
        """Check if a non-numeric text column can be parsed into floats."""
        sample = self.df[col].dropna().head(10)
        if len(sample) == 0:
            return False
        try:
            conversions = sample.apply(self._convert_value_to_float)
            return conversions.notna().sum() / len(conversions) > 0.5
        except:
            return False
    
    def _convert_value_to_float(self, value) -> float:
        """Convert individual value to float"""
        if pd.isna(value):
            return np.nan
        
        if isinstance(value, (int, float)):
            return float(value)
        
        value_str = str(value).strip().lower()
        
        # Boolean conversions
        if value_str in ['oui', 'yes', 'true', '1']:
            return 1.0
        if value_str in ['non', 'no', 'false', '0']:
            return 0.0
        
        # Range conversions (for "sup à 12", "inf à 12", etc.)
        if 'sup' in value_str or 'supérieur' in value_str or '>' in value_str:
            # Extract number if present, else use 12
            match = re.search(r'\d+\.?\d*', value_str)
            return float(match.group()) + 0.5 if match else 12.5
        
        if 'inf' in value_str or 'inférieur' in value_str or '<' in value_str:
            match = re.search(r'\d+\.?\d*', value_str)
            return float(match.group()) - 0.5 if match else 11.5
        
        # Try direct float conversion
        try:
            return float(value_str)
        except:
            return np.nan
    
    def _convert_text_to_numeric(self):
        """Convert convertible text columns to numeric.
        Converted columns are added to _all_numeric_cols (for pipeline use)
        but NOT to report['numeric_columns'] (report keeps native-only count)."""
        for col in getattr(self, '_convertible_columns', []):
            try:
                converted = self.df[col].apply(self._convert_value_to_float)
                if converted.notna().sum() / len(converted) > 0.5:
                    self.df[col] = converted
                    self.validation_report['converted_columns'].append(col)
                    self._all_numeric_cols.append(col)
                    logger.info(f"Converted column '{col}' to numeric")
            except Exception as e:
                logger.warning(f"Failed to convert column '{col}': {str(e)}")
                self.validation_report['warnings'].append(
                    f"Could not convert '{col}' to numeric"
                )
    
    def _handle_missing_values(self):
        """Handle missing values intelligently"""
        numeric_cols = getattr(self, '_all_numeric_cols', self.validation_report['numeric_columns'])
        
        missing_summary = {}
        
        for col in numeric_cols:
            missing_count = self.df[col].isna().sum()
            missing_pct = missing_count / len(self.df)
            
            if missing_count > 0:
                missing_summary[col] = {
                    'count': int(missing_count),
                    'percentage': float(missing_pct * 100)
                }
                
                # Fill missing values with median
                if missing_pct < 0.5:  # Only if < 50% missing
                    median_val = self.df[col].median()
                    self.df[col] = self.df[col].fillna(median_val)
                    logger.info(f"Filled {missing_count} missing values in '{col}' with median {median_val:.2f}")
                else:
                    # Too many missing, warn
                    self.validation_report['warnings'].append(
                        f"Column '{col}' has {missing_pct*100:.1f}% missing values - consider removing"
                    )
        
        self.validation_report['missing_data'] = missing_summary
    
    def _detect_outliers(self):
        """Detect outliers using IQR method"""
        numeric_cols = getattr(self, '_all_numeric_cols', self.validation_report['numeric_columns'])
        
        outliers_summary = {}
        
        for col in numeric_cols:
            try:
                # IQR method
                Q1 = self.df[col].quantile(0.25)
                Q3 = self.df[col].quantile(0.75)
                IQR = Q3 - Q1
                
                if IQR == 0:
                    # Binary or constant column — IQR method not applicable
                    continue

                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR

                outlier_mask = (self.df[col] < lower_bound) | (self.df[col] > upper_bound)
                outlier_count = outlier_mask.sum()
                
                if outlier_count > 0:
                    outlier_rows = self.df[outlier_mask]
                    id_col = 'ID' if 'ID' in self.df.columns else self.df.columns[0]
                    candidates = [
                        {'id': str(row[id_col]), 'value': round(float(row[col]), 4)}
                        for _, row in outlier_rows.iterrows()
                    ]
                    outliers_summary[col] = {
                        'count': int(outlier_count),
                        'lower_bound': float(lower_bound),
                        'upper_bound': float(upper_bound),
                        'candidates': candidates
                    }
                    
                    if outlier_count / len(self.df) > 0.05:  # More than 5%
                        self.validation_report['warnings'].append(
                            f"Column '{col}': {outlier_count} outliers detected (> 5% of data)"
                        )
            
            except Exception as e:
                logger.warning(f"Outlier detection failed for '{col}': {str(e)}")
        
        self.validation_report['outliers_detected'] = outliers_summary
    
    def _calculate_quality_score(self):
        """Calculate overall data quality score (0-100%).

        Missing penalty is graduated: high rates (>20%) indicate structural
        incompleteness (expected in real datasets), not data entry errors.
          0-5%  : 0.5 pts/% — likely entry errors, penalise harder
          5-20% : 0.2 pts/% — moderate, some missing expected
          >20%  : 0.05 pts/% — structural/optional fields, light penalty
        """
        score = 100.0

        # Critical issues: -40 pts each (blocking problems)
        score -= len(self.validation_report['critical_issues']) * 40

        for col, stats in self.validation_report['missing_data'].items():
            pct = stats['percentage']
            if pct <= 5:
                penalty = pct * 0.5
            elif pct <= 20:
                penalty = 5 * 0.5 + (pct - 5) * 0.2
            else:
                penalty = 5 * 0.5 + 15 * 0.2 + (pct - 20) * 0.05
            score -= penalty

        # Outliers: 0.1 pts per % — informational only
        for col, stats in self.validation_report['outliers_detected'].items():
            outlier_pct = (stats['count'] / self.validation_report['total_rows']) * 100
            score -= outlier_pct * 0.1

        # Warnings: 2 pts each
        score -= len(self.validation_report['warnings']) * 2

        self.validation_report['quality_score'] = max(0.0, min(100.0, score))
    
    def get_summary(self) -> Dict[str, Any]:
        """Get human-readable summary"""
        return {
            'status': self.validation_report['status'],
            'total_candidates': self.validation_report['total_rows'],
            'numeric_criteria': len(self.validation_report['numeric_columns']),
            'criteria_detected': self.validation_report['numeric_columns'],
            'converted': len(self.validation_report['converted_columns']),
            'missing_columns': len(self.validation_report['missing_data']),
            'outliers_detected': len(self.validation_report['outliers_detected']),
            'quality_score': f"{self.validation_report['quality_score']:.1f}%",
            'warnings': self.validation_report['warnings'],
            'errors': self.validation_report['errors']
        }


def preprocess_data(filepath: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Main entry point for data preprocessing.
    Supports CSV (auto-detect encoding) and Excel.
    """
    from core.file_reader import read_dataframe
    logger.info(f"Loading data from {filepath}")
    df = read_dataframe(filepath)
    preprocessor = DataPreprocessor(df)
    cleaned_df, report = preprocessor.preprocess()
    return cleaned_df, report
