"""
Download Route - Download ranking results
"""

from flask import Blueprint, send_file, jsonify, current_app
from pathlib import Path
import logging

bp = Blueprint('download', __name__, url_prefix='/api/download')
logger = logging.getLogger(__name__)


@bp.route('/results/<result_id>', methods=['GET'])
def download_results(result_id):
    """
    Download ranking results as CSV
    """
    try:
        # Construct filepath
        result_dir = Path(current_app.config['RESULTS_FOLDER'])
        filepath = result_dir / f"{result_id}.csv"
        
        if not filepath.exists():
            return jsonify({'error': 'Result file not found'}), 404
        
        logger.info(f"Downloading: {result_id}.csv")
        
        return send_file(
            str(filepath),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"ranking_results_{result_id}.csv"
        ), 200
    
    except Exception as e:
        logger.error(f"Error downloading results: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/results/<result_id>/excel', methods=['GET'])
def download_results_excel(result_id):
    """
    Download ranking results as Excel
    """
    try:
        import pandas as pd
        
        result_dir = Path(current_app.config['RESULTS_FOLDER'])
        csv_path = result_dir / f"{result_id}.csv"
        
        if not csv_path.exists():
            return jsonify({'error': 'Result file not found'}), 404
        
        # Read CSV and convert to Excel
        df = pd.read_csv(str(csv_path))
        
        excel_path = result_dir / f"{result_id}.xlsx"
        df.to_excel(str(excel_path), index=False, sheet_name='Rankings')
        
        logger.info(f"Downloading: {result_id}.xlsx")
        
        return send_file(
            str(excel_path),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"ranking_results_{result_id}.xlsx"
        ), 200
    
    except Exception as e:
        logger.error(f"Error downloading Excel results: {str(e)}")
        return jsonify({'error': str(e)}), 500
