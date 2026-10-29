// PayShield front-end, Stage 2.
// Security note: all text from the user or server is inserted with
// textContent (never innerHTML), so it cannot inject HTML or scripts.

const form = document.getElementById("check-form");
const urlInput = document.getElementById("url-input");
const messageInput = document.getElementById("message-input");
const charCount = document.getElementById("char-count");
const formError = document.getElementById("form-error");
const analyzeBtn = document.getElementById("analyze-btn");
const sampleBtn = document.getElementById("sample-btn");
const resultSection = document.getElementById("result");
const resultText = document.getElementById("result-text");

// Clearly fake demonstration data. ".example" is a reserved domain that
// can never belong to a real website.
const SAMPLE_URL = "paypal.com.secure-refund-check.example/pay";
const SAMPLE_MESSAGE =
  "DEMO MESSAGE: Your parcel is on hold. Pay a $2.99 release fee within " +
  "2 hours or it will be returned. Pay now at the link below.";

function showError(text) {
  formError.textContent = text;
  formError.hidden = false;
}

function clearError() {
  formError.textContent = "";
  formError.hidden = true;
}

function setLoading(isLoading) {
  analyzeBtn.disabled = isLoading;
  sampleBtn.disabled = isLoading;
  analyzeBtn.textContent = isLoading ? "Checking..." : "Check this website";
}

messageInput.addEventListener("input", () => {
  charCount.textContent = String(messageInput.value.length);
});

sampleBtn.addEventListener("click", () => {
  urlInput.value = SAMPLE_URL;
  messageInput.value = SAMPLE_MESSAGE;
  charCount.textContent = String(messageInput.value.length);
  clearError();
  resultSection.hidden = true;
  urlInput.focus();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  resultSection.hidden = true;

  const url = urlInput.value.trim();
  if (!url) {
    showError("Please enter the website you plan to pay.");
    urlInput.focus();
    return;
  }

  setLoading(true);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url, message: messageInput.value }),
      signal: controller.signal,
    });

    let data = null;
    try {
      data = await response.json();
    } catch (parseError) {
      data = null;
    }

    if (!response.ok || !data) {
      showError((data && data.error) || "Something went wrong. Please try again.");
      return;
    }

    resultText.textContent =
      "Input accepted. Website address parsed as: " + data.hostname +
      ". The analysis engine is not built yet (arrives in Stage 3), so " +
      "there is no risk assessment to show.";
    resultSection.hidden = false;
  } catch (error) {
    if (error.name === "AbortError") {
      showError("The request took too long. Please try again.");
    } else {
      showError("Could not reach the server. Is it running?");
    }
  } finally {
    clearTimeout(timer);
    setLoading(false);
  }
});