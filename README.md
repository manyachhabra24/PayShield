# PayShield

**Check a payment destination before you send money.**
Built for the PayPal AI Hackathon.

Don't just detect payment scams. Stop and think before you pay.

A privacy-first, pre-transaction payment security scanner.

 PayShield helps consumers identify suspicious payment destinations before authorizing a transaction. PayShield is a pre-transaction scanner that stores nothing. A user enters the website they are about to pay and, optionally, the message that asked them to pay. PayShield runs deterministic, rule-based checks for brand impersonation and coercive payment language. It can pair those findings with an optional Gemini explanation constrained to a strict output schema. It then demonstrates how a PayPal checkout can stay paused until the user acknowledges the specific warnings found.

> **Sandbox only.** No real money is involved anywhere in this project.

## Try it in 60 seconds

1. Run the app (see [Installation](#installation)) and open http://127.0.0.1:5000.
2. Click a demo scenario (all data is fake):
   - **Look-alike + fee**: a trusted brand placed in front of an unrelated domain, plus a "release fee" demand. Expected result: *High concern*.
   - **Urgent invoice**: pressure to pay with gift cards. Expected result: *Some warning signs*.
   - **No warning signs**: an ordinary address and receipt message. Expected result: a blue *No obvious warning signs* result that still says it proves nothing.
3. Optionally tick the AI box to add a Gemini explanation.
4. Unlock the sandbox checkout (acknowledge the warnings if any were found) and pay with a PayPal sandbox buyer account. The page shows a result only after the server verifies it with PayPal.

## The problem

Scams work by rushing someone into paying a website or account they have not verified: a parcel "release fee", a refund that needs a fee first, a look-alike checkout page. Most tools return a one-word verdict with no reasoning, or nothing at all before the payment.

PayShield's principle: **check the payment request, not the person's life.** It needs no inbox, contacts, bank account or payment history, and it only sees what the user deliberately pastes.

## What PayShield does

- **Local rule engine (always on).** The website address is analyzed *as text* and never visited. The rule checks use only Python's standard library and make no network calls, no DNS lookups and no external API calls, so they keep working with the internet switched off once the app is running locally. Checks include:
  - a trusted brand name placed in front of a different domain
  - look-alike spellings and brand names inside unknown domains
  - the `@` address trick, IP-address hosts, link shorteners, encoded (`xn--`) and non-English host names
  - payment-pressure language: urgent deadlines, fees to "release" something, gift cards or crypto, requests for one-time codes or passwords, account threats, prize claims
- **Cautious assessment.** Every finding states what was observed and why it matters. One weak sign can never produce "High concern". The score is a simple count of warning signs and is labelled **not a probability**. A low result is shown in blue, not green, and always says it proves nothing.
- **Optional AI explanation (opt-in, off by default).** A Gemini model explains the evidence in plain language, in its own labelled box. It cannot change the rule-based assessment.
- **Gated PayPal sandbox checkout.** After a check, a demo checkout for a fixed test product unlocks. If warnings were found, the user must acknowledge them first.

## Responsible AI design

The AI layer is built around the idea that a model should *interpret evidence*, not act as an oracle.

- **Opt-in with disclosure.** Nothing is sent to Google unless the user ticks the box, and the form states what is sent: the website's hostname (not the path), the warning signs found, and the message text.
- **It reports agreement with the rules.** The output states whether its reading is *consistent*, *partly consistent* or *inconsistent* with the rule-based result, with a note. Disagreement is shown, not hidden.
- **It separates unverified context.** Things it noticed in the message that the rules did not cover are listed separately and marked unverified (for example, that a message mentions a parcel being on hold).
- **It states its uncertainty.** Each answer lists what is not known (for example, who sent the message, or whether the website relates to the brand named).
- **It cannot claim to have checked anything.** The prompt forbids claims about reputation, domain age, ownership, blocklists or website content. The model receives no such data.
- **Untrusted input handling.** The message is passed as a JSON string, and the instructions say to ignore any instructions inside it (prompt injection). The reply must match a strict JSON schema and pass server-side validation (lengths, allowed values). Any reply that vouches for a site's safety is discarded.
- **Graceful fallback.** If the AI is off, unconfigured, rate-limited, slow or returns something invalid, the page says so and the rule-based result is unaffected.

No accuracy figures are claimed. This design was checked with unit tests and manual testing, not with a benchmark.

## Why PayPal Checkout is included

PayShield demonstrates **protective friction**. In an active scam, victims are pressured into an impulsive checkout. Step 2 is a simulation of how a checkout button, rendered with the PayPal JavaScript SDK v6, can stay locked until the user has seen and acknowledged the specific warning signs found in Step 1.

What this demo is, and is not:
- It **is** a working, server-verified PayPal sandbox flow: server-side order creation, verification and capture.
- It **is not** a payment to the website being checked. PayPal pays accounts, not URLs, so the checkout pays PayShield's own demo merchant, and a successful test payment says nothing about the checked website.
- The gate is enforced in the **browser** only (see [Known limitations](#known-limitations)).

## How PayPal and AI are used

**PayPal**
- Browser: PayPal JavaScript SDK v6 button.
- Server: PayPal Orders API v2. The server creates the order for a **fixed, server-defined product, amount and currency** (the browser sends no price).
- Before capturing, the server fetches the order from PayPal and checks the product, amount and currency, then captures with a `PayPal-Request-Id`. It re-fetches the order and shows success **only** when PayPal reports a completed capture for the expected amount.
- Repeated capture requests are handled safely, with no second charge. Cancelled and failed payments show clear messages.

**AI**
- Google Gemini API (`generateContent`) with structured JSON output. The AI code is isolated in `ai_explainer.py`, so the provider can be swapped without touching the rest of the app.

## Architecture and data flow

```
User input (URL / message)
          │
          ▼
[ Flask API: POST /api/analyze ]
    ├── validation.py    ──> Input validation (length, format, hidden/control characters)
    ├── analyzer.py      ──> Rule engine (local text analysis, 0 network calls)
    └── ai_explainer.py  ──> (opt-in) Gemini API, schema-constrained output, validated
          │
          ▼
[ Gated checkout demo: /api/paypal/* ]
    ├── create-order     ──> Fixed-amount server-side order ($5.00 USD)
    └── capture-order    ──> Verify order, capture with PayPal-Request-Id (idempotent),
                             re-verify completed capture
          │
          ▼
PayPal Sandbox API (Orders v2)
```

Files: `app.py` (routes), `validation.py`, `analyzer.py`, `ai_explainer.py`, `paypal_client.py`, `templates/index.html`, `static/app.js`, `static/style.css`, `tests/`.

## Privacy behavior

- No database, no accounts, no analytics. Submitted text is **not stored**.
- Logs record only error types and PayPal debug IDs, never user input, tokens or secrets.
- Websites are **never fetched or resolved**, so there is no server-side request forgery surface.
- Nothing the user types is sent to PayPal.
- Text is sent to Google **only if the AI box is ticked**. Google's terms for the free Gemini API tier say submitted content may be used to improve its products, so check Google's current terms and use only sample data when testing. PayShield cannot control what a provider does with data it receives.

## Installation

Requirements: Python 3.10+ and Git.

```powershell
git clone https://github.com/YOUR-USERNAME/payshield.git
cd payshield
python -m venv venv
.\venv\Scripts\Activate.ps1          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
Copy-Item .env.example .env          # macOS/Linux: cp .env.example .env
```

Fill in `.env` (see below), then run:

```powershell
flask --app app run
```

Open http://127.0.0.1:5000. (Add `--debug` only for local development.)

The rule checks work with no `.env` values at all. PayPal and the AI each need their own keys.

### Configure the PayPal sandbox

1. Create a free account at https://developer.paypal.com and switch the dashboard toggle to **Sandbox**.
2. Under **Testing Tools > Sandbox Accounts**, create a **Business** account and a **Personal** account, both with country **United States**.
3. Under **Apps & Credentials > Sandbox > Create App**, create a **Merchant** app and link it to the US Business account.
4. Copy the app's Client ID and Secret into `.env` as `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET`.
5. Verify the credentials: `python check_paypal.py` should print an order ID and status `CREATED`.
6. When you click the PayPal button, log in with the **sandbox Personal account** (never a real PayPal login).

> Use a US sandbox merchant. With a merchant account from another country, PayPal returned `UNSUPPORTED_PAYEE_CURRENCY` for the USD order.

### Configure the AI (optional)

Create a Gemini API key in Google AI Studio and set `AI_API_KEY` and `AI_MODEL` in `.env`. Model names change and some are retired, so run `python check_ai.py` to list the models your key can use, and pick a fast Flash or Flash-Lite one (for example `gemini-flash-lite-latest`). `check_ai.py` also runs a test call on the demo sample.

## Tests

```powershell
python -m unittest discover -s tests -t . -v
```

The automated tests cover the rule engine (legitimate, suspicious, look-alike and edge-case inputs, and the three demo scenarios), input validation, PayPal order matching and verification logic (offline), and AI output validation, the safety filter and prompt construction (offline). Live PayPal and Gemini behavior was tested manually, not in automated tests.

## Known limitations

- **The checkout gate is a front-end demonstration.** The server's `create-order` endpoint does not require a prior analysis, so the gate is not a security boundary. A production version would tie each checkout to a server-side record of the check.
- The checkout pays PayShield's demo merchant, not the website being checked.
- The known-brand list is a small starter list. A genuine partner site that is not on it can be flagged by mistake.
- Message checks understand English only.
- Rules are heuristics. They cannot see a website's content, age, ownership or blocklist status, and the AI cannot either.
- Sandbox only. Free-tier AI can be slow, busy or rate-limited, and model names change over time.
- Rate limiting exists only for AI requests and is held in memory.
- Not hosted. Run it locally using the steps above.

## Security considerations

Implemented: secrets only in `.env` (git-ignored), the sandbox API address hard-coded, server-side validation and a request-size limit, no `innerHTML` (all dynamic text uses `textContent`), server-defined price, order verification before and after capture, idempotent capture, and validation of untrusted AI output.

Not done: no Content Security Policy, no CSRF tokens (the API uses no cookies or sessions), no rate limiting beyond the AI endpoint, and no independent audit. This is a hackathon demonstration and is **not production-ready**.

## Future improvements

A larger, curated brand list; more languages; domain-age and blocklist lookups from legitimate APIs; extracting links from pasted messages; a server-enforced link between a check and a checkout; a merchant-side integration that checks a payment request against a real PayPal order; hosted deployment.

## License

MIT. See `LICENSE`.

## Built by

PayShield was built by a first-year BTech student. I used Claude (Anthropic) as an architectural sounding board, and coding accelerator. I ran the application, tested the PayPal sandbox flow and the Gemini integration, ran the unit tests, and debugged the problems that came up. The AI feature uses Google's Gemini API.