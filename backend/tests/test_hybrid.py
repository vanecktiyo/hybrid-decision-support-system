"""Tests for HybridRanker"""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.hybrid import HybridRanker


@pytest.fixture
def topsis_result():
    return pd.DataFrame({
        'ID': ['A', 'B', 'C', 'D'],
        'TOPSIS_Score': [0.3, 0.7, 0.5, 0.9],
    })

@pytest.fixture
def ml_predictions():
    return np.array([0.4, 0.6, 0.8, 0.7])


class TestHybridRankerBasic:
    def test_initialization_defaults(self):
        hr = HybridRanker()
        assert hr.topsis_weight == 0.6
        assert hr.ml_weight == 0.4

    def test_initialization_custom_weights(self):
        hr = HybridRanker(topsis_weight=0.7, ml_weight=0.3)
        assert hr.topsis_weight == 0.7
        assert hr.ml_weight == 0.3

    def test_weights_not_summing_to_one_raises(self):
        with pytest.raises(ValueError):
            HybridRanker(topsis_weight=0.5, ml_weight=0.6)

    def test_combine_without_ml_returns_topsis_scores(self, topsis_result):
        hr = HybridRanker()
        result = hr.combine(topsis_result)
        assert 'Final_Score' in result.columns
        assert 'Final_Rank' in result.columns
        pd.testing.assert_series_equal(
            result['Final_Score'].reset_index(drop=True),
            topsis_result['TOPSIS_Score'].reset_index(drop=True),
            check_names=False,
        )

    def test_combine_with_ml_has_required_columns(self, topsis_result, ml_predictions):
        hr = HybridRanker()
        result = hr.combine(topsis_result, ml_predictions)
        assert 'Final_Score' in result.columns
        assert 'Final_Rank' in result.columns
        assert 'ML_Score' in result.columns

    def test_combine_row_count_preserved(self, topsis_result, ml_predictions):
        hr = HybridRanker()
        result = hr.combine(topsis_result, ml_predictions)
        assert len(result) == len(topsis_result)

    def test_final_scores_in_range(self, topsis_result, ml_predictions):
        hr = HybridRanker()
        result = hr.combine(topsis_result, ml_predictions)
        assert result['Final_Score'].between(0, 1).all()

    def test_ranking_descending_order(self, topsis_result, ml_predictions):
        hr = HybridRanker()
        result = hr.combine(topsis_result, ml_predictions)
        sorted_r = result.sort_values('Final_Rank')
        scores = sorted_r['Final_Score'].values
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))

    def test_ml_score_normalized_in_range(self, topsis_result, ml_predictions):
        hr = HybridRanker()
        result = hr.combine(topsis_result, ml_predictions)
        assert result['ML_Score'].between(0, 1).all()


class TestWeightedFusion:
    def test_weighted_formula_applied(self, topsis_result, ml_predictions):
        hr = HybridRanker(topsis_weight=0.6, ml_weight=0.4)
        result = hr.combine(topsis_result, ml_predictions)
        # P(Excellent) is already in [0,1] — no normalization
        expected = np.round(0.6 * topsis_result['TOPSIS_Score'].values + 0.4 * ml_predictions, 6)
        np.testing.assert_array_almost_equal(
            result.sort_values('ID')['Final_Score'].values,
            expected,
            decimal=5,
        )

    def test_custom_weights_respected(self):
        df = pd.DataFrame({'ID': ['A', 'B'], 'TOPSIS_Score': [0.4, 0.8]})
        ml = np.array([0.3, 0.7])
        hr = HybridRanker(topsis_weight=0.8, ml_weight=0.2)
        result = hr.combine(df, ml)
        # P(Excellent) is already in [0,1] — no normalization
        expected = np.round(0.8 * df['TOPSIS_Score'].values + 0.2 * ml, 6)
        np.testing.assert_array_almost_equal(
            result.sort_values('ID')['Final_Score'].values,
            expected,
            decimal=5,
        )

    def test_equal_topsis_and_ml_weight(self):
        df = pd.DataFrame({
            'ID': ['A', 'B', 'C'],
            'TOPSIS_Score': [0.3, 0.7, 0.5],
        })
        ml = np.array([0.4, 0.6, 0.5])
        hr = HybridRanker(topsis_weight=0.5, ml_weight=0.5)
        result = hr.combine(df, ml)
        assert result['Final_Score'].between(0, 1).all()


class TestEdgeCases:
    def test_single_candidate_no_ml(self):
        df = pd.DataFrame({'ID': ['A'], 'TOPSIS_Score': [0.7]})
        hr = HybridRanker()
        result = hr.combine(df)
        assert len(result) == 1
        assert result['Final_Rank'].values[0] == 1

    def test_identical_topsis_scores_all_rank_one(self):
        df = pd.DataFrame({
            'ID': ['A', 'B', 'C'],
            'TOPSIS_Score': [0.5, 0.5, 0.5],
        })
        hr = HybridRanker()
        result = hr.combine(df)
        assert (result['Final_Rank'] == 1).all()

    def test_constant_ml_predictions_fallback(self):
        df = pd.DataFrame({'ID': ['A', 'B'], 'TOPSIS_Score': [0.3, 0.7]})
        ml = np.array([0.5, 0.5])  # constant P(Excellent)
        hr = HybridRanker()
        result = hr.combine(df, ml)
        assert result['Final_Score'].isna().sum() == 0

    def test_empty_ml_treated_as_no_ml(self, topsis_result):
        hr = HybridRanker()
        result = hr.combine(topsis_result, None)
        assert 'Final_Score' in result.columns
        pd.testing.assert_series_equal(
            result['Final_Score'].reset_index(drop=True),
            topsis_result['TOPSIS_Score'].reset_index(drop=True),
            check_names=False,
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
