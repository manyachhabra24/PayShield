# PayShield - deterministic analysis engine (Stage 3).
# No network access, no AI: just transparent rules that look at TEXT.
# Every finding is an INDICATOR, not proof.

import ipaddress
import re

from validation import parse_url_text

ASSESSMENT_LABELS = {
    "high_concern": "High concern",
    "some_warning_signs": "Some warning signs",
    "no_obvious_warning_signs": "No obvious warning signs detected",
    "unable_to_assess": "Unable to assess reliably",
}

# Small STARTER list. Verify each entry before adding more.
# A brand appearing in a domain we do NOT list here gets flagged,
# so this list must be extended carefully to avoid false alarms.
OFFICIAL_DOMAINS = {
    "paypal": {"paypal.com", "paypal.me", "paypalobjects.com"},
    "amazon": {"amazon.com", "amazon.in", "amazon.co.uk", "amazon.de",
               "amazon.ca", "amazonaws.com"},
    "google": {"google.com", "google.co.in", "googleapis.com", "gstatic.com",
               "googleusercontent.com"},
    "microsoft": {"microsoft.com", "microsoftonline.com", "live.com",
                  "office.com", "windows.com", "azure.com"},
    "netflix": {"netflix.com", "nflxvideo.net"},
    "flipkart": {"flipkart.com"},
    "phonepe": {"phonepe.com"},
    "hdfcbank": {"hdfcbank.com"},
    "icicibank": {"icicibank.com"},
    "apple": {"apple.com", "icloud.com"},
    "paytm": {"paytm.com"},
    "fedex": {"fedex.com"},
}

URL_SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd",
                  "cutt.ly", "rb.gy", "ow.ly"}

# Used by the registered-domain heuristic (e.g. bbc.co.uk).
# Real software uses the Public Suffix List; this is a simplified stand-in.
COMMON_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "edu", "ac"}


def _snippet(text, limit=80):
    return " ".join(text.split())[:limit]


def _indicator(ind_id, title, severity, points, source, observed, why):
    return {"id": ind_id, "title": title, "severity": severity,
            "points": points, "source": source,
            "observed": observed, "why": why}


# ---------------------------------------------------------------- URL checks

def registered_domain(hostname):
    """Simplified guess at the part of a hostname that is actually registered."""
    labels = hostname.split(".")
    if len(labels) <= 2:
        return hostname
    if len(labels[-1]) == 2 and labels[-2] in COMMON_SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _levenshtein(a, b):
    """Number of single-character edits needed to turn a into b."""
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _normalize_lookalike(label):
    label = label.replace("rn", "m").replace("vv", "w")
    return label.translate(str.maketrans({"0": "o", "1": "l", "3": "e",
                                          "5": "s", "$": "s"}))


def _mentions_brand(text, brand):
    # Short brand names must match a whole word, to avoid "apple" in "pineapple".
    if len(brand) >= 6:
        return brand in text
    return brand in re.split(r"[^a-z0-9]+", text)


def check_url(url):
    """Returns (hostname, [indicators])."""
    parsed = parse_url_text(url)
    hostname = (parsed.hostname or "").rstrip(".")
    found = []

    if parsed.username is not None:
        found.append(_indicator(
            "userinfo_trick", "Text before an @ sign in the address", "high", 4, "url",
            "Text before the @ sign: " + _snippet(parsed.username, 60),
            "In a web address, everything before @ is ignored when deciding where "
            "you actually go. Scammers put a trusted-looking name there so the "
            "real destination (after the @) is easy to miss."))

    if url.strip().lower().startswith("http://"):
        found.append(_indicator(
            "not_https", "Address starts with http:// (not https://)", "low", 1, "url",
            "The address you entered begins with http://.",
            "Unencrypted connections are weaker, and payment pages normally use "
            "https. This alone proves nothing: plenty of fraudulent sites use "
            "https too."))

    try:
        ipaddress.ip_address(hostname)
        found.append(_indicator(
            "ip_address_host", "Address is a number, not a name", "high", 3, "url",
            "Host: " + _snippet(hostname, 60),
            "Legitimate businesses almost always use a named website. A raw "
            "number hides who owns the destination."))
        return hostname, found
    except ValueError:
        pass  # not an IP address, which is the normal case

    labels = hostname.split(".")
    reg = registered_domain(hostname)
    sub_part = hostname[:-len(reg)].rstrip(".") if hostname != reg else ""
    sub_labels = sub_part.split(".") if sub_part else []
    reg_label = reg.split(".")[0]

    if any(label.startswith("xn--") for label in labels):
        found.append(_indicator(
            "punycode", "Address uses an encoded international name (xn--)", "medium", 2,
            "url", "Host: " + _snippet(hostname, 60),
            "The xn-- form is how international characters are stored. It can be "
            "legitimate, but it is also used to build look-alike addresses."))

    if any(ord(ch) > 127 for ch in hostname):
        found.append(_indicator(
            "non_ascii_hostname", "Address contains non-English characters", "medium", 2,
            "url", "Host: " + _snippet(hostname, 60),
            "Some letters from other alphabets look identical to English letters. "
            "Attackers use them to imitate real names. Many genuine international "
            "websites also use such characters."))

    if hostname in URL_SHORTENERS or reg in URL_SHORTENERS:
        found.append(_indicator(
            "url_shortener", "Link shortener", "medium", 2, "url",
            "Host: " + _snippet(hostname, 60),
            "A shortened link hides its real destination. We cannot see where it "
            "leads because we never visit links."))

    # Brand checks: report at most one brand finding.
    for brand, official in OFFICIAL_DOMAINS.items():
        if reg in official:
            continue
        if _mentions_brand(sub_part, brand):
            found.append(_indicator(
                "brand_in_subdomain", "Familiar brand name placed in front of a different domain",
                "high", 4, "url",
                f"The address contains '{brand}', but its real domain is {reg}.",
                "Only the part just before the final ending (like .com) shows who "
                "owns an address. Putting a trusted name in front is a common way "
                "to make a fake address look real."))
            break
        if _mentions_brand(reg_label, brand):
            found.append(_indicator(
                "brand_in_domain", "Brand name inside a domain this demo does not recognize",
                "medium", 3, "url",
                f"The domain {reg} contains '{brand}'.",
                "Fake sites often include a well-known name in their own domain. "
                "Note: this demo only knows a small list of official domains, so a "
                "genuine partner site could be flagged by mistake."))
            break
        if len(brand) >= 6 and reg_label != brand:
            nearest = min(_levenshtein(reg_label, brand),
                          _levenshtein(_normalize_lookalike(reg_label), brand))
            if nearest <= 1:
                found.append(_indicator(
                    "lookalike_spelling", "Domain spelled almost like a known brand",
                    "medium", 3, "url",
                    f"The domain {reg} is very close to '{brand}'.",
                    "Swapping or adding one character (like a 1 for an l) is a "
                    "classic way to imitate a trusted name."))
                break

    if len(sub_labels) >= 3:
        found.append(_indicator(
            "many_subdomains", "Many levels before the main domain", "low", 1, "url",
            f"{len(sub_labels)} extra parts before {reg}.",
            "Long chains can bury the real domain, but some legitimate services "
            "use them too."))

    if reg_label.count("-") >= 3:
        found.append(_indicator(
            "many_hyphens", "Domain name with many hyphens", "low", 1, "url",
            "Domain: " + _snippet(reg, 60),
            "Throwaway domains often chain words with hyphens. It is a weak "
            "signal on its own."))

    return hostname, found


# ------------------------------------------------------------ message checks

def _rule(rule_id, title, severity, points, pattern, why, skip_if_negated=False):
    return {"id": rule_id, "title": title, "severity": severity,
            "points": points, "regex": re.compile(pattern, re.IGNORECASE),
            "why": why, "skip_if_negated": skip_if_negated}


# Patterns use bounded gaps like {0,80} so they stay fast on long input.
MESSAGE_RULES = [
    _rule("urgency", "Pressure to act quickly", "medium", 2,
          r"\b(?:urgent(?:ly)?|immediately|act now|right away|final notice|last chance"
          r"|within\s+\d+\s*(?:hours?|hrs?|minutes?|mins?)|expires?\s+(?:today|soon|in))\b",
          "Urgency leaves little time to think or verify. Real organizations also "
          "send deadlines, so on its own this is a weak signal."),
    _rule("unexpected_fee", "Fee demanded to receive something", "high", 3,
          r"\b(?:release|customs|clearance|redelivery|re-delivery|handling|processing"
          r"|unlock|activation)\s+(?:fee|charge)s?\b"
          r"|\b(?:pay|send|transfer)\b[^.!?\n]{0,80}?\bto\s+(?:receive|release|unlock|claim|restore|reactivate)\b",
          "Being asked to pay first so that a parcel, refund or prize can be "
          "'released' is a very common scam pattern."),
    _rule("unusual_payment_method", "Unusual or hard-to-reverse payment method", "high", 3,
          r"\b(?:gift\s*cards?|bitcoin|crypto(?:currency)?|usdt|western union|moneygram"
          r"|wire transfer|friends\s*(?:and|&)\s*family)\b",
          "Gift cards, crypto and wire transfers are hard to get back. Payment "
          "types meant for friends and family usually do not come with purchase "
          "protection."),
    _rule("sensitive_info_request", "Asks for a code, password or card detail", "high", 4,
          r"\b(?:share|send|enter|provide|confirm|reply with|tell us|give)\b[^.!?\n]{0,40}?"
          r"\b(?:otp|one[- ]time (?:password|code)|password|pin|cvv|card number|aadhaar)\b",
          "Genuine organizations do not ask you to hand over one-time codes or "
          "passwords by message.", skip_if_negated=True),
    _rule("account_threat", "Threat of account problems or legal trouble", "medium", 2,
          r"\b(?:account|card|access)\b[^.!?\n]{0,40}?\b(?:suspended|blocked|closed|locked|terminated|limited)\b"
          r"|\blegal action\b|\barrest(?:ed)?\b",
          "Threats are used to scare people into acting. Real account notices "
          "exist too, so check through the official app or website."),
    _rule("prize_claim", "Claims you won something", "medium", 2,
          r"\b(?:you(?:'ve|\s+have)?\s+won|lottery|claim your prize|lucky winner)\b",
          "Unexpected prizes are a common lure, especially when paired with a "
          "fee."),
    _rule("off_platform_contact", "Moves the conversation to a chat app", "low", 1,
          r"\b(?:whatsapp|telegram)\b",
          "Scammers like private chat apps, but many honest businesses use "
          "them too."),
]

_NEGATION = re.compile(r"\b(?:never|do not|don't|dont|not)\b", re.IGNORECASE)


def check_message(message):
    found = []
    for rule in MESSAGE_RULES:
        for match in rule["regex"].finditer(message):
            if rule["skip_if_negated"]:
                prefix = message[max(0, match.start() - 30):match.start()]
                if _NEGATION.search(prefix):
                    continue  # e.g. "Never share your OTP" is advice, not a request
            found.append(_indicator(
                rule["id"], rule["title"], rule["severity"], rule["points"],
                "message", "Message says: \"" + _snippet(match.group(0)) + "\"",
                rule["why"]))
            break  # one finding per rule
    return found


def _mostly_non_english(message):
    letters = [ch for ch in message if ch.isalpha()]
    if len(letters) < 5:
        return False
    ascii_letters = [ch for ch in letters if ch.isascii()]
    return len(ascii_letters) / len(letters) < 0.5


# ---------------------------------------------------------------- combining

NEXT_STEPS = {
    "high_concern": [
        "Do not send money or share any details yet.",
        "Do not use links or phone numbers from the message. Type the official website address yourself, or use an app you already trust.",
        "Ask the person or business through a different, trusted channel whether they really sent this request.",
        "If you have already paid or shared details, contact your bank or the payment provider's official support right away.",
    ],
    "some_warning_signs": [
        "Pause before paying and double-check the recipient.",
        "Open the official website yourself instead of using the link you were given.",
        "Confirm the request through a channel you already trust.",
    ],
    "no_obvious_warning_signs": [
        "Still confirm the recipient through a channel you already trust before paying.",
        "If anything feels off, trust that feeling and verify first.",
    ],
    "unable_to_assess": [
        "Check the website address on its own, or paste the message in English.",
        "Verify the request through a channel you already trust.",
    ],
}

UNCERTAINTY = {
    "high_concern": "Several independent warning signs appeared together, which raises concern. These are rule-based indicators, so they can still be wrong in either direction.",
    "some_warning_signs": "Some warning signs were found, but each can also appear on legitimate sites and messages. Treat this as a reason to double-check, not as a verdict.",
    "no_obvious_warning_signs": "The checks found nothing notable, but they only cover what these simple rules can see. This says nothing about who really owns the website.",
    "unable_to_assess": "Part of the input could not be read by the checks (they only understand English messages), so this result is incomplete.",
}


def analyze(url, message=""):
    """Analyze already-validated input. Returns a structured, JSON-ready dict."""
    hostname, url_findings = check_url(url)
    message_findings = check_message(message) if message else []
    indicators = sorted(url_findings + message_findings, key=lambda i: -i["points"])

    total = sum(i["points"] for i in indicators)
    has_high = any(i["severity"] == "high" for i in indicators)
    non_english = bool(message) and _mostly_non_english(message)

    # A single keyword or single weak sign can never produce "high concern".
    if total >= 6 and len(indicators) >= 2 and has_high:
        assessment = "high_concern"
    elif total >= 2:
        assessment = "some_warning_signs"
    elif non_english and total < 2:
        assessment = "unable_to_assess"
    else:
        assessment = "no_obvious_warning_signs"

    not_verified = [
        "Whether the website exists or what it contains (we never visit it).",
        "How old the domain is, or whether it appears on any blocklist.",
        "Who owns the website, or whether it belongs to the business it claims to be.",
    ]
    if message:
        not_verified.append("Who actually sent the message.")

    limitations = ["The rule-based checks read the address and message as text only. They use no live reputation data.",
                   "The list of known brands is a small starter list."]
    if non_english:
        limitations.append("Message checks only understand English text.")

    return {
        "assessment": assessment,
        "assessment_label": ASSESSMENT_LABELS[assessment],
        "heuristic_points": total,
        "score_note": "A simple count of warning signs. It is not a probability.",
        "uncertainty_note": UNCERTAINTY[assessment],
        "hostname": hostname,
        "indicators": indicators,
        "not_verified": not_verified,
        "limitations": limitations,
        "next_steps": NEXT_STEPS[assessment],
        "disclaimer": "A low-concern result does not prove a request is legitimate. Always verify through an official channel you already trust.",
    }