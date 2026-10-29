# PayShield - main Flask application.
# Stage 2: serves the page, a health check, and an /api/analyze endpoint
# that VALIDATES input only. The real analysis engine comes in Stage 3.

from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)
# Reject oversized request bodies (16 KB) before we even read them.
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

MAX_URL_LEN = 2048
MAX_MESSAGE_LEN = 2000


def validate_input(data):
    """Check the submitted data.
    Returns (cleaned_values, None) on success or (None, error_message) on failure.
    Error messages never echo the user's input back."""
    if not isinstance(data, dict):
        return None, "Invalid request."

    url = data.get("url", "")
    message = data.get("message", "")
    if not isinstance(url, str) or not isinstance(message, str):
        return None, "Invalid request."

    url = url.strip()
    message = message.strip()

    if not url:
        return None, "Please enter the website you plan to pay."
    if len(url) > MAX_URL_LEN:
        return None, "That web address is too long."
    if len(message) > MAX_MESSAGE_LEN:
        return None, f"The message is too long (maximum {MAX_MESSAGE_LEN} characters)."
    if any(ch.isspace() or ord(ch) < 32 for ch in url):
        return None, "A web address cannot contain spaces or hidden characters."

    # We only PARSE the URL as text. We never visit it.
    candidate = url if "://" in url else "http://" + url
    try:
        parsed = urlparse(candidate)
        hostname = parsed.hostname
        _ = parsed.port  # raises ValueError if the port is invalid
    except ValueError:
        return None, "That does not look like a valid web address."

    if parsed.scheme not in ("http", "https"):
        return None, "Only http and https web addresses can be checked."
    if not hostname or "." not in hostname or len(hostname) > 253:
        return None, "That does not look like a valid website address."

    return {"url": url, "hostname": hostname, "message": message}, None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "app": "PayShield"})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True)
    cleaned, error = validate_input(data)
    if error:
        return jsonify({"error": error}), 400

    # Stage 2: input is validated, but no analysis exists yet.
    # We deliberately do NOT invent a score.
    return jsonify({
        "status": "validated",
        "hostname": cleaned["hostname"],
        "has_message": bool(cleaned["message"]),
        "analysis_available": False,
    })


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "That request is too large."}), 413


@app.errorhandler(405)
def bad_method(_e):
    return jsonify({"error": "Method not allowed."}), 405