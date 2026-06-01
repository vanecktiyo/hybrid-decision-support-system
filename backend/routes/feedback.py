"""
Feedback Route - Responsable de formation submits validated rankings.
These are stored as historical sessions used by MLTrainer for incremental learning.
"""
import json
import logging
import tempfile
import time
from pathlib import Path

import pandas as pd
from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from core.file_reader import read_dataframe
from core.historical_store import HistoricalStore

bp = Blueprint("feedback", __name__, url_prefix="/api/feedback")
logger = logging.getLogger(__name__)

SYSTEM_COLS = {
    "TOPSIS_Score", "TOPSIS_Rank", "ML_Score", "Final_Score",
    "Final_Rank", "Classe_predite", "Predicted_Tier", "Validated_Tier",
}

ALLOWED_EXT = (".csv", ".xlsx", ".xls")
MIN_CLASSES = 2   # ground-truth must have at least 2 distinct classes to be learnable


@bp.route("/submit", methods=["POST"])
def submit_feedback():
    """
    Submit a validated ranking file (CSV or Excel) for historical learning.

    Multipart form fields:
      - file       : CSV / XLSX / XLS file (required)
      - session_id : string identifier (optional, auto-generated if absent)
      - criteria   : JSON array of column names to use as ML features (optional)

    The file must contain a ground-truth label column: 'Validated_Tier'
    (preferred), else 'Classe_predite' / 'Predicted_Tier'. Labels are free-form:
    ANY class names are accepted as long as there are at least MIN_CLASSES
    distinct values (the system is no longer tied to Faible/Moyen/Bon/Excellent).
    """
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        fname = secure_filename(file.filename)
        if not fname.lower().endswith(ALLOWED_EXT):
            return jsonify(
                {"error": "Format non supporté. Utilisez un fichier CSV, XLSX ou XLS."}
            ), 400

        session_id = request.form.get(
            "session_id", f"session_{int(time.time())}"
        )
        criteria_json = request.form.get("criteria", "[]")

        try:
            criteria_cols = json.loads(criteria_json)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON in 'criteria' field"}), 400

        # Persist to a temp file then read via the shared CSV/Excel reader
        suffix = Path(fname).suffix
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name
            df = read_dataframe(tmp_path)
        except Exception as exc:
            return jsonify({"error": f"Impossible de lire le fichier : {exc}"}), 400
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

        # Identify the ground-truth label column
        if "Validated_Tier" in df.columns:
            tier_col = "Validated_Tier"
        elif "Classe_predite" in df.columns:
            tier_col = "Classe_predite"
        elif "Predicted_Tier" in df.columns:
            tier_col = "Predicted_Tier"
        else:
            return jsonify(
                {
                    "error": (
                        "Le fichier doit contenir une colonne de vérité terrain "
                        "'Validated_Tier' (ou 'Classe_predite' si vous ne l'avez pas renommée)."
                    )
                }
            ), 400

        # Free-form labels: keep rows with a non-empty label, require >= MIN_CLASSES.
        labels = df[tier_col].astype(str).str.strip()
        valid_mask = df[tier_col].notna() & (labels != "") & (labels.str.lower() != "nan")
        distinct = sorted(labels[valid_mask].unique().tolist())
        if len(distinct) < MIN_CLASSES:
            return jsonify(
                {
                    "error": (
                        f"La colonne '{tier_col}' doit contenir au moins {MIN_CLASSES} "
                        f"classes distinctes (trouvé : {distinct or 'aucune'})."
                    )
                }
            ), 400

        # Identify feature columns
        if criteria_cols:
            feature_cols = [c for c in criteria_cols if c in df.columns]
        else:
            id_col_candidates = {
                "id", "student_id", "candidat_id", "reference", "ref",
                "name", "nom", "index",
            }
            feature_cols = [
                c for c in df.columns
                if c not in SYSTEM_COLS
                and c.lower() not in id_col_candidates
                and pd.api.types.is_numeric_dtype(df[c])
            ]

        if not feature_cols:
            return jsonify(
                {"error": "Aucune colonne de critère numérique exploitable dans le fichier."}
            ), 400

        # Keep only rows that carry a label
        X = df.loc[valid_mask, feature_cols].reset_index(drop=True)
        y = labels[valid_mask].reset_index(drop=True)

        if len(X) < 4:
            return jsonify(
                {"error": f"Trop peu d'enregistrements valides ({len(X)}). Minimum 4 requis."}
            ), 400

        store = HistoricalStore(current_app.config["HISTORICAL_FOLDER"])
        store.save(X, y, session_id)

        tier_dist = y.value_counts().to_dict()
        logger.info(
            f"Feedback submitted: session={session_id}  "
            f"records={len(X)}  dist={tier_dist}"
        )

        return jsonify(
            {
                "status": "success",
                "session_id": session_id,
                "n_records": len(X),
                "features_saved": feature_cols,
                "tier_distribution": tier_dist,
                "message": (
                    f"{len(X)} enregistrements sauvegardés. "
                    "Le modèle ML utilisera ces données lors du prochain classement."
                ),
            }
        ), 200

    except Exception as exc:
        logger.error(f"Feedback error: {exc}", exc_info=True)
        return jsonify({"error": str(exc)}), 500


@bp.route("/history", methods=["GET"])
def get_history():
    """List all historical sessions stored."""
    try:
        store = HistoricalStore(current_app.config["HISTORICAL_FOLDER"])
        sessions = store.list_sessions()
        return jsonify(
            {
                "status": "success",
                "n_sessions": len(sessions),
                "total_records": store.total_records(),
                "sessions": sessions,
            }
        ), 200
    except Exception as exc:
        logger.error(f"History error: {exc}")
        return jsonify({"error": str(exc)}), 500


@bp.route("/history/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """Delete a historical session."""
    try:
        store = HistoricalStore(current_app.config["HISTORICAL_FOLDER"])
        deleted = store.delete_session(session_id)
        if deleted:
            return jsonify({"status": "success", "deleted": session_id}), 200
        return jsonify({"error": f"Session '{session_id}' not found"}), 404
    except Exception as exc:
        logger.error(f"Delete session error: {exc}")
        return jsonify({"error": str(exc)}), 500
