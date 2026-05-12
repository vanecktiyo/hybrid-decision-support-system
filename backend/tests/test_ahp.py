"""Tests for AHP (Analytic Hierarchy Process)"""
import pytest
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ahp import AHP


class TestAHPBasic:
    def test_initialization_default(self):
        ahp = AHP()
        assert ahp.consistency_threshold == 0.1

    def test_initialization_custom_threshold(self):
        ahp = AHP(consistency_threshold=0.05)
        assert ahp.consistency_threshold == 0.05

    def test_calculate_returns_dict(self):
        ahp = AHP()
        result = ahp.calculate([[1.0, 1.0], [1.0, 1.0]], ['C1', 'C2'])
        assert isinstance(result, dict)
        for key in ('weights', 'consistency_ratio', 'is_consistent', 'normalized_matrix', 'lambda_max'):
            assert key in result

    def test_auto_names_when_none(self):
        ahp = AHP()
        result = ahp.calculate([[1.0, 2.0], [0.5, 1.0]])
        assert 'C1' in result['weights']
        assert 'C2' in result['weights']

    def test_non_square_matrix_raises(self):
        ahp = AHP()
        with pytest.raises(ValueError):
            ahp.calculate([[1, 2, 3], [0.5, 1, 2]], ['C1', 'C2'])

    def test_single_criterion_raises(self):
        ahp = AHP()
        with pytest.raises(ValueError):
            ahp.calculate([[1]], ['C1'])

    def test_wrong_criteria_count_raises(self):
        ahp = AHP()
        with pytest.raises(ValueError):
            ahp.calculate([[1.0, 2.0], [0.5, 1.0]], ['C1', 'C2', 'C3'])


class TestAHPWeights:
    def test_weights_sum_to_one_equal_matrix(self):
        ahp = AHP()
        result = ahp.calculate([[1.0, 1.0], [1.0, 1.0]], ['A', 'B'])
        assert abs(sum(result['weights'].values()) - 1.0) < 1e-6

    def test_equal_matrix_gives_equal_weights(self):
        ahp = AHP()
        result = ahp.calculate([[1.0, 1.0], [1.0, 1.0]], ['A', 'B'])
        assert abs(result['weights']['A'] - result['weights']['B']) < 1e-6

    def test_weights_positive(self):
        ahp = AHP()
        result = ahp.calculate([[1.0, 3.0], [1/3, 1.0]], ['A', 'B'])
        for w in result['weights'].values():
            assert w > 0

    def test_weights_sum_to_one_asymmetric(self):
        ahp = AHP()
        matrix = [[1, 2, 4], [0.5, 1, 2], [0.25, 0.5, 1]]
        result = ahp.calculate(matrix, ['C1', 'C2', 'C3'])
        assert abs(sum(result['weights'].values()) - 1.0) < 1e-6

    def test_higher_preference_gives_higher_weight(self):
        ahp = AHP()
        # C1 preferred 9x over C2 → weight C1 >> C2
        result = ahp.calculate([[1.0, 9.0], [1/9, 1.0]], ['C1', 'C2'])
        assert result['weights']['C1'] > result['weights']['C2']

    def test_equal_weights_helper(self):
        ahp = AHP()
        result = ahp.equal_weights(['X', 'Y', 'Z'])
        assert abs(sum(result['weights'].values()) - 1.0) < 1e-6
        for w in result['weights'].values():
            assert abs(w - 1/3) < 1e-6


class TestConsistencyRatio:
    def test_cr_zero_for_two_criteria(self):
        ahp = AHP()
        result = ahp.calculate([[1.0, 1.0], [1.0, 1.0]], ['C1', 'C2'])
        assert result['consistency_ratio'] == 0.0

    def test_cr_in_valid_range(self):
        ahp = AHP()
        matrix = [[1, 2, 4], [0.5, 1, 2], [0.25, 0.5, 1]]
        result = ahp.calculate(matrix, ['C1', 'C2', 'C3'])
        assert 0 <= result['consistency_ratio'] <= 1

    def test_perfectly_consistent_matrix(self):
        ahp = AHP()
        # Perfectly consistent: a12=2, a13=4, a23=2
        matrix = [[1, 2, 4], [0.5, 1, 2], [0.25, 0.5, 1]]
        result = ahp.calculate(matrix, ['C1', 'C2', 'C3'])
        assert result['is_consistent'] is True
        assert result['consistency_ratio'] < 0.01

    def test_inconsistent_matrix_detected(self):
        ahp = AHP()
        matrix = [[1.0, 0.2, 0.5], [5.0, 1.0, 0.1], [2.0, 10.0, 1.0]]
        result = ahp.calculate(matrix, ['C1', 'C2', 'C3'])
        assert result['consistency_ratio'] > 0.1
        assert result['is_consistent'] is False

    def test_custom_threshold(self):
        ahp = AHP(consistency_threshold=0.05)
        # Slightly inconsistent matrix — consistent with 0.1 but not 0.05
        matrix = [[1, 2, 4], [0.5, 1, 3], [0.25, 0.33, 1]]
        result = ahp.calculate(matrix, ['C1', 'C2', 'C3'])
        # is_consistent depends on threshold
        assert result['is_consistent'] == (result['consistency_ratio'] < 0.05)

    def test_5x5_matrix(self):
        ahp = AHP()
        matrix = [
            [1,   9,   9,   9,   9  ],
            [1/9, 1,   1,   1,   1  ],
            [1/9, 1,   1,   1,   1  ],
            [1/9, 1,   1,   1,   1  ],
            [1/9, 1,   1,   1,   1  ],
        ]
        result = ahp.calculate(matrix, ['A', 'B', 'C', 'D', 'E'])
        assert 0 <= result['consistency_ratio'] <= 1
        assert abs(sum(result['weights'].values()) - 1.0) < 1e-6


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
