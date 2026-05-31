"""Tests for TOPSIS (Technique for Order Preference by Similarity to Ideal Solution)"""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.topsis import TOPSIS


@pytest.fixture
def sample_data():
    return pd.DataFrame({
        'ID': ['A', 'B', 'C', 'D'],
        'Col1': [0.2, 0.5, 0.8, 0.9],
        'Col2': [0.3, 0.7, 0.4, 0.6],
        'Col3': [0.6, 0.4, 0.5, 0.7],
    })

@pytest.fixture
def criteria():
    return [
        {'name': 'C1', 'source_column': 'Col1', 'type': 'benefit'},
        {'name': 'C2', 'source_column': 'Col2', 'type': 'benefit'},
        {'name': 'C3', 'source_column': 'Col3', 'type': 'benefit'},
    ]

@pytest.fixture
def weights():
    return {'C1': 0.4, 'C2': 0.35, 'C3': 0.25}


class TestTOPSISBasic:
    def test_rank_returns_tuple(self, sample_data, weights, criteria):
        topsis = TOPSIS()
        result = topsis.rank(sample_data, weights, criteria)
        assert isinstance(result, tuple) and len(result) == 2

    def test_ranking_has_required_columns(self, sample_data, weights, criteria):
        topsis = TOPSIS()
        ranking, _ = topsis.rank(sample_data, weights, criteria)
        assert 'TOPSIS_Score' in ranking.columns
        assert 'TOPSIS_Rank' in ranking.columns

    def test_ranking_row_count(self, sample_data, weights, criteria):
        topsis = TOPSIS()
        ranking, _ = topsis.rank(sample_data, weights, criteria)
        assert len(ranking) == len(sample_data)

    def test_scores_in_range(self, sample_data, weights, criteria):
        topsis = TOPSIS()
        ranking, _ = topsis.rank(sample_data, weights, criteria)
        assert ranking['TOPSIS_Score'].between(0, 1).all()

    def test_ranking_in_descending_score_order(self, sample_data, weights, criteria):
        topsis = TOPSIS()
        ranking, _ = topsis.rank(sample_data, weights, criteria)
        sorted_r = ranking.sort_values('TOPSIS_Rank')
        scores = sorted_r['TOPSIS_Score'].values
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))

    def test_details_dict_has_required_keys(self, sample_data, weights, criteria):
        topsis = TOPSIS()
        _, details = topsis.rank(sample_data, weights, criteria)
        for key in ('pis', 'nis', 'weighted_matrix', 's_plus', 's_minus'):
            assert key in details

    def test_id_column_preserved(self, sample_data, weights, criteria):
        topsis = TOPSIS()
        ranking, _ = topsis.rank(sample_data, weights, criteria, id_column='ID')
        assert 'ID' in ranking.columns
        assert set(ranking['ID']) == set(sample_data['ID'])


class TestTOPSISIdealSolutions:
    def test_pis_length(self, sample_data, weights, criteria):
        topsis = TOPSIS()
        _, details = topsis.rank(sample_data, weights, criteria)
        assert len(details['pis']) == len(criteria)

    def test_nis_length(self, sample_data, weights, criteria):
        topsis = TOPSIS()
        _, details = topsis.rank(sample_data, weights, criteria)
        assert len(details['nis']) == len(criteria)

    def test_pis_geq_nis_for_benefit(self, sample_data, weights, criteria):
        topsis = TOPSIS()
        _, details = topsis.rank(sample_data, weights, criteria)
        for p, n in zip(details['pis'], details['nis']):
            assert p >= n

    def test_input_is_pre_oriented_higher_is_better(self):
        # TOPSIS no longer handles benefit/cost: DataProcessor pre-orients data so
        # that higher is always better. A cost criterion is therefore already
        # inverted upstream — here we pass the post-normalization values directly.
        # Raw cost [0.1, 0.5, 0.9] inverted by DataProcessor -> [1.0, 0.5, 0.0].
        topsis = TOPSIS()
        data = pd.DataFrame({
            'ID': ['A', 'B', 'C'],
            'Cost': [1.0, 0.5, 0.0],  # already inverted (A had the lowest raw cost)
        })
        criteria = [{'name': 'Cost', 'source_column': 'Cost'}]
        weights = {'Cost': 1.0}
        ranking, _ = topsis.rank(data, weights, criteria)
        # A (lowest raw cost -> highest oriented value) should rank #1
        assert ranking.iloc[0]['ID'] == 'A'

    def test_benefit_criterion_best_is_highest_value(self):
        topsis = TOPSIS()
        data = pd.DataFrame({
            'ID': ['A', 'B', 'C'],
            'Score': [0.1, 0.5, 0.9],
        })
        criteria = [{'name': 'Score', 'source_column': 'Score', 'type': 'benefit'}]
        weights = {'Score': 1.0}
        ranking, _ = topsis.rank(data, weights, criteria)
        assert ranking.iloc[0]['ID'] == 'C'


class TestTOPSISEquivalent:
    def test_identical_alternatives_same_score(self):
        topsis = TOPSIS()
        data = pd.DataFrame({
            'ID': ['A', 'B', 'A_copy'],
            'C1': [0.5, 0.7, 0.5],
            'C2': [0.6, 0.4, 0.6],
        })
        criteria = [
            {'name': 'C1', 'source_column': 'C1', 'type': 'benefit'},
            {'name': 'C2', 'source_column': 'C2', 'type': 'benefit'},
        ]
        weights = {'C1': 0.5, 'C2': 0.5}
        ranking, _ = topsis.rank(data, weights, criteria)
        score_a = ranking[ranking['ID'] == 'A']['TOPSIS_Score'].values[0]
        score_copy = ranking[ranking['ID'] == 'A_copy']['TOPSIS_Score'].values[0]
        assert abs(score_a - score_copy) < 1e-9

    def test_weighted_matrix_shape(self, sample_data, weights, criteria):
        topsis = TOPSIS()
        _, details = topsis.rank(sample_data, weights, criteria)
        wm = np.array(details['weighted_matrix'])
        assert wm.shape == (len(sample_data), len(criteria))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
