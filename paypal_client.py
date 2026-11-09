# PayShield - PayPal Sandbox client (Stage 5A).
# SANDBOX ONLY: the API address below is hard-coded, so this code can never
# touch real money. The amount is defined HERE, never by the browser.
import logging
import os
import re
import time
import uuid
from decimal import Decimal, InvalidOperation

import requests

SANDBOX_API = "https://api-m.sandbox.paypal.com"
TIMEOUT_SECONDS = 15
ORDER_ID_RE = re.compile(r"^[A-Z0-9]{1,36}$")
log = logging.getLogger("payshield.paypal")
# The ONE product this demo can sell. Fixed on the server.
DEMO_PRODUCT = {
    "id": "payshield-demo-checkout",
    "name": "PayShield sandbox demo checkout",
    "amount": "5.00",
    "currency": "USD",
}


class PayPalError(Exception):
    """A safe-to-show problem. The message never contains secrets or user input."""

    def __init__(self, message, http_status=502, issue=None, debug_id=None):
        super().__init__(message)
        self.message = message
        self.http_status = http_status
        self.issue = issue
        self.debug_id = debug_id


_token_cache = {"token": None, "expires_at": 0.0}


def is_configured():
    return bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_CLIENT_SECRET"))


def get_client_id():
    # The client ID is designed to be public. The SECRET never leaves the server.
    return os.getenv("PAYPAL_CLIENT_ID", "")


def _get_access_token():
    if _token_cache["token"] and _token_cache["expires_at"] - 60 > time.time():
        return _token_cache["token"]
    if not is_configured():
        raise PayPalError("PayPal is not configured on the server.", 503)
    try:
        response = requests.post(
            SANDBOX_API + "/v1/oauth2/token",
            auth=(os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_CLIENT_SECRET")),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        raise PayPalError("Could not reach PayPal. Please try again.", 502)
    if response.status_code != 200:
        raise PayPalError("PayPal rejected the server credentials. Check the .env file.", 502)
    try:
        data = response.json()
        token = data["access_token"]
        lifetime = float(data.get("expires_in", 300))
    except (ValueError, KeyError, TypeError):
        raise PayPalError("PayPal sent an unexpected response.", 502)
    _token_cache["token"] = token
    _token_cache["expires_at"] = time.time() + lifetime
    return token


def _request(method, path, json_body=None, request_id=None):
    headers = {
        "Authorization": "Bearer " + _get_access_token(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if request_id:
        headers["PayPal-Request-Id"] = request_id
    try:
        response = requests.request(method, SANDBOX_API + path, json=json_body,
                                    headers=headers, timeout=TIMEOUT_SECONDS)
    except requests.RequestException:
        raise PayPalError("Could not reach PayPal. Please try again.", 502)
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if response.status_code >= 400:
        details = data.get("details")
        issue = None
        if isinstance(details, list) and details and isinstance(details[0], dict):
            issue = details[0].get("issue")
        raise PayPalError("PayPal could not complete the request.", 502,
                          issue=issue, debug_id=data.get("debug_id"))
    return data


def _amounts_equal(a, b):
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except (InvalidOperation, ValueError):
        return False


def order_matches_demo_product(order):
    """True only if the order is exactly our fixed demo product."""
    if not isinstance(order, dict) or order.get("intent") != "CAPTURE":
        return False
    units = order.get("purchase_units")
    if not isinstance(units, list) or len(units) != 1 or not isinstance(units[0], dict):
        return False
    unit = units[0]
    amount = unit.get("amount") or {}
    return (unit.get("reference_id") == DEMO_PRODUCT["id"]
            and amount.get("currency_code") == DEMO_PRODUCT["currency"]
            and _amounts_equal(amount.get("value"), DEMO_PRODUCT["amount"]))


def extract_verified_capture(order):
    """Returns a small result dict ONLY if PayPal says the payment is completed
    for the expected amount and currency. Otherwise returns None."""
    if not order_matches_demo_product(order) or order.get("status") != "COMPLETED":
        return None
    payments = order["purchase_units"][0].get("payments") or {}
    captures = payments.get("captures")
    if not isinstance(captures, list) or not captures or not isinstance(captures[0], dict):
        return None
    capture = captures[0]
    amount = capture.get("amount") or {}
    if (capture.get("status") != "COMPLETED"
            or amount.get("currency_code") != DEMO_PRODUCT["currency"]
            or not _amounts_equal(amount.get("value"), DEMO_PRODUCT["amount"])):
        return None
    return {
        "order_id": order.get("id"),
        "capture_id": capture.get("id"),
        "status": "COMPLETED",
        "product": DEMO_PRODUCT["name"],
        "amount": DEMO_PRODUCT["amount"],
        "currency": DEMO_PRODUCT["currency"],
        "time": capture.get("create_time"),
    }


def create_demo_order():
    body = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": DEMO_PRODUCT["id"],
            "description": DEMO_PRODUCT["name"],
            "amount": {"currency_code": DEMO_PRODUCT["currency"],
                       "value": DEMO_PRODUCT["amount"]},
        }],
    }
    data = _request("POST", "/v2/checkout/orders", body, request_id=str(uuid.uuid4()))
    order_id = data.get("id")
    if not isinstance(order_id, str) or not ORDER_ID_RE.match(order_id):
        raise PayPalError("PayPal sent an unexpected response.", 502)
    return order_id


def get_order(order_id):
    return _request("GET", "/v2/checkout/orders/" + order_id)


def _capture_status(order):
    """Safe helper for logging: the status of the first capture, if any."""
    try:
        return order["purchase_units"][0]["payments"]["captures"][0].get("status")
    except (KeyError, IndexError, TypeError, AttributeError):
        return None


def capture_demo_order(order_id):
    """Verify, then capture. Safe to call twice for the same order.
    The final verification always uses a fresh GET of the order from PayPal."""
    order = get_order(order_id)
    if not order_matches_demo_product(order):
        raise PayPalError("This order does not match the demo product, so it was not captured.", 400)

    status = order.get("status")
    already_captured = False
    if status == "COMPLETED":
        already_captured = True
    elif status == "APPROVED":
        try:
            _request("POST", "/v2/checkout/orders/" + order_id + "/capture",
                     request_id="capture-" + order_id)
        except PayPalError as exc:
            if exc.issue == "ORDER_ALREADY_CAPTURED":
                already_captured = True
            elif exc.issue == "INSTRUMENT_DECLINED":
                raise PayPalError("PayPal reported that the payment method was declined. "
                                  "You can try again with another one.", 402,
                                  issue=exc.issue, debug_id=exc.debug_id)
            else:
                raise
    else:
        raise PayPalError("This order has not been approved by the buyer yet.", 409)

    # Re-read the order from PayPal and verify THAT (it includes intent,
    # product, amount and capture details in one consistent shape).
    final_order = get_order(order_id)
    result = extract_verified_capture(final_order)
    if result is None:
        # Log only statuses: no names, emails, tokens or secrets.
        log.warning("Verification failed: order_status=%s capture_status=%s matches=%s",
                    final_order.get("status"), _capture_status(final_order),
                    order_matches_demo_product(final_order))
        raise PayPalError("PayPal did not confirm a completed payment for the expected amount.", 502)
    result["already_captured"] = already_captured
    return result