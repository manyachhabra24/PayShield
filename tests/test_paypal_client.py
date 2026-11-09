import copy
import unittest

from paypal_client import DEMO_PRODUCT, extract_verified_capture, order_matches_demo_product


def make_order(status="APPROVED", value="5.00", currency="USD",
               ref=DEMO_PRODUCT["id"], intent="CAPTURE", with_capture=False,
               capture_value="5.00", capture_status="COMPLETED"):
    order = {
        "id": "ABC123", "intent": intent, "status": status,
        "purchase_units": [{
            "reference_id": ref,
            "amount": {"currency_code": currency, "value": value},
        }],
    }
    if with_capture:
        order["purchase_units"][0]["payments"] = {"captures": [{
            "id": "CAP1", "status": capture_status,
            "amount": {"currency_code": currency, "value": capture_value},
            "create_time": "2026-11-02T10:00:00Z",
        }]}
    return order


class TestOrderMatching(unittest.TestCase):
    def test_correct_order_matches(self):
        self.assertTrue(order_matches_demo_product(make_order()))

    def test_value_formatting_is_tolerated(self):
        self.assertTrue(order_matches_demo_product(make_order(value="5")))

    def test_wrong_amount_rejected(self):
        self.assertFalse(order_matches_demo_product(make_order(value="500.00")))

    def test_wrong_currency_rejected(self):
        self.assertFalse(order_matches_demo_product(make_order(currency="EUR")))

    def test_wrong_product_rejected(self):
        self.assertFalse(order_matches_demo_product(make_order(ref="something-else")))

    def test_wrong_intent_rejected(self):
        self.assertFalse(order_matches_demo_product(make_order(intent="AUTHORIZE")))

    def test_two_units_rejected(self):
        order = make_order()
        order["purchase_units"].append(copy.deepcopy(order["purchase_units"][0]))
        self.assertFalse(order_matches_demo_product(order))

    def test_garbage_rejected(self):
        for bad in (None, "x", 5, {}, {"purchase_units": "no"}):
            self.assertFalse(order_matches_demo_product(bad))


class TestVerifiedCapture(unittest.TestCase):
    def test_completed_order_is_verified(self):
        result = extract_verified_capture(make_order("COMPLETED", with_capture=True))
        self.assertEqual(result["capture_id"], "CAP1")
        self.assertEqual(result["amount"], "5.00")

    def test_not_completed_is_not_verified(self):
        self.assertIsNone(extract_verified_capture(make_order("APPROVED", with_capture=True)))

    def test_missing_capture_is_not_verified(self):
        self.assertIsNone(extract_verified_capture(make_order("COMPLETED")))

    def test_pending_capture_is_not_verified(self):
        order = make_order("COMPLETED", with_capture=True, capture_status="PENDING")
        self.assertIsNone(extract_verified_capture(order))

    def test_capture_amount_mismatch_is_not_verified(self):
        order = make_order("COMPLETED", with_capture=True, capture_value="1.00")
        self.assertIsNone(extract_verified_capture(order))


if __name__ == "__main__":
    unittest.main()