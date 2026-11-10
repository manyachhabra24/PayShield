# Lists models your key can use, then tests the AI layer on the demo sample.
# Prints NO secrets.
import os

from dotenv import load_dotenv

load_dotenv()

import requests

import ai_explainer
from analyzer import analyze

key = os.getenv("AI_API_KEY", "").strip()
if not key:
    raise SystemExit("AI_API_KEY is empty in .env")

response = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                        headers={"x-goog-api-key": key}, params={"pageSize": 100}, timeout=20)
print("Model list HTTP status:", response.status_code)
if response.status_code == 200:
    print("Models that support generateContent:")
    for m in response.json().get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            print("  ", m["name"].replace("models/", ""))

model = os.getenv("AI_MODEL", "").strip()
print("\nAI_MODEL in .env:", model or "(empty)")
if model:
    sample = "DEMO MESSAGE: Your parcel is on hold. Pay a $2.99 release fee within 2 hours."
    result = analyze("paypal.com.secure-refund-check.example/pay", sample)
    ai = ai_explainer.explain(result, sample, client_key="check-script")
    print("AI status:", ai.get("status"))
    print({k: v for k, v in ai.items() if k != "status"})