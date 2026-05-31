"""Tests for DataProcessor — base cleaning only (NO normalization)."""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_processor import DataProcessor


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        'ID': ['A', 'B', 'C'],
        'Score1': [50.0, 70.0, 90.0],
        'Score2': [30.0, 50.0, 80.0],
    })

@pytest.fixture
def criteria_benefit():
    return [
        {'name': 'Score1', 'source_column': 'Score1'},
        {'name': 'Score2', 'source_column': 'Score2'},
    ]


class TestDataProcessorBasic:
    def test_initialization(self):
        dp = DataProcessor()
        assert dp.raw_data is None
        assert dp.cleaned_data is None

    def test_load_csv(self, sample_df, tmp_path):
        csv_path = tmp_path / "test.csv"
        sample_df.to_csv(csv_path, index=False)
        dp = DataProcessor()
        result = dp.load(str(csv_path))
        assert len(result) == 3
        assert 'Score1' in result.columns

    def test_load_sets_raw_data(self, sample_df, tmp_path):
        csv_path = tmp_path / "test.csv"
        sample_df.to_csv(csv_path, index=False)
        dp = DataProcessor()
        dp.load(str(csv_path))
        assert dp.raw_data is not None

    def test_load_unsupported_format_raises(self, tmp_path):
        bad_file = tmp_path / "data.json"
        bad_file.write_text('{}')
        dp = DataProcessor()
        with pytest.raises(ValueError):
            dp.load(str(bad_file))

    def test_process_without_load_raises(self, criteria_benefit):
        dp = DataProcessor()
        with pytest.raises(ValueError):
            dp.process(criteria_benefit)

    def test_process_returns_dataframe(self, sample_df, criteria_benefit):
        dp = DataProcessor()
        dp.raw_data = sample_df
        result = dp.process(criteria_benefit, id_column='ID')
        assert isinstance(result, pd.DataFrame)

    def test_process_sets_cleaned_data(self, sample_df, criteria_benefit):
        dp = DataProcessor()
        dp.raw_data = sample_df
        dp.process(criteria_benefit, id_column='ID')
        assert dp.cleaned_data is not None

    def test_id_column_preserved(self, sample_df, criteria_benefit):
        dp = DataProcessor()
        dp.raw_data = sample_df
        result = dp.process(criteria_benefit, id_column='ID')
        assert 'ID' in result.columns
        assert list(result['ID']) == list(sample_df['ID'])

    def test_criteria_columns_in_output(self, sample_df, criteria_benefit):
        dp = DataProcessor()
        dp.raw_data = sample_df
        result = dp.process(criteria_benefit, id_column='ID')
        assert 'Score1' in result.columns
        assert 'Score2' in result.columns

    def test_missing_source_column_skipped(self, sample_df):
        dp = DataProcessor()
        dp.raw_data = sample_df
        criteria = [{'name': 'Ghost', 'source_column': 'NonExistent'}]
        result = dp.process(criteria, id_column='ID')
        assert 'NonExistent' not in result.columns


class TestNoNormalization:
    """Output must keep RAW values — normalization is delegated to TOPSIS / ML."""

    def test_values_are_raw_not_normalized(self, sample_df, criteria_benefit):
        dp = DataProcessor()
        dp.raw_data = sample_df
        result = dp.process(criteria_benefit, id_column='ID')
        # Raw values preserved exactly (no 0-1 scaling)
        assert list(result['Score1']) == [50.0, 70.0, 90.0]
        assert list(result['Score2']) == [30.0, 50.0, 80.0]

    def test_values_can_exceed_one(self):
        dp = DataProcessor()
        dp.raw_data = pd.DataFrame({'ID': ['A', 'B'], 'Score': [12.0, 18.0]})
        result = dp.process([{'name': 'Score', 'source_column': 'Score'}], id_column='ID')
        assert result['Score'].max() == 18.0  # not squashed to 1.0

    def test_ordinal_encoding_kept_raw(self):
        dp = DataProcessor()
        dp.raw_data = pd.DataFrame({
            'ID': ['A', 'B', 'C'],
            'Level': ['Low', 'Medium', 'High'],
        })
        criteria = [{
            'name': 'Level',
            'source_column': 'Level',
            'encoding': {'Low': 1, 'Medium': 2, 'High': 3},
        }]
        result = dp.process(criteria, id_column='ID')
        # Encoded to raw ordinal codes, NOT normalized
        assert list(result['Level']) == [1.0, 2.0, 3.0]


class TestMissingValues:
    def test_zero_imputation_fills_with_zero(self):
        dp = DataProcessor()
        dp.raw_data = pd.DataFrame({'ID': ['A', 'B', 'C'], 'Score': [10.0, np.nan, 30.0]})
        criteria = [{'name': 'Score', 'source_column': 'Score'}]
        result = dp.process(criteria, id_column='ID', missing_strategy='zero')
        assert result['Score'].isna().sum() == 0
        # The missing value is filled with exactly 0 (real, displayed value)
        assert result.loc[result['ID'] == 'B', 'Score'].iloc[0] == 0.0

    def test_mean_imputation_fills_with_mean(self):
        dp = DataProcessor()
        dp.raw_data = pd.DataFrame({'ID': ['A', 'B', 'C'], 'Score': [10.0, np.nan, 30.0]})
        criteria = [{'name': 'Score', 'source_column': 'Score'}]
        result = dp.process(criteria, id_column='ID', missing_strategy='mean')
        assert result['Score'].isna().sum() == 0
        assert result.loc[result['ID'] == 'B', 'Score'].iloc[0] == 20.0  # mean of 10,30

    def test_median_imputation_fills_with_median(self):
        dp = DataProcessor()
        dp.raw_data = pd.DataFrame({'ID': ['A', 'B', 'C', 'D'], 'Score': [10.0, np.nan, 30.0, 50.0]})
        criteria = [{'name': 'Score', 'source_column': 'Score'}]
        result = dp.process(criteria, id_column='ID', missing_strategy='median')
        assert result.loc[result['ID'] == 'B', 'Score'].iloc[0] == 30.0  # median of 10,30,50

    def test_no_candidate_is_ever_dropped(self):
        dp = DataProcessor()
        dp.raw_data = pd.DataFrame({'ID': ['A', 'B', 'C'], 'Score': [10.0, np.nan, 30.0]})
        criteria = [{'name': 'Score', 'source_column': 'Score'}]
        for strategy in ('mean', 'median', 'zero'):
            result = dp.process(criteria, id_column='ID', missing_strategy=strategy)
            assert len(result) == 3, f"strategy={strategy} dropped candidates"
            assert result['Score'].isna().sum() == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
