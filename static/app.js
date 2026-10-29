// PayShield front-end, Stage 3.
// Security: all text from the user or server is inserted with textContent
// (never innerHTML), so it cannot inject HTML or scripts.

const form = document.getElementById("check-form");
const urlInput = document.getElementById("url-input");
const messageInput = document.getElementById("message-input");
const charCount = document.getElementById("char-count");
const formError = document.getElementById("form-error");
const analyzeBtn = document.getElementById("analyze-btn");
const sampleBtn = document.getElementById("sample-btn");
const resultSection = document.getElementById("result");
const resultHeading = document.getElementById("result-heading");
const resultBody = document.getElementById("result-body");

// Clearly fake demonstration data (".example" can never be a real website).
const SAMPLE_URL = "paypal.com.secure-refund-check.example/pay";
const SAMPLE_MESSAGE =
  "DEMO MESSAGE: Your parcel is on hold. Pay a $2.99 release fee within " +
  "2 hours or it will be returned. Pay now at the link below.";

const BADGE_CLASS = {
  high_concern: "badge-high",
  some_warning_signs: "badge-some",
  no_obvious_warning_signs: "badge-none",
  unable_to_assess: "badge-unable",
};
const SEVERITY_TEXT = {
  high: "Stronger warning sign",
  medium: "Warning sign",
  low: "Minor note",
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function addList(title, items) {
  if (!items || items.length === 0) return;
  resultBody.append(el("h3", null, title));
  const ul = el("ul");
  items.forEach((item) => ul.append(el("li", null, item)));
  resultBody.append(ul);
}

function renderResult(data) {
  resultBody.replaceChildren();

  resultBody.append(el("p", "badge " + (BADGE_CLASS[data.assessment] || "badge-unable"), data.assessment_label));
  resultBody.append(el("p", "muted", "Heuristic points: " + data.heuristic_points + ". " + data.score_note));
  resultBody.append(el("p", null, data.uncertainty_note));

  resultBody.append(el("h3", null, "What we observed"));
  if (data.indicators.length === 0) {
    resultBody.append(el("p", null, "The checks we ran found no specific warning signs."));
  }
  data.indicators.forEach((ind) => {
    const box = el("div", "indicator sev-" + ind.severity);
    box.append(el("p", "indicator-title", ind.title));
    box.append(el("p", "indicator-level", SEVERITY_TEXT[ind.severity] || ""));
    box.append(el("p", "observed", ind.observed));
    box.append(el("p", "why", "Why it matters (general explanation, not proof): " + ind.why));
    resultBody.append(box);
  });

  addList("What we could not verify", data.not_verified);
  addList("What to do next", data.next_steps);
  addList("Limitations of this check", data.limitations);
  resultBody.append(el("p", "disclaimer", data.disclaimer));

  resultSection.hidden = false;
  resultHeading.focus();
}

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
    renderResult(data);
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