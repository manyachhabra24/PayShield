# PayShield - main Flask application (Stage 3).
# The route only handles HTTP. The thinking happens in analyzer.py.

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from analyzer import analyze
from validation import validate_input

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # reject oversized requests


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "PayShield"})


@app.route("/api/analyze", methods=["POST"])
def analyze_route():
    cleaned, error = validate_input(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400

    try:
        result = analyze(cleaned["url"], cleaned["message"])
    except Exception as exc:
        # Log only the error TYPE, never the user's input.
        app.logger.error("Analysis failed: %s", type(exc).__name__)
        return jsonify({"error": "Something went wrong while checking. Please try again."}), 500

    return jsonify(result)


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "That request is too large."}), 413


@app.errorhandler(405)
def bad_method(_e):
    return jsonify({"error": "Method not allowed."}), 405