"""
Upload Route - Handle file uploads
"""

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
import logging
from pathlib import Path
from core.data_preprocessor import preprocess_data
from core.file_reader import read_dataframe

bp = Blueprint('upload', __name__, url_prefix='/api/upload')
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route('/file', methods=['POST'])
def upload_file():
    """
    Upload a data file
    Expected: multipart form data with 'file' field
    Returns: File info and preview of data
    """
    try:
        # Check if file was provided
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
        
        # Save file
        filename = secure_filename(file.filename)
        upload_folder = Path(current_app.config['UPLOAD_FOLDER'])
        upload_folder.mkdir(parents=True, exist_ok=True)
        
        filepath = upload_folder / filename
        file.save(str(filepath))
        
        logger.info(f"File uploaded: {filename}")
        
        # Read file to get info
        df = read_dataframe(str(filepath))

        columns = df.columns.tolist()
        rows, cols = df.shape

        # Replace NaN/inf with None so jsonify produces valid JSON
        preview_df = df.head(5).replace({float('nan'): None, float('inf'): None, float('-inf'): None})
        preview = preview_df.to_dict(orient='records')

        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}

        response = {
            'filename': filename,
            'rows': rows,
            'columns': cols,
            'column_names': columns,
            'column_types': dtypes,
            'preview': preview
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/preview/<filename>', methods=['GET'])
def get_preview(filename):
    """Get preview of uploaded file"""
    try:
        filepath = Path(current_app.config['UPLOAD_FOLDER']) / secure_filename(filename)
        
        if not filepath.exists():
            return jsonify({'error': 'File not found'}), 404
        
        df = read_dataframe(str(filepath))
        preview_df = df.head(10).replace({float('nan'): None, float('inf'): None, float('-inf'): None})
        preview = preview_df.to_dict(orient='records')
        
        return jsonify({
            'filename': filename,
            'rows': len(df),
            'columns': df.columns.tolist(),
            'preview': preview
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting preview: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/validate/<filename>', methods=['POST'])
def validate_file(filename):
    """
    Validate and preprocess uploaded file
    Returns QA report with data quality metrics
    """
    try:
        filepath = Path(current_app.config['UPLOAD_FOLDER']) / secure_filename(filename)
        
        if not filepath.exists():
            return jsonify({'error': 'File not found'}), 404
        
        logger.info(f"Validating file: {filename}")
        
        # Run preprocessing pipeline
        cleaned_df, report = preprocess_data(str(filepath))
        
        # Save cleaned data temporarily
        cleaned_filepath = Path(current_app.config['UPLOAD_FOLDER']) / f"cleaned_{filename}"
        if filename.endswith('.csv'):
            cleaned_df.to_csv(str(cleaned_filepath), index=False)
        else:
            cleaned_df.to_excel(str(cleaned_filepath), index=False)
        
        # Build response
        recommendation = _get_recommendation(report)
        response = {
            'status': 'success',
            'filename': filename,
            'cleaned_filename': f"cleaned_{filename}",
            'validation_report': {
                'total_candidates': report['total_rows'],
                'total_criteria_detected': len(report['numeric_columns']),
                'criteria_names': report['numeric_columns'],
                'text_converted': report['converted_columns'],
                'missing_data_summary': report['missing_data'],
                'outliers_detected': report['outliers_detected'],
                'quality_score': report['quality_score'],
                'warnings': report['warnings'],
                'errors': report['errors'],
                'recommendation': recommendation
            }
        }
        
        logger.info(f"Validation complete. Quality: {report['quality_score']:.1f}%")
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Error validating file: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def _get_recommendation(report):
    """Generate recommendation based on quality score.
    Never returns action='fix' — users can always proceed after reviewing."""
    score = report['quality_score']

    if score >= 80:
        return {
            'level': 'good',
            'message': 'Qualité des données bonne. Vous pouvez continuer.',
            'action': 'continue'
        }
    elif score >= 60:
        return {
            'level': 'warning',
            'message': 'Qualité acceptable. Vérifiez les avertissements avant de continuer.',
            'action': 'review'
        }
    else:
        return {
            'level': 'warning',
            'message': f'Score de qualité : {score:.1f}%. Des valeurs manquantes ou des anomalies ont été détectées. '
                       'Vous pouvez continuer — les colonnes seront configurées à l\'étape suivante.',
            'action': 'review'
        }

