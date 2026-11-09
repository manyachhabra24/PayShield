# PayShield - main Flask application (Stage 5A).
# Routes only handle HTTP. Analysis lives in analyzer.py, PayPal in paypal_client.py.

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()  # must run before paypal_client reads environment variables

import paypal_client
from analyzer import analyze
from validation import validate_input

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
        app.logger.error("Analysis failed: %s", type(exc).__name__)
        return jsonify({"error": "Something went wrong while checking. Please try again."}), 500
    return jsonify(result)


# ------------------------------------------------------------------ PayPal

def _paypal_error_response(exc):
    # Log only safe identifiers: never tokens, secrets, or user input.
    app.logger.error("PayPal error: issue=%s debug_id=%s", exc.issue, exc.debug_id)
    return jsonify({"error": exc.message}), exc.http_status


@app.route("/api/paypal/config")
def paypal_config():
    configured = paypal_client.is_configured()
    return jsonify({
        "configured": configured,
        "environment": "sandbox",
        "client_id": paypal_client.get_client_id() if configured else None,
        "product": {
            "name": paypal_client.DEMO_PRODUCT["name"],
            "amount": paypal_client.DEMO_PRODUCT["amount"],
            "currency": paypal_client.DEMO_PRODUCT["currency"],
        },
    })


@app.route("/api/paypal/create-order", methods=["POST"])
def paypal_create_order():
    # The request body is deliberately ignored: the browser cannot choose
    # the product or the price.
    try:
        order_id = paypal_client.create_demo_order()
    except paypal_client.PayPalError as exc:
        return _paypal_error_response(exc)
    return jsonify({"id": order_id})


@app.route("/api/paypal/capture-order", methods=["POST"])
def paypal_capture_order():
    data = request.get_json(silent=True)
    order_id = data.get("orderID") if isinstance(data, dict) else None
    if not isinstance(order_id, str) or not paypal_client.ORDER_ID_RE.match(order_id):
        return jsonify({"error": "Invalid order."}), 400
    try:
        result = paypal_client.capture_demo_order(order_id)
    except paypal_client.PayPalError as exc:
        return _paypal_error_response(exc)
    return jsonify(result)


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "That request is too large."}), 413


@app.errorhandler(405)
def bad_method(_e):
    return jsonify({"error": "Method not allowed."}), 405