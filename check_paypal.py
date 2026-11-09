# Manual check that your sandbox credentials work. Prints NO secrets.
from dotenv import load_dotenv

load_dotenv()

import paypal_client

print("Credentials present in .env:", paypal_client.is_configured())
try:
    order_id = paypal_client.create_demo_order()
    print("Order created. ID:", order_id)
    order = paypal_client.get_order(order_id)
    print("PayPal says status:", order.get("status"))
    print("Matches our demo product:", paypal_client.order_matches_demo_product(order))
except paypal_client.PayPalError as exc:
    print("FAILED:", exc.message, "| issue:", exc.issue, "| debug_id:", exc.debug_id)