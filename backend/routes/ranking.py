"""
Ranking Route - Full pipeline: Upload → AHP → TOPSIS → ML (classification) → Hybrid Fusion
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Blueprint, current_app, jsonify, request

from core.ahp import AHP
from core.data_processor import DataProcessor
from core.file_reader import read_dataframe
from core.historical_store import HistoricalStore
from core.hybrid import HybridRanker
from core.ml_trainer import MLTrainer
from core.topsis import TOPSIS

bp = Blueprint("ranking", __name__, url_prefix="/api/ranking")
logger = logging.getLogger(__name__)


@bp.route("/process", methods=["POST"])
def process_data():
    """
    Full ranking pipeline.

    Expected JSON:
    {
        "filename": "data.csv",
        "config": {
            "data_source": {"id_column": "ID"},
            "criteria": [{"name": "...", "source_column": "...", "type": "benefit"|"cost"}],
            "ahp": {
                "enabled": true,
                "comparison_matrix": [[1, 2], [0.5, 1]],
                "weights": {"C1": 0.6, "C2": 0.4},
                "cr": 0.043
            },
            "machine_learning": {"enabled": true, "target_column": "Chance_of_Admit"},
            "hybrid": {"topsis_weight": 0.6, "ml_weight": 0.4}
        }
    }
    """
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "No JSON data provided"}), 400

        filename = payload.get("filename")
        config = payload.get("config", {})

        if not filename:
            return jsonify({"error": "Missing filename"}), 400

        filepath = Path(current_app.config["UPLOAD_FOLDER"]) / filename
        if not filepath.exists():
            return jsonify({"error": f"File not found: {filename}"}), 404

        criteria = config.get("criteria", [])
        if not criteria:
            return jsonify({"error": "No criteria configured"}), 400

        id_column = config.get("data_source", {}).get("id_column", "ID")
        missing_strategy = config.get("missing_strategy", "mean")
        col_names = [c.get("source_column", c.get("column", c["name"])) for c in criteria]

        # -- STEP 1: Load & normalize ------------------------------------------------
        logger.info("=== STEP 1: Data Processing ===")
        processor = DataProcessor()
        processor.load(str(filepath))
        normalized_df = processor.process(
            criteria, id_column=id_column, missing_strategy=missing_strategy
        )
        logger.info(f"  {len(normalized_df)} candidates, {len(criteria)} criteria")

        # -- STEP 2: AHP weights -----------------------------------------------------
        logger.info("=== STEP 2: AHP Weights ===")
        ahp_config = config.get("ahp", {})
        criteria_names = [c["name"] for c in criteria]
        comparison_matrix = ahp_config.get("comparison_matrix")
        ahp_weights = ahp_config.get("weights")

        if ahp_weights and isinstance(ahp_weights, dict):
            weights = ahp_weights
            cr = float(ahp_config.get("cr", 0.0))
            is_consistent = cr < 0.1
            logger.info(f"  Pre-calculated AHP weights: {weights}")
        elif comparison_matrix:
            ahp = AHP()
            ahp_result = ahp.calculate(comparison_matrix, criteria_names)
            weights = ahp_result["weights"]
            cr = ahp_result["consistency_ratio"]
            is_consistent = ahp_result["is_consistent"]
            logger.info(f"  AHP calculated: CR={cr:.4f}")
        else:
            ahp = AHP()
            ahp_result = ahp.equal_weights(criteria_names)
            weights = ahp_result["weights"]
            cr = 0.0
            is_consistent = True
            logger.info("  Equal weights (no matrix provided)")

        # -- STEP 3: TOPSIS ----------------------------------------------------------
        logger.info("=== STEP 3: TOPSIS Ranking ===")
        topsis = TOPSIS()
        topsis_df, topsis_details = topsis.rank(
            data=normalized_df,
            weights=weights,
            criteria=criteria,
            id_column=id_column,
        )
        logger.info(
            f"  TOPSIS scores: [{topsis_df['TOPSIS_Score'].min():.4f}, "
            f"{topsis_df['TOPSIS_Score'].max():.4f}]"
        )

        # -- STEP 4: ML Classification (optional) ------------------------------------
        logger.info("=== STEP 4: Machine Learning (Classification) ===")
        ml_config = config.get("machine_learning", {})
        target_column = ml_config.get("target_column")
        ml_info = {"enabled": False}
        proba_excellent = None
        predicted_tiers = None
        shap_values = None

        if ml_config.get("enabled", False) and target_column:
            if target_column in processor.raw_data.columns:
                X_ml = normalized_df[col_names]

                # Align target with normalized_df rows — critical when missing_strategy='exclude'
                # drops rows from normalized_df but raw_data still has all original rows.
                if id_column in processor.raw_data.columns and id_column in normalized_df.columns:
                    kept_ids = normalized_df[id_column].astype(str).values
                    mask = processor.raw_data[id_column].astype(str).isin(kept_ids)
                    target_series = processor.raw_data.loc[mask, target_column].reset_index(drop=True)
                else:
                    target_series = processor.raw_data[target_column].iloc[:len(normalized_df)].reset_index(drop=True)

                # Detect whether the target is numeric (continuous) or categorical (tier labels)
                is_numeric_target = pd.api.types.is_numeric_dtype(target_series)
                if is_numeric_target:
                    y_ml = target_series.astype(float)
                    y_is_continuous = True
                else:
                    y_ml = target_series.astype(str).str.strip()
                    y_is_continuous = False

                historical_store = HistoricalStore(
                    current_app.config["HISTORICAL_FOLDER"]
                )
                trainer = MLTrainer()
                ml_info = trainer.train(
                    X_ml, y_ml, historical_store=historical_store,
                    y_is_continuous=y_is_continuous
                )

                if ml_info.get("enabled"):
                    raw_tiers, raw_proba_exc, raw_proba_full = trainer.predict(X_ml)

                    # Reorder predictions to match topsis_df row order
                    if id_column in topsis_df.columns and id_column in normalized_df.columns:
                        id_to_idx = {
                            str(row[id_column]): i
                            for i, row in normalized_df.iterrows()
                        }
                        ordered_idx = [
                            id_to_idx[str(row[id_column])]
                            for _, row in topsis_df.iterrows()
                        ]
                        proba_excellent = raw_proba_exc[ordered_idx]
                        predicted_tiers = raw_tiers[ordered_idx]
                    else:
                        proba_excellent = raw_proba_exc
                        predicted_tiers = raw_tiers

                    # Identify top-candidate row indices in normalized_df order for SHAP priority
                    id_to_row = {
                        str(row[id_column]): i
                        for i, (_, row) in enumerate(normalized_df.iterrows())
                    }
                    top_ids = (
                        topsis_df.nlargest(15, "TOPSIS_Score")[id_column]
                        .astype(str).values
                    )
                    shap_priority = np.array(
                        [id_to_row[sid] for sid in top_ids if sid in id_to_row],
                        dtype=int,
                    )

                    # SHAP values (in normalized_df order)
                    shap_raw = trainer.compute_shap(X_ml, priority_indices=shap_priority)
                    if shap_raw is not None:
                        shap_explanations_by_id = {}
                        formatted = trainer.format_shap_explanations(shap_raw)
                        for pos, (_, row) in enumerate(normalized_df.iterrows()):
                            if pos < len(formatted):
                                # Normalise ID to int-string to avoid "1.0" vs "1" mismatches
                                raw_id = row[id_column]
                                try:
                                    key = str(int(float(raw_id)))
                                except (ValueError, TypeError):
                                    key = str(raw_id).strip()
                                shap_explanations_by_id[key] = formatted[pos]
                    else:
                        shap_explanations_by_id = {}

                    logger.info(f"  Best model: {ml_info.get('best_model_display')}")
            else:
                logger.warning(f"Target column '{target_column}' not found in data")
                ml_info = {
                    "enabled": False,
                    "reason": f"Column '{target_column}' not found",
                }
        else:
            shap_explanations_by_id = {}
            logger.info("  ML disabled (no target column specified)")

        # -- STEP 5: Hybrid Fusion ---------------------------------------------------
        logger.info("=== STEP 5: Hybrid Fusion ===")
        hybrid_config = config.get("hybrid", {})
        topsis_w = float(hybrid_config.get("topsis_weight", 0.6))
        ml_w = float(hybrid_config.get("ml_weight", 0.4))

        if not ml_info.get("enabled"):
            topsis_w, ml_w = 1.0, 0.0
            shap_explanations_by_id = {}

        ranker = HybridRanker(topsis_weight=topsis_w, ml_weight=ml_w)
        final_df = ranker.combine(topsis_df, proba_excellent, predicted_tiers)
        logger.info(
            f"  Final scores: [{final_df['Final_Score'].min():.4f}, "
            f"{final_df['Final_Score'].max():.4f}]"
        )

        # -- STEP 6: Merge criteria values for historical store ----------------------
        if id_column in final_df.columns and id_column in normalized_df.columns:
            criteria_cols = normalized_df[[id_column] + col_names].copy()
            final_df = final_df.merge(criteria_cols, on=id_column, how="left")

        # -- STEP 7: Save results ----------------------------------------------------
        result_dir = Path(current_app.config["RESULTS_FOLDER"])
        result_dir.mkdir(parents=True, exist_ok=True)
        result_id = filename.replace(".", "_").replace(" ", "_")
        result_file = result_dir / f"{result_id}.csv"
        final_df.to_csv(str(result_file), index=False)

        # -- STEP 8: Build response --------------------------------------------------
        top_n = 20
        top_df = (
            final_df.sort_values("Final_Score", ascending=False)
            .head(top_n)
            .replace({np.nan: None})
        )
        top_results = top_df.to_dict("records")

        # Attach SHAP explanation to each top candidate
        if shap_explanations_by_id:
            for row in top_results:
                raw_id = row.get(id_column, "")
                try:
                    candidate_id = str(int(float(raw_id)))
                except (ValueError, TypeError):
                    candidate_id = str(raw_id).strip()
                row["shap_explanation"] = shap_explanations_by_id.get(candidate_id, [])

        response = {
            "status": "success",
            "filename": filename,
            "result_id": result_id,
            "id_column": id_column,
            "statistics": {
                "total_candidates": len(final_df),
                "top_score": round(float(final_df["Final_Score"].max()), 6),
                "avg_score": round(float(final_df["Final_Score"].mean()), 6),
                "min_score": round(float(final_df["Final_Score"].min()), 6),
                "median_score": round(float(final_df["Final_Score"].median()), 6),
                "std_dev": round(float(final_df["Final_Score"].std()), 6),
                "weights": {k: round(v, 6) for k, v in weights.items()},
            },
            "ahp": {
                "consistency_ratio": round(cr, 6),
                "is_consistent": is_consistent,
                "weights": {k: round(v, 6) for k, v in weights.items()},
            },
            "topsis": {
                "score_range": [
                    round(float(topsis_df["TOPSIS_Score"].min()), 6),
                    round(float(topsis_df["TOPSIS_Score"].max()), 6),
                ]
            },
            "machine_learning": ml_info,
            "hybrid": {
                "topsis_weight": topsis_w,
                "ml_weight": ml_w,
                "ml_enabled": ml_info.get("enabled", False),
            },
            f"top_{top_n}": top_results,
        }

        return jsonify(response), 200

    except Exception as exc:
        logger.error(f"Processing error: {exc}", exc_info=True)
        return jsonify({"error": str(exc)}), 500


@bp.route("/criteria-suggestions/<filename>", methods=["GET"])
def get_criteria_suggestions(filename):
    """Analyse uploaded file and suggest criteria with detected types."""
    try:
        filepath = Path(current_app.config["UPLOAD_FOLDER"]) / filename
        if not filepath.exists():
            return jsonify({"error": "File not found"}), 404

        df = read_dataframe(str(filepath))

        id_column = "ID"
        suggestions = []
        categorical_columns = []
        potential_targets = []

        id_candidates = {
            "id", "student_id", "candidat_id", "reference", "ref", "name", "nom", "index"
        }

        for col in df.columns:
            col_stripped = col.strip()
            if col_stripped.lower() in id_candidates:
                id_column = col
                continue

            missing = int(df[col].isna().sum())

            if pd.api.types.is_numeric_dtype(df[col]):
                valid = df[col].dropna()
                if len(valid) == 0:
                    continue

                col_min = float(valid.min())
                col_max = float(valid.max())
                col_mean = float(valid.mean())

                if pd.isna(col_min) or pd.isna(col_max):
                    continue

                suggestions.append(
                    {
                        "name": col_stripped,
                        "display_name": col_stripped.replace("_", " ").title(),
                        "source_column": col,
                        "data_type": "numeric",
                        "type": "benefit",
                        "range": [round(col_min, 4), round(col_max, 4)],
                        "mean": round(col_mean, 4),
                        "missing": missing,
                    }
                )
                potential_targets.append(col)

            else:
                cleaned = (
                    df[col]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .str.replace("\xa0", "", regex=False)
                )
                cleaned = cleaned[cleaned != ""]
                unique_vals = sorted(cleaned.unique().tolist())
                if len(unique_vals) >= 2:
                    categorical_columns.append(
                        {
                            "name": col_stripped,
                            "display_name": col_stripped.replace("_", " ").title(),
                            "source_column": col,
                            "data_type": "categorical",
                            "type": "benefit",
                            "unique_values": unique_vals,
                            "missing": missing,
                        }
                    )
                    # Categorical columns with ≤ 10 unique values can serve as ML targets
                    if len(unique_vals) <= 10:
                        potential_targets.append(col)

        if suggestions:
            equal_w = round(1.0 / len(suggestions), 6)
            for s in suggestions:
                s["weight"] = equal_w

        return (
            jsonify(
                {
                    "filename": filename,
                    "id_column": id_column,
                    "suggested_criteria": suggestions,
                    "categorical_columns": categorical_columns,
                    "potential_target_columns": potential_targets,
                    "total_rows": len(df),
                }
            ),
            200,
        )

    except Exception as exc:
        logger.error(f"Error: {exc}")
        return jsonify({"error": str(exc)}), 500
