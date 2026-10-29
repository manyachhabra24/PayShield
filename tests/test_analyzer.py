import time
import unittest

from analyzer import analyze
from validation import MAX_MESSAGE_LEN, MAX_URL_LEN, validate_input

SAMPLE_MESSAGE = ("DEMO MESSAGE: Your parcel is on hold. Pay a $2.99 release fee within "
                  "2 hours or it will be returned. Pay now at the link below.")


def ids(result):
    return {i["id"] for i in result["indicators"]}


class TestLegitimateInputs(unittest.TestCase):
    def test_official_paypal_url(self):
        r = analyze("https://www.paypal.com/myaccount", "")
        self.assertEqual(r["assessment"], "no_obvious_warning_signs")
        self.assertEqual(r["heuristic_points"], 0)

    def test_official_subdomain_is_not_flagged(self):
        r = analyze("https://login.paypal.com", "")
        self.assertEqual(r["assessment"], "no_obvious_warning_signs")

    def test_ordinary_message(self):
        r = analyze("amazon.in", "Your order #123 has shipped. Track it in your account.")
        self.assertEqual(r["assessment"], "no_obvious_warning_signs")


class TestSuspiciousInputs(unittest.TestCase):
    def test_sample_is_high_concern(self):
        r = analyze("paypal.com.secure-refund-check.example/pay", SAMPLE_MESSAGE)
        self.assertEqual(r["assessment"], "high_concern")
        self.assertIn("brand_in_subdomain", ids(r))
        self.assertIn("unexpected_fee", ids(r))

    def test_misleading_subdomain(self):
        r = analyze("https://paypal.com.account-verify.example", "")
        self.assertIn("brand_in_subdomain", ids(r))
        self.assertEqual(r["assessment"], "some_warning_signs")

    def test_lookalike_spelling(self):
        r = analyze("https://paypa1.com", "")
        self.assertIn("lookalike_spelling", ids(r))

    def test_ip_address_host(self):
        self.assertIn("ip_address_host", ids(analyze("http://192.168.0.1/pay", "")))

    def test_at_sign_trick(self):
        self.assertIn("userinfo_trick", ids(analyze("https://paypal.com@evil.example/", "")))

    def test_url_shortener(self):
        self.assertIn("url_shortener", ids(analyze("https://bit.ly/abc", "")))

    def test_gift_card_request(self):
        self.assertIn("unusual_payment_method", ids(analyze("example.com", "Please pay with gift cards.")))

    def test_otp_request(self):
        self.assertIn("sensitive_info_request", ids(analyze("example.com", "Please share your OTP to confirm.")))


class TestUnusualButPossiblyLegitimate(unittest.TestCase):
    def test_http_alone_is_a_minor_note(self):
        r = analyze("http://example.com", "")
        self.assertIn("not_https", ids(r))
        self.assertEqual(r["assessment"], "no_obvious_warning_signs")

    def test_many_subdomains_alone_is_minor(self):
        r = analyze("https://a.b.c.d.example.com", "")
        self.assertIn("many_subdomains", ids(r))
        self.assertEqual(r["assessment"], "no_obvious_warning_signs")

    def test_long_hostname_alone_is_not_flagged(self):
        r = analyze("https://very-long-but-ordinary-business-name-for-testing.example.com", "")
        self.assertEqual(r["assessment"], "no_obvious_warning_signs")

    def test_international_domain_is_not_high_concern(self):
        r = analyze("https://münchen.de", "")
        self.assertIn("non_ascii_hostname", ids(r))
        self.assertNotEqual(r["assessment"], "high_concern")


class TestFalsePositives(unittest.TestCase):
    def test_negated_otp_advice_is_not_a_request(self):
        r = analyze("paypal.com", "Never share your OTP with anyone.")
        self.assertNotIn("sensitive_info_request", ids(r))

    def test_delivery_window_is_not_high_concern(self):
        r = analyze("example.com", "Your delivery arrives within 2 hours.")
        self.assertNotEqual(r["assessment"], "high_concern")

    def test_keywords_alone_cannot_reach_high_concern(self):
        r = analyze("example.com", "Urgent: act now! Your account has been suspended. You won a lottery.")
        self.assertEqual(r["assessment"], "some_warning_signs")


class TestValidation(unittest.TestCase):
    def assert_rejected(self, data):
        cleaned, error = validate_input(data)
        self.assertIsNone(cleaned)
        self.assertIsInstance(error, str)

    def test_empty(self):
        self.assert_rejected({"url": "", "message": ""})

    def test_whitespace_only(self):
        self.assert_rejected({"url": "   ", "message": ""})

    def test_not_a_dict(self):
        self.assert_rejected("hello")

    def test_non_string_url(self):
        self.assert_rejected({"url": 123, "message": ""})

    def test_no_dot(self):
        self.assert_rejected({"url": "hello", "message": ""})

    def test_wrong_scheme(self):
        self.assert_rejected({"url": "ftp://example.com", "message": ""})

    def test_space_inside(self):
        self.assert_rejected({"url": "exa mple.com", "message": ""})

    def test_hidden_character(self):
        self.assert_rejected({"url": "example\u200b.com", "message": ""})

    def test_bad_port(self):
        self.assert_rejected({"url": "http://example.com:99999", "message": ""})

    def test_scheme_only(self):
        self.assert_rejected({"url": "http://", "message": ""})

    def test_url_too_long(self):
        self.assert_rejected({"url": "a" * (MAX_URL_LEN + 1) + ".com", "message": ""})

    def test_message_too_long(self):
        self.assert_rejected({"url": "example.com", "message": "a" * (MAX_MESSAGE_LEN + 1)})

    def test_valid_without_scheme(self):
        cleaned, error = validate_input({"url": "example.com", "message": ""})
        self.assertIsNone(error)
        self.assertEqual(cleaned["url"], "example.com")


class TestRobustness(unittest.TestCase):
    def test_max_length_message_is_fast(self):
        message = ("pay urgent " * 200)[:MAX_MESSAGE_LEN]
        start = time.time()
        analyze("example.com", message)
        self.assertLess(time.time() - start, 1.0)

    def test_emoji_message_does_not_crash(self):
        r = analyze("example.com", "\U0001F389 You won! \U0001F389")
        self.assertIn("assessment", r)

    def test_non_english_message_is_unable_to_assess(self):
        r = analyze("example.com", "आपका पार्सल रुका है। कृपया भुगतान करें।")
        self.assertEqual(r["assessment"], "unable_to_assess")

    def test_result_has_expected_keys(self):
        r = analyze("example.com", "")
        for key in ("assessment", "assessment_label", "heuristic_points", "score_note",
                    "uncertainty_note", "indicators", "not_verified", "limitations",
                    "next_steps", "disclaimer", "hostname"):
            self.assertIn(key, r)


if __name__ == "__main__":
    unittest.main()