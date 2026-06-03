# Admission Ranking System

Generic hybrid decision support system for candidate ranking using a multi-criteria pipeline: **AHP → TOPSIS → ML classification → Hybrid Fusion**.

Built with Flask (backend) and React (frontend).

---

## Overview

This application allows any organization to rank candidates based on multiple criteria. It is not tied to a specific dataset — upload any CSV or Excel file and configure the criteria through the UI.

**Pipeline:**
1. **AHP** — compute criterion weights from pairwise comparisons (or use equal weights)
2. **TOPSIS** — rank candidates using weighted normalized distances (all criteria are benefit: higher = better)
3. **ML Classification** — classify candidates using the best cross-validated model among Random Forest, Gradient Boosting, Decision Tree, Logistic Regression, SVM (and XGBoost when available). The class labels come from the user's ground-truth column — **any label set with at least 2 classes** (the system is not tied to a fixed 4-tier scheme).
4. **Hybrid Fusion** — combine TOPSIS score (60%) and ML probability of the best class (40%) into a final score
5. **SHAP** — explain the top candidates' scores using feature-level contributions
6. **Feedback loop** — experts validate and correct predicted classes (CSV or Excel); validated data is stored and used to improve the ML model on future runs

A held-out test set (rows never seen during training) provides an honest performance estimate, reported separately from the cross-validation scores used for model selection.

---

## Project Structure

```
admission-ranking-system/
├── backend/
│   ├── app.py                  # Flask entry point
│   ├── core/
│   │   ├── ahp.py              # AHP weights + consistency ratio
│   │   ├── topsis.py           # TOPSIS ranking
│   │   ├── data_processor.py   # Base cleaning (encoding + missing values); no normalization
│   │   ├── ml_trainer.py       # ML training, SHAP, tier classification
│   │   ├── hybrid.py           # Hybrid fusion (TOPSIS + ML)
│   │   ├── historical_store.py # Persist validated tiers for incremental learning
│   │   └── file_reader.py      # CSV/Excel reader with encoding fallback
│   ├── routes/
│   │   ├── upload.py           # POST /api/upload
│   │   ├── ranking.py          # POST /api/ranking/process
│   │   ├── ahp.py              # POST /api/ahp/calculate
│   │   ├── feedback.py         # POST /api/feedback/submit
│   │   └── download.py         # GET  /api/download/:result_id
│   ├── tests/                  # Unit tests (pytest)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── LandingPage.js
│   │   │   ├── FileUploader.js
│   │   │   ├── QAReport.js
│   │   │   ├── CriteriaConfig.js
│   │   │   ├── AHPMatrix.js
│   │   │   ├── Dashboard.js        # Step orchestration
│   │   │   ├── ResultsViewer.js    # Results + SHAP explanations + test-set metrics
│   │   │   └── FeedbackModal.js    # Expert validation interface
│   │   └── services/api.js
│   └── package.json
├── data/
│   ├── input/                  # Input datasets (not versioned)
│   └── validation/             # Validation files (not versioned)
├── notebooks/
│   └── ml_module_validation.ipynb
├── docs/
│   └── resource/               # Reference papers (AHP, TOPSIS)
├── config.yaml                 # Example configuration
└── requirements.txt
```

---

## Installation

### Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

The API runs on `http://localhost:5000`.

### Frontend

```bash
cd frontend
npm install
npm start
```

The UI runs on `http://localhost:3000`.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload CSV or Excel file |
| GET | `/api/ranking/criteria-suggestions/<filename>` | Auto-detect criteria from file |
| POST | `/api/ahp/calculate` | Compute AHP weights from comparison matrix |
| POST | `/api/ranking/process` | Run full pipeline and return ranked results |
| GET | `/api/download/<result_id>` | Download ranking results as CSV |
| POST | `/api/feedback/submit` | Submit expert-validated tiers for historical learning |
| GET | `/api/feedback/history` | List all stored historical sessions |

---

## ML Classification

The system trains several classifiers and selects the best by cross-validated F1-macro
(ROC-AUC for binary targets), then tunes only the winner via RandomizedSearchCV:

- Random Forest
- Gradient Boosting
- Decision Tree
- Logistic Regression
- SVM (RBF)
- XGBoost (when installed)

Candidates are classified according to the user-provided **ground-truth column**
(a categorical label column). The class set is **free**: any names, any count ≥ 2
(e.g. `Admis / Refusé`, or `Non_classe / Moyen / Bon / Excellent`). The ground-truth
column must be defined from data **independent of the chosen criteria** to avoid target
leakage.

To keep the evaluation honest:
- scaling lives inside a per-fold `Pipeline` (no preprocessing leakage),
- a stratified hold-out set gives a real generalization estimate,
- the deployed model is then refit on all data.

SHAP values are computed for the top-ranked candidates to explain feature contributions
toward the best class.

---

## Feedback Loop

After reviewing the ranked results, an expert can:
1. Download the results (CSV or Excel)
2. Rename `Classe_predite` (or `Predicted_Tier`) to `Validated_Tier` and correct values — any label set with ≥ 2 classes
3. Re-upload via the FeedbackModal (CSV or Excel)

The validated data is stored in `backend/historical/` and automatically included in the next training session **whose criteria match** (sessions with different criteria are skipped to avoid mixing incomparable feature spaces), making the model progressively more accurate.

---

## Author

Vaneck DAGAR — *Méthodes de prise de décision multicritère hybrides pour le classement des candidatures*, 2026


