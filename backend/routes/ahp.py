"""
AHP Route - Handle AHP pairwise comparison matrix and weight calculation
"""
from flask import Blueprint, request, jsonify
import logging
import numpy as np
from core.ahp import AHP

bp = Blueprint("ahp", __name__, url_prefix="/api/ahp")
logger = logging.getLogger(__name__)


@bp.route("/matrix/<int:n_criteria>", methods=["GET"])
def get_empty_matrix(n_criteria):
    """Return an identity comparison matrix template (all 1s)."""
    if not 2 <= n_criteria <= 15:
        return jsonify({"error": "Number of criteria must be between 2 and 15"}), 400

    # All 1s = equal importance (valid starting point)
    matrix = [[1.0 for _ in range(n_criteria)] for _ in range(n_criteria)]

    return jsonify({
        "n_criteria": n_criteria,
        "matrix": matrix,
        "instructions": (
            "Fill the upper triangle with values 1-9 (row criterion vs column criterion). "
            "1=equal, 3=moderate, 5=strong, 7=very strong, 9=extreme. "
            "Lower triangle is auto-filled as reciprocals."
        )
    }), 200


@bp.route("/weights", methods=["POST"])
def calculate_weights():
    """
    Calculate AHP weights from comparison matrix.
    Expected JSON: {"matrix": [[...], ...], "criteria": [{"name": ...}, ...]}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    matrix = data.get("matrix")
    criteria = data.get("criteria", [])
    criteria_names = [c.get("name", f"C{i+1}") for i, c in enumerate(criteria)] if criteria else None

    if not matrix:
        return jsonify({"error": "comparison matrix not provided"}), 400

    try:
        ahp = AHP(consistency_threshold=0.1)
        result = ahp.calculate(matrix, criteria_names)

        return jsonify({
            "status": "success",
            "weights": result["weights"],
            "cr": result["consistency_ratio"],
            "consistency_ratio": result["consistency_ratio"],
            "lambda_max": result["lambda_max"],
            "consistency_index": result["consistency_index"],
            "is_consistent": result["is_consistent"],
            "is_valid": result["is_consistent"],
            "normalized_matrix": result["normalized_matrix"],
            "message": (
                f"CR = {result['consistency_ratio']:.4f} — "
                + ("Valid (CR < 0.10)" if result["is_consistent"] else "Warning: CR >= 0.10, review comparisons")
            )
        }), 200

    except Exception as e:
        logger.error(f"AHP error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@bp.route("/validate-matrix", methods=["POST"])
def validate_matrix():
    """Validate reciprocal and positivity properties of comparison matrix."""
    data = request.get_json()
    matrix = data.get("matrix", [])
    n = len(matrix)
    issues = []

    for i in range(n):
        if len(matrix[i]) != n:
            issues.append(f"Row {i} has {len(matrix[i])} elements, expected {n}")
            continue
        for j in range(n):
            val = matrix[i][j]
            if val <= 0:
                issues.append(f"matrix[{i},{j}] = {val} is not positive")
            if i == j and abs(val - 1.0) > 0.01:
                issues.append(f"Diagonal matrix[{i},{i}] should be 1, got {val}")
            if i != j:
                recip = matrix[j][i]
                if abs(val * recip - 1.0) > 0.05:
                    issues.append(f"Reciprocal violated: [{i},{j}]={val}, [{j},{i}]={recip}")

    return jsonify({
        "is_valid": len(issues) == 0,
        "issues": issues,
        "message": "Valid" if not issues else f"{len(issues)} issue(s) found"
    }), 200
