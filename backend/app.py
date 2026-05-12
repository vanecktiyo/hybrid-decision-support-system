"""
Flask Application - Hybrid MCDM Backend
"""
from flask import Flask, jsonify
from flask_cors import CORS
import logging
from pathlib import Path

BASE_DIR = Path(__file__).parent

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = str(BASE_DIR / "uploads")
app.config["RESULTS_FOLDER"] = str(BASE_DIR / "results")
app.config["HISTORICAL_FOLDER"] = str(BASE_DIR / "historical")

Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
Path(app.config["RESULTS_FOLDER"]).mkdir(parents=True, exist_ok=True)
Path(app.config["HISTORICAL_FOLDER"]).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Register all blueprints
from routes import upload, download, ahp, ranking, feedback

app.register_blueprint(upload.bp)
app.register_blueprint(download.bp)
app.register_blueprint(ahp.bp)
app.register_blueprint(ranking.bp)
app.register_blueprint(feedback.bp)


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "version": "2.0.0"}), 200


@app.route("/api/info", methods=["GET"])
def app_info():
    return jsonify({
        "name": "Hybrid Multi-Criteria Decision Making System",
        "version": "2.0.0",
        "algorithms": ["AHP", "TOPSIS", "Random Forest", "Gradient Boosting", "Hybrid Fusion"],
        "supported_formats": ["CSV", "XLSX", "XLS"],
    }), 200


@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "Bad request", "message": str(e)}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal error: {e}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    logger.info("Starting Flask application on port 5000...")
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
