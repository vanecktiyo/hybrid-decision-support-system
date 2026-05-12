# Admission Ranking System

Generic hybrid decision support system for candidate ranking using a multi-criteria pipeline: **AHP → TOPSIS → ML classification → Hybrid Fusion**.

Built with Flask (backend) and React (frontend).

---

## Overview

This application allows any organization to rank candidates based on multiple criteria. It is not tied to a specific dataset — upload any CSV or Excel file and configure the criteria through the UI.

**Pipeline:**
1. **AHP** — compute criterion weights from pairwise comparisons (or use equal weights)
2. **TOPSIS** — rank candidates using weighted normalized distances
3. **ML Classification** — classify candidates into 4 levels (Faible / Moyen / Bon / Excellent) using the best cross-validated model among Random Forest, Gradient Boosting, Decision Tree, Logistic Regression, SVM
4. **Hybrid Fusion** — combine TOPSIS score (60%) and ML probability of Excellent (40%) into a final score
5. **SHAP** — explain the top candidates' scores using feature-level contributions
6. **Feedback loop** — experts validate and correct predicted tiers; validated data is stored and used to improve the ML model on future runs

---

## Project Structure

```
admission-ranking-system/
├── backend/
│   ├── app.py                  # Flask entry point
│   ├── core/
│   │   ├── ahp.py              # AHP weights + consistency ratio
│   │   ├── topsis.py           # TOPSIS ranking
│   │   ├── data_processor.py   # Normalization + missing value handling
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
│   │   │   ├── Dashboard.js        # Results + SHAP explanations
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

The system trains 5 classifiers and selects the best by cross-validated F1-macro:

- Random Forest
- Gradient Boosting
- Decision Tree
- Logistic Regression
- SVM (RBF)

Candidates are assigned to one of 4 tiers based on their target column (continuous or categorical):

| Tier | Level |
|------|-------|
| 0 | Faible |
| 1 | Moyen |
| 2 | Bon |
| 3 | Excellent |

SHAP values are computed for the top-ranked candidates to explain feature contributions toward the Excellent class.

---

## Feedback Loop

After reviewing the ranked results, an expert can:
1. Download the result CSV
2. Rename `Predicted_Tier` to `Validated_Tier` and correct values
3. Re-upload via the FeedbackModal

The validated data is stored in `backend/historical/` and automatically included in the next training session, making the model progressively more accurate.

---

## Author

Vaneck DAGAR — *Méthodes de prise de décision multicritère hybrides pour le classement des candidatures*, 2026
