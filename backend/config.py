"""
Backend Configuration Module
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Flask Configuration
DEBUG = os.getenv('FLASK_DEBUG', True)
TESTING = os.getenv('FLASK_TESTING', False)

# File Upload Configuration
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
UPLOAD_FOLDER = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

# Create directories
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "results").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)

# CORS Configuration
CORS_ORIGINS = '*'

# Logging Configuration
LOG_FILE = str(BASE_DIR / 'logs' / 'app.log')
LOG_LEVEL = 'INFO'

# Algorithm Configuration
DEFAULT_COMPARISON_MATRIX = [
    [1.0, 1.4, 1.75, 1.75],
    [0.714, 1.0, 1.25, 1.25],
    [0.571, 0.8, 1.0, 1.0],
    [0.571, 0.8, 1.0, 1.0]
]

HYBRID_CONFIG = {
    'fusion_type': 'weighted',
    'weights': {
        'topsis': 0.6,
        'random_forest': 0.4
    }
}
