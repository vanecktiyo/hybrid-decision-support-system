"""Tests for /api/feedback routes."""
import io
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def app(tmp_path):
    """Create a Flask test app with an isolated temp historical folder."""
    import importlib
    import app as app_module
    importlib.reload(app_module)  # ensure clean state

    app_module.app.config["TESTING"] = True
    app_module.app.config["HISTORICAL_FOLDER"] = str(tmp_path / "historical")
    Path(app_module.app.config["HISTORICAL_FOLDER"]).mkdir(parents=True, exist_ok=True)
    return app_module.app


@pytest.fixture
def client(app):
    return app.test_client()


def _csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def _valid_feedback_csv() -> bytes:
    df = pd.DataFrame(
        {
            "feat_a": [0.1, 0.5, 0.9, 0.3, 0.7],
            "feat_b": [0.8, 0.2, 0.6, 0.4, 0.9],
            "Validated_Tier": ["Faible", "Moyen", "Bon", "Excellent", "Bon"],
        }
    )
    return _csv_bytes(df)


# ------------------------------------------------------------------ POST /submit
class TestFeedbackSubmit:
    def test_submit_valid_csv_returns_200(self, client):
        data = {
            "file": (io.BytesIO(_valid_feedback_csv()), "test.csv"),
            "session_id": "test_session_01",
        }
        resp = client.post(
            "/api/feedback/submit", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 200

    def test_submit_response_has_status_success(self, client):
        data = {"file": (io.BytesIO(_valid_feedback_csv()), "test.csv")}
        resp = client.post(
            "/api/feedback/submit", data=data, content_type="multipart/form-data"
        )
        assert resp.get_json()["status"] == "success"

    def test_submit_returns_session_id(self, client):
        data = {
            "file": (io.BytesIO(_valid_feedback_csv()), "test.csv"),
            "session_id": "mySession",
        }
        resp = client.post(
            "/api/feedback/submit", data=data, content_type="multipart/form-data"
        )
        assert resp.get_json()["session_id"] == "mySession"

    def test_submit_returns_n_records(self, client):
        data = {"file": (io.BytesIO(_valid_feedback_csv()), "test.csv")}
        resp = client.post(
            "/api/feedback/submit", data=data, content_type="multipart/form-data"
        )
        assert resp.get_json()["n_records"] == 5

    def test_submit_no_file_returns_400(self, client):
        resp = client.post(
            "/api/feedback/submit", data={}, content_type="multipart/form-data"
        )
        assert resp.status_code == 400

    def test_submit_free_form_labels_accepted(self, client):
        # Labels are now free-form: any class names are valid (>= 2 distinct).
        df = pd.DataFrame(
            {"feat_a": [0.1, 0.5, 0.9, 0.3], "Validated_Tier": ["Low", "Mid", "High", "Low"]}
        )
        data = {"file": (io.BytesIO(_csv_bytes(df)), "free.csv")}
        resp = client.post(
            "/api/feedback/submit", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 200

    def test_submit_binary_labels_accepted(self, client):
        # Two classes are enough (e.g. Admis / Refusé).
        df = pd.DataFrame(
            {"feat_a": [0.1, 0.5, 0.9, 0.3], "Validated_Tier": ["Admis", "Refuse", "Admis", "Refuse"]}
        )
        data = {"file": (io.BytesIO(_csv_bytes(df)), "binary.csv")}
        resp = client.post(
            "/api/feedback/submit", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 200

    def test_submit_single_class_returns_400(self, client):
        # Fewer than 2 distinct classes is not learnable -> rejected.
        df = pd.DataFrame(
            {"feat_a": [0.1, 0.5, 0.9, 0.3], "Validated_Tier": ["Admis", "Admis", "Admis", "Admis"]}
        )
        data = {"file": (io.BytesIO(_csv_bytes(df)), "single.csv")}
        resp = client.post(
            "/api/feedback/submit", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 400

    def test_submit_excel_file_accepted(self, client):
        df = pd.DataFrame(
            {
                "feat_a": [0.1, 0.5, 0.9, 0.3, 0.7],
                "Validated_Tier": ["Bon", "Moyen", "Bon", "Excellent", "Moyen"],
            }
        )
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        data = {"file": (io.BytesIO(buf.getvalue()), "feedback.xlsx")}
        resp = client.post(
            "/api/feedback/submit", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 200

    def test_submit_missing_tier_column_returns_400(self, client):
        df = pd.DataFrame({"feat_a": [0.1, 0.5, 0.9, 0.3]})
        data = {"file": (io.BytesIO(_csv_bytes(df)), "no_tier.csv")}
        resp = client.post(
            "/api/feedback/submit", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 400

    def test_submit_too_few_rows_returns_400(self, client):
        df = pd.DataFrame(
            {"feat_a": [0.1, 0.5, 0.9], "Validated_Tier": ["Faible", "Moyen", "Bon"]}
        )
        data = {"file": (io.BytesIO(_csv_bytes(df)), "tiny.csv")}
        resp = client.post(
            "/api/feedback/submit", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 400

    def test_submit_with_predicted_tier_column_accepted(self, client):
        df = pd.DataFrame(
            {
                "feat_a": [0.1, 0.5, 0.9, 0.3, 0.7],
                "Predicted_Tier": ["Faible", "Moyen", "Bon", "Excellent", "Bon"],
            }
        )
        data = {"file": (io.BytesIO(_csv_bytes(df)), "predicted.csv")}
        resp = client.post(
            "/api/feedback/submit", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 200

    def test_submit_with_criteria_json_filters_features(self, client):
        df = pd.DataFrame(
            {
                "feat_a": [0.1, 0.5, 0.9, 0.3, 0.7],
                "unwanted": [1, 2, 3, 4, 5],
                "Validated_Tier": ["Faible", "Moyen", "Bon", "Excellent", "Bon"],
            }
        )
        import json
        data = {
            "file": (io.BytesIO(_csv_bytes(df)), "test.csv"),
            "criteria": json.dumps(["feat_a"]),
        }
        resp = client.post(
            "/api/feedback/submit", data=data, content_type="multipart/form-data"
        )
        body = resp.get_json()
        assert resp.status_code == 200
        assert "feat_a" in body["features_saved"]
        assert "unwanted" not in body["features_saved"]


# ------------------------------------------------------------------ GET /history
class TestFeedbackHistory:
    def test_history_returns_200(self, client):
        resp = client.get("/api/feedback/history")
        assert resp.status_code == 200

    def test_history_empty_initially(self, client):
        body = client.get("/api/feedback/history").get_json()
        assert body["n_sessions"] == 0
        assert body["sessions"] == []

    def test_history_reflects_submitted_session(self, client):
        data = {
            "file": (io.BytesIO(_valid_feedback_csv()), "test.csv"),
            "session_id": "hist_test",
        }
        client.post("/api/feedback/submit", data=data, content_type="multipart/form-data")
        body = client.get("/api/feedback/history").get_json()
        assert body["n_sessions"] == 1
        assert body["sessions"][0]["session_id"] == "hist_test"

    def test_history_total_records(self, client):
        data = {"file": (io.BytesIO(_valid_feedback_csv()), "test.csv")}
        client.post("/api/feedback/submit", data=data, content_type="multipart/form-data")
        body = client.get("/api/feedback/history").get_json()
        assert body["total_records"] == 5


# ------------------------------------------------------------------ DELETE /history/<id>
class TestFeedbackDelete:
    def _submit(self, client, session_id="del_session"):
        data = {
            "file": (io.BytesIO(_valid_feedback_csv()), "test.csv"),
            "session_id": session_id,
        }
        client.post("/api/feedback/submit", data=data, content_type="multipart/form-data")

    def test_delete_existing_returns_200(self, client):
        self._submit(client)
        resp = client.delete("/api/feedback/history/del_session")
        assert resp.status_code == 200

    def test_delete_removes_from_history(self, client):
        self._submit(client)
        client.delete("/api/feedback/history/del_session")
        body = client.get("/api/feedback/history").get_json()
        assert body["n_sessions"] == 0

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete("/api/feedback/history/ghost_session")
        assert resp.status_code == 404
