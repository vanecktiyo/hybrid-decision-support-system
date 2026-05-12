"""Tests for DataProcessor"""
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
        {'name': 'Score1', 'source_column': 'Score1', 'type': 'benefit'},
        {'name': 'Score2', 'source_column': 'Score2', 'type': 'benefit'},
    ]


class TestDataProcessorBasic:
    def test_initialization(self):
        dp = DataProcessor()
        assert dp.raw_data is None
        assert dp.normalized_data is None

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

    def test_process_sets_normalized_data(self, sample_df, criteria_benefit):
        dp = DataProcessor()
        dp.raw_data = sample_df
        dp.process(criteria_benefit, id_column='ID')
        assert dp.normalized_data is not None

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
        criteria = [{'name': 'Ghost', 'source_column': 'NonExistent', 'type': 'benefit'}]
        result = dp.process(criteria, id_column='ID')
        assert 'NonExistent' not in result.columns


class TestDataNormalization:
    def test_benefit_range_zero_to_one(self, sample_df, criteria_benefit):
        dp = DataProcessor()
        dp.raw_data = sample_df
        result = dp.process(criteria_benefit, id_column='ID')
        for col in ['Score1', 'Score2']:
            assert result[col].between(0, 1).all()
            assert abs(result[col].min() - 0.0) < 1e-9
            assert abs(result[col].max() - 1.0) < 1e-9

    def test_cost_direction_inverts(self):
        dp = DataProcessor()
        dp.raw_data = pd.DataFrame({
            'ID': ['A', 'B', 'C'],
            'Cost': [10.0, 20.0, 30.0],
        })
        criteria = [{'name': 'Cost', 'source_column': 'Cost', 'type': 'cost'}]
        result = dp.process(criteria, id_column='ID')
        # Lowest cost (A=10) → normalized 1.0; highest (C=30) → 0.0
        idx_a = result[result['ID'] == 'A'].index[0]
        idx_c = result[result['ID'] == 'C'].index[0]
        assert abs(result.loc[idx_a, 'Cost'] - 1.0) < 1e-9
        assert abs(result.loc[idx_c, 'Cost'] - 0.0) < 1e-9

    def test_constant_column_gives_half(self):
        dp = DataProcessor()
        dp.raw_data = pd.DataFrame({
            'ID': ['A', 'B', 'C'],
            'Flat': [5.0, 5.0, 5.0],
        })
        criteria = [{'name': 'Flat', 'source_column': 'Flat', 'type': 'benefit'}]
        result = dp.process(criteria, id_column='ID')
        assert (result['Flat'] == 0.5).all()

    def test_ordinal_encoding_then_normalized(self):
        dp = DataProcessor()
        dp.raw_data = pd.DataFrame({
            'ID': ['A', 'B', 'C'],
            'Level': ['Low', 'Medium', 'High'],
        })
        criteria = [{
            'name': 'Level',
            'source_column': 'Level',
            'type': 'benefit',
            'encoding': {'Low': 1, 'Medium': 2, 'High': 3},
        }]
        result = dp.process(criteria, id_column='ID')
        assert result['Level'].between(0, 1).all()
        # High (3) → 1.0 ; Low (1) → 0.0
        idx_high = result[result['ID'] == 'C'].index[0]
        idx_low = result[result['ID'] == 'A'].index[0]
        assert abs(result.loc[idx_high, 'Level'] - 1.0) < 1e-9
        assert abs(result.loc[idx_low, 'Level'] - 0.0) < 1e-9


class TestMissingValues:
    def test_mean_imputation_no_nans(self):
        dp = DataProcessor()
        dp.raw_data = pd.DataFrame({
            'ID': ['A', 'B', 'C'],
            'Score': [10.0, np.nan, 30.0],
        })
        criteria = [{'name': 'Score', 'source_column': 'Score', 'type': 'benefit'}]
        result = dp.process(criteria, id_column='ID', missing_strategy='mean')
        assert result['Score'].isna().sum() == 0

    def test_zero_imputation_no_nans(self):
        dp = DataProcessor()
        dp.raw_data = pd.DataFrame({
            'ID': ['A', 'B', 'C'],
            'Score': [10.0, np.nan, 30.0],
        })
        criteria = [{'name': 'Score', 'source_column': 'Score', 'type': 'benefit'}]
        result = dp.process(criteria, id_column='ID', missing_strategy='zero')
        assert result['Score'].isna().sum() == 0

    def test_exclude_removes_rows_with_missing(self):
        dp = DataProcessor()
        dp.raw_data = pd.DataFrame({
            'ID': ['A', 'B', 'C'],
            'Score': [10.0, np.nan, 30.0],
        })
        criteria = [{'name': 'Score', 'source_column': 'Score', 'type': 'benefit'}]
        result = dp.process(criteria, id_column='ID', missing_strategy='exclude')
        assert len(result) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
