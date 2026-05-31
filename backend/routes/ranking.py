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
        missing_strategy = config.get("missing_strategy", "zero")  # align with UI default
        col_names = [c.get("source_column", c.get("column", c["name"])) for c in criteria]

        # -- STEP 1: Load & clean (no normalization here) ----------------------------
        logger.info("=== STEP 1: Data Processing ===")
        processor = DataProcessor()
        processor.load(str(filepath))
        cleaned_df = processor.process(
            criteria, id_column=id_column, missing_strategy=missing_strategy
        )
        logger.info(f"  {len(cleaned_df)} candidates, {len(criteria)} criteria")

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
            data=cleaned_df,
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

        trainer = None
        ordered_tier_labels = None
        if ml_config.get("enabled", False) and target_column:
            if target_column in processor.raw_data.columns:
                # Defensive copy: keep cleaned_df immutable so ML never affects
                # the DataFrame TOPSIS also reads from (single shared source).
                X_ml = cleaned_df[col_names].copy()

                # Align target with cleaned_df rows by ID (defensive: keeps the
                # target matched to the right candidates regardless of row order).
                if id_column in processor.raw_data.columns and id_column in cleaned_df.columns:
                    kept_ids = cleaned_df[id_column].astype(str).values
                    mask = processor.raw_data[id_column].astype(str).isin(kept_ids)
                    target_series = processor.raw_data.loc[mask, target_column].reset_index(drop=True)
                else:
                    target_series = processor.raw_data[target_column].iloc[:len(cleaned_df)].reset_index(drop=True)

                # Apply user-defined mapping to convert labels to integers
                target_mapping = ml_config.get("target_mapping", {})

                if pd.api.types.is_numeric_dtype(target_series) and not target_mapping:
                    logger.warning(f"Target '{target_column}' is numeric with no mapping. Skipping ML.")
                    ml_info = {
                        "enabled": False,
                        "reason": f"La colonne cible '{target_column}' est numérique. "
                                  "Définissez un mapping d'étiquettes à l'étape Critères."
                    }
                else:
                    labels = target_series.astype(str).str.strip()
                    if target_mapping:
                        int_mapping = {str(k): int(v) for k, v in target_mapping.items()}
                        y_ml = labels.map(int_mapping).fillna(0).astype(int)

                        # Normalize to 0-based indexing (handles 1-based user input)
                        int_to_label = {int(v): k for k, v in target_mapping.items()}
                        min_idx = min(int_to_label.keys())
                        if min_idx != 0:
                            int_to_label = {k - min_idx: v for k, v in int_to_label.items()}
                            y_ml = y_ml - min_idx
                        n_cls = max(int_to_label.keys()) + 1
                        ordered_tier_labels = [int_to_label[i] for i in range(n_cls) if i in int_to_label]
                        # Pad missing indices with closest label
                        if len(ordered_tier_labels) < n_cls:
                            ordered_tier_labels = [
                                int_to_label.get(i, ordered_tier_labels[-1] if ordered_tier_labels else "Inconnu")
                                for i in range(n_cls)
                            ]
                    else:
                        y_ml = labels
                        ordered_tier_labels = None

                    historical_store = HistoricalStore(
                        current_app.config["HISTORICAL_FOLDER"]
                    )
                    trainer = MLTrainer()
                    # Pass the same label ordering used to encode the current session
                    # so historical sessions are encoded on the SAME class scale.
                    # test_size is a fixed methodological choice (TEST_SIZE in ml_trainer).
                    ml_info = trainer.train(
                        X_ml, y_ml,
                        historical_store=historical_store,
                        tier_labels=ordered_tier_labels,
                    )

                if ml_info.get("enabled") and trainer is not None:
                    raw_tiers, raw_proba_exc, raw_proba_full = trainer.predict(X_ml)

                    # Reorder predictions to match topsis_df row order
                    if id_column in topsis_df.columns and id_column in cleaned_df.columns:
                        id_to_idx = {
                            str(row[id_column]): i
                            for i, row in cleaned_df.iterrows()
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

                    # SHAP values for all candidates
                    shap_raw = trainer.compute_shap(X_ml)
                    if shap_raw is not None:
                        shap_explanations_by_id = {}
                        formatted = trainer.format_shap_explanations(shap_raw)
                        for pos, (_, row) in enumerate(cleaned_df.iterrows()):
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

                    # Translate class_distribution keys from int indices to actual labels
                    if ordered_tier_labels and "class_distribution" in ml_info:
                        ml_info["class_distribution"] = {
                            ordered_tier_labels[int(k)] if int(k) < len(ordered_tier_labels) else k: v
                            for k, v in ml_info["class_distribution"].items()
                        }
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
        # Fusion weights are chosen per run via the UI slider (AHP step). The 0.6/0.4
        # fallback only applies to direct API calls that omit the hybrid block.
        logger.info("=== STEP 5: Hybrid Fusion ===")
        hybrid_config = config.get("hybrid", {})
        topsis_w = float(hybrid_config.get("topsis_weight", 0.6))
        ml_w = float(hybrid_config.get("ml_weight", 0.4))

        if not ml_info.get("enabled"):
            topsis_w, ml_w = 1.0, 0.0
            shap_explanations_by_id = {}

        ranker = HybridRanker(topsis_weight=topsis_w, ml_weight=ml_w)
        final_df = ranker.combine(topsis_df, proba_excellent, predicted_tiers,
                                  tier_labels=ordered_tier_labels if ml_info.get("enabled") else None)
        logger.info(
            f"  Final scores: [{final_df['Final_Score'].min():.4f}, "
            f"{final_df['Final_Score'].max():.4f}]"
        )

        # -- STEP 6: Merge criteria values for historical store ----------------------
        if id_column in final_df.columns and id_column in cleaned_df.columns:
            criteria_cols = cleaned_df[[id_column] + col_names].copy()
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

        # Build TOPSIS per-criterion contributions indexed by candidate ID
        topsis_contributions_by_id = {}
        if topsis_details and "weighted_matrix" in topsis_details:
            V = np.array(topsis_details["weighted_matrix"])          # (n_alt, n_crit)
            pis = np.array(topsis_details["pis"])                    # (n_crit,)
            nis = np.array(topsis_details["nis"])                    # (n_crit,)
            V_mean = V.mean(axis=0)
            V_range = np.where((pis - nis) != 0, pis - nis, 1.0)    # avoid /0

            for pos, (_, row_nd) in enumerate(cleaned_df.iterrows()):
                if pos >= len(V):
                    break
                raw_id = row_nd[id_column]
                try:
                    cid = str(int(float(raw_id)))
                except (ValueError, TypeError):
                    cid = str(raw_id).strip()

                contribs = []
                for j, crit in enumerate(criteria):
                    crit_name = crit.get("source_column", crit.get("column", crit["name"]))
                    # Relative position vs mean: positive = above average (better for benefit)
                    relative = float((V[pos, j] - V_mean[j]) / V_range[j])
                    crit_type = crit.get("type", "benefit")
                    direction = "positive" if (
                        (crit_type == "benefit" and relative >= 0) or
                        (crit_type == "cost" and relative <= 0)
                    ) else "negative"
                    contribs.append({
                        "feature": crit_name,
                        "contribution": round(relative, 6),
                        "weight": round(weights.get(crit["name"], 0.0), 4),
                        "direction": direction,
                    })
                # Sort by absolute contribution descending
                contribs.sort(key=lambda x: abs(x["contribution"]), reverse=True)
                topsis_contributions_by_id[cid] = contribs

        # Attach SHAP and TOPSIS explanations to each top candidate
        for row in top_results:
            raw_id = row.get(id_column, "")
            try:
                candidate_id = str(int(float(raw_id)))
            except (ValueError, TypeError):
                candidate_id = str(raw_id).strip()
            row["shap_explanation"] = shap_explanations_by_id.get(candidate_id, [])
            row["topsis_explanation"] = topsis_contributions_by_id.get(candidate_id, [])

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
                # Numeric columns are NOT valid ML targets — ML requires categorical labels

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
                        potential_targets.append({
                            "name": col,
                            "unique_values": unique_vals,
                        })

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
