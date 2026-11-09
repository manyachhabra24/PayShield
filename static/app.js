// PayShield front-end, Stage 5B.
// Security: all text from the user or server is inserted with textContent
// (never innerHTML). The browser never decides the payment amount, and a
// payment is only shown as successful after the SERVER verifies it.

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

const payProduct = document.getElementById("pay-product");
const payLockNote = document.getElementById("pay-lock-note");
const payAck = document.getElementById("pay-ack");
const ackCheckbox = document.getElementById("ack-checkbox");
const ackText = document.getElementById("ack-text");
const payError = document.getElementById("pay-error");
const payButton = document.getElementById("paypal-button");
const payResult = document.getElementById("pay-result");

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

// ------------------------------------------------------------- analysis UI

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

// ------------------------------------------------------------- payment gate

let currentAssessment = null;   // null until a check has finished
let paypalReady = false;
let paypalSetupError = null;
let paymentInProgress = false;

class ServerMessageError extends Error {}

function needsAcknowledgement() {
  return currentAssessment === "high_concern" || currentAssessment === "some_warning_signs";
}

function isUnlocked() {
  if (!currentAssessment || !paypalReady) return false;
  return !needsAcknowledgement() || ackCheckbox.checked;
}

function showPayError(text) {
  payError.textContent = text;
  payError.hidden = false;
}

function clearPayError() {
  payError.textContent = "";
  payError.hidden = true;
}

function updatePaymentGate() {
  if (!currentAssessment) {
    payLockNote.textContent = "Check a website above first. This step unlocks after the check.";
    payLockNote.hidden = false;
    payAck.hidden = true;
    payButton.hidden = true;
    return;
  }

  const needsAck = needsAcknowledgement();
  payAck.hidden = !needsAck;
  if (needsAck) {
    ackText.textContent = currentAssessment === "high_concern"
      ? "PayShield found strong warning signs. I understand the risk and still want to continue with this demo payment."
      : "PayShield found some warning signs. I have read them and still want to continue with this demo payment.";
  }

  if (!paypalReady) {
    payLockNote.textContent = paypalSetupError || "Loading PayPal...";
    payLockNote.hidden = false;
    payButton.hidden = true;
    return;
  }

  if (!isUnlocked()) {
    payLockNote.textContent = "Tick the box above to continue.";
    payLockNote.hidden = false;
    payButton.hidden = true;
    return;
  }

  payLockNote.hidden = true;
  payButton.hidden = false;
}

ackCheckbox.addEventListener("change", updatePaymentGate);

function renderPaymentResult(result) {
  payResult.replaceChildren();
  payResult.append(el("h3", null, "Payment verified (sandbox)"));
  payResult.append(el("p", null, "Our server confirmed with PayPal that this test payment was completed."));
  payResult.append(el("p", null, "Product: " + result.product));
  payResult.append(el("p", null, "Amount: " + result.amount + " " + result.currency + " (test money)"));
  payResult.append(el("p", null, "Status: " + result.status));
  payResult.append(el("p", "mono", "Order ID: " + result.order_id));
  payResult.append(el("p", "mono", "Capture ID: " + result.capture_id));
  if (result.time) payResult.append(el("p", null, "Time: " + result.time));
  if (result.already_captured) {
    payResult.append(el("p", "muted", "This order had already been captured, so no second payment was taken."));
  }
  payResult.append(el("p", "muted",
    "This was a sandbox test. No real money moved, and it does not mean the website you checked is safe."));
  payResult.hidden = false;

  payButton.hidden = true;
  payAck.hidden = true;
  payLockNote.hidden = true;
}

// ------------------------------------------------------------- PayPal flow

async function createOrder() {
  // We send NO amount and NO product: the server decides both.
  const response = await fetch("/api/paypal/create-order", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  let data = null;
  try {
    data = await response.json();
  } catch (e) {
    data = null;
  }
  if (!response.ok || !data || !data.id) {
    throw new ServerMessageError((data && data.error) || "Could not create the order.");
  }
  return { orderId: data.id };   // v6 requires this exact shape
}

async function handleApprove(data) {
  try {
    const response = await fetch("/api/paypal/capture-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ orderID: data.orderId }),
    });
    let result = null;
    try {
      result = await response.json();
    } catch (e) {
      result = null;
    }
    if (!response.ok || !result) {
      showPayError((result && result.error) ||
        "We could not verify the payment. Do not assume it succeeded.");
      return;
    }
    renderPaymentResult(result);
  } catch (error) {
    showPayError("We could not confirm the payment. Do not assume it succeeded.");
  } finally {
    paymentInProgress = false;
  }
}

function handleCancel() {
  paymentInProgress = false;
  showPayError("Payment cancelled. Nothing was charged.");
}

function handleError(error) {
  console.error("PayPal error:", error);
  paymentInProgress = false;
  showPayError("PayPal reported a problem. Nothing was charged. Please try again.");
}

async function onPayClick(session) {
  if (paymentInProgress || !isUnlocked()) return;
  clearPayError();
  payResult.hidden = true;
  paymentInProgress = true;
  try {
    await session.start({ presentationMode: "auto" }, createOrder());
  } catch (error) {
    paymentInProgress = false;
    showPayError(error instanceof ServerMessageError
      ? error.message
      : "Could not start the PayPal checkout. Please try again.");
  }
}

async function setUpPayPalSdk(config) {
  try {
    const sdkInstance = await window.paypal.createInstance({
      clientId: config.client_id,
      components: ["paypal-payments"],
      pageType: "checkout",
    });
    const methods = await sdkInstance.findEligibleMethods({ currencyCode: config.product.currency });
    if (!methods.isEligible("paypal")) {
      paypalSetupError = "PayPal checkout is not available for this setup.";
      updatePaymentGate();
      return;
    }
    const session = sdkInstance.createPayPalOneTimePaymentSession({
      onApprove: handleApprove,
      onCancel: handleCancel,
      onError: handleError,
    });
    payButton.addEventListener("click", () => onPayClick(session));
    paypalReady = true;
  } catch (error) {
    console.error("PayPal SDK setup failed:", error);
    paypalSetupError = "PayPal could not be set up. Open the browser console (F12) for details.";
  }
  updatePaymentGate();
}

async function initPayPal() {
  let config = null;
  try {
    const response = await fetch("/api/paypal/config");
    config = await response.json();
  } catch (error) {
    paypalSetupError = "Could not load payment settings.";
    updatePaymentGate();
    return;
  }
  payProduct.textContent = "Demo product: " + config.product.name + ", " +
    config.product.amount + " " + config.product.currency + " (test money)";
  if (!config.configured) {
    paypalSetupError = "PayPal sandbox is not configured on the server.";
    updatePaymentGate();
    return;
  }
  const script = document.createElement("script");
  script.src = "https://www.sandbox.paypal.com/web-sdk/v6/core";
  script.async = true;
  script.onload = () => setUpPayPalSdk(config);
  script.onerror = () => {
    paypalSetupError = "Could not load PayPal. Check your internet connection.";
    updatePaymentGate();
  };
  document.head.append(script);
}

// ------------------------------------------------------------- form wiring

function resetForNewCheck() {
  currentAssessment = null;
  ackCheckbox.checked = false;
  clearPayError();
  payResult.hidden = true;
  updatePaymentGate();
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
  resetForNewCheck();
  urlInput.focus();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  resultSection.hidden = true;
  resetForNewCheck();

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
    currentAssessment = data.assessment;
    updatePaymentGate();
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

updatePaymentGate();
initPayPal();