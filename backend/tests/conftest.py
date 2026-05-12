"""
Test fixtures and utilities
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path


@pytest.fixture
def sample_student_data():
    """Create sample student evaluation data"""
    return pd.DataFrame({
        'Student_ID': ['S001', 'S002', 'S003', 'S004', 'S005'],
        'Academic_Score': [85, 78, 92, 88, 75],
        'Certificate_Level': [3, 2, 4, 4, 1],
        'Event_Count': [5, 3, 8, 6, 2],
        'Test_Score': [92, 88, 96, 94, 82],
        'Participation_Rate': [0.95, 0.80, 1.00, 0.92, 0.65]
    })


@pytest.fixture
def config_student():
    """Create configuration for student evaluation"""
    return {
        'data_source': {
            'id_column': 'Student_ID'
        },
        'criteria': [
            {
                'name': 'Academic_Score',
                'source_column': 'Academic_Score',
                'type': 'numeric',
                'normalization': 'min_max',
                'range': [0, 100]
            },
            {
                'name': 'Certificate_Level',
                'source_column': 'Certificate_Level',
                'type': 'numeric',
                'normalization': 'min_max',
                'range': [1, 5]
            },
            {
                'name': 'Event_Count',
                'source_column': 'Event_Count',
                'type': 'numeric',
                'normalization': 'min_max',
                'range': [0, 20]
            },
            {
                'name': 'Test_Score',
                'source_column': 'Test_Score',
                'type': 'numeric',
                'normalization': 'min_max',
                'range': [0, 100]
            },
            {
                'name': 'Participation_Rate',
                'source_column': 'Participation_Rate',
                'type': 'numeric',
                'normalization': 'min_max',
                'range': [0, 1]
            }
        ],
        'ahp': {
            'consistency_threshold': 0.1
        },
        'hybrid': {
            'fusion_strategy': 'weighted',
            'topsis_weight': 0.6,
            'ml_weight': 0.4
        }
    }


@pytest.fixture
def ahp_matrix_5x5():
    """Create sample 5x5 AHP comparison matrix"""
    return [
        [1.0, 1.5, 1.2, 2.0, 3.0],      # Academic vs others
        [0.67, 1.0, 0.8, 1.5, 2.5],     # Certificate vs others
        [0.83, 1.25, 1.0, 1.8, 2.8],    # Event_Count vs others
        [0.5, 0.67, 0.56, 1.0, 2.0],    # Test_Score vs others
        [0.33, 0.4, 0.36, 0.5, 1.0]     # Participation vs others
    ]
