(function () {
  "use strict";

  const config = document.getElementById("session-timeout-config");
  const warning = document.getElementById("session-timeout-warning");
  const continueButton = document.getElementById("session-timeout-continue");
  const countdown = document.getElementById("session-timeout-countdown");
  if (!config || !warning || !continueButton || !countdown) {
    return;
  }

  const timeoutSeconds = Number(config.dataset.sessionTimeoutSeconds);
  const activityUrl = config.dataset.sessionActivityUrl;
  const loginUrl = config.dataset.sessionLoginUrl;
  const warningMs = Math.min(60000, Math.max(5000, timeoutSeconds * 200));
  const activityStorageKey = "cargotrack.session.activity";
  const channel = "BroadcastChannel" in window
    ? new BroadcastChannel("cargotrack-session")
    : null;
  let deadline = Number(config.dataset.sessionDeadlineMs);
  let heartbeatTimer = null;
  let lastHeartbeatAt = 0;
  let redirecting = false;

  function getCsrfToken() {
    const input = document.querySelector("input[name='csrfmiddlewaretoken']");
    if (input) {
      return input.value;
    }
    const cookie = document.cookie.split(";").map(function (part) {
      return part.trim();
    }).find(function (part) {
      return part.startsWith("csrftoken=");
    });
    return cookie ? decodeURIComponent(cookie.slice("csrftoken=".length)) : "";
  }

  function redirectToLogin() {
    if (redirecting) {
      return;
    }
    redirecting = true;
    const next = window.location.pathname + window.location.search;
    window.location.replace(loginUrl + "?next=" + encodeURIComponent(next));
  }

  function notifyOtherTabs(message) {
    if (channel) {
      channel.postMessage(message);
    } else {
      window.localStorage.setItem(activityStorageKey, JSON.stringify(message));
    }
  }

  function updateDeadline(nextDeadline, notify) {
    if (!Number.isFinite(nextDeadline)) {
      return;
    }
    deadline = nextDeadline;
    if (notify) {
      notifyOtherTabs({ type: "activity", deadline: deadline });
    }
  }

  function formatCountdown(milliseconds) {
    const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
    return String(Math.floor(seconds / 60)).padStart(2, "0") + ":" +
      String(seconds % 60).padStart(2, "0");
  }

  function updateCountdown() {
    const remaining = deadline - Date.now();
    if (remaining <= 0) {
      redirectToLogin();
      return;
    }
    if (remaining <= warningMs) {
      countdown.textContent = formatCountdown(remaining);
      if (warning.hidden) {
        warning.hidden = false;
        continueButton.focus();
      }
    } else {
      warning.hidden = true;
    }
  }

  function sendActivity() {
    window.clearTimeout(heartbeatTimer);
    heartbeatTimer = null;
    lastHeartbeatAt = Date.now();
    fetch(activityUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: "{}",
    }).then(function (response) {
      if (response.status === 401 || response.redirected) {
        redirectToLogin();
        return null;
      }
      if (!response.ok) {
        throw new Error("No se pudo actualizar la actividad de la sesión.");
      }
      return response.json();
    }).then(function (data) {
      if (data && data.authenticated) {
        updateDeadline(Number(data.deadline_ms), true);
        warning.hidden = true;
      }
    }).catch(function (error) {
      console.error(error);
    });
  }

  function scheduleActivity() {
    if (redirecting || heartbeatTimer) {
      return;
    }
    const elapsed = Date.now() - lastHeartbeatAt;
    const wait = elapsed >= 15000 ? 500 : Math.max(500, 15000 - elapsed);
    heartbeatTimer = window.setTimeout(sendActivity, wait);
  }

  ["click", "input", "keydown", "scroll", "submit", "touchstart"].forEach(function (eventName) {
    document.addEventListener(eventName, function (event) {
      if (
        event.target instanceof Element
        && event.target.closest(
          "#session-timeout-warning, form[action*='/accounts/logout/']"
        )
      ) {
        return;
      }
      scheduleActivity();
    }, { passive: eventName === "scroll" || eventName === "touchstart" });
  });

  continueButton.addEventListener("click", sendActivity);
  document.querySelectorAll("form[action*='/accounts/logout/']").forEach(function (form) {
    form.addEventListener("submit", function () {
      notifyOtherTabs({ type: "logout" });
    });
  });

  function onCrossTabMessage(message) {
    if (message?.type === "logout") {
      redirectToLogin();
    } else if (message?.type === "activity") {
      updateDeadline(Math.max(deadline, Number(message.deadline)), false);
    }
  }

  if (channel) {
    channel.addEventListener("message", function (event) {
      onCrossTabMessage(event.data);
    });
  } else {
    window.addEventListener("storage", function (event) {
      if (event.key === activityStorageKey && event.newValue) {
        try {
          onCrossTabMessage(JSON.parse(event.newValue));
        } catch (error) {
          console.error("No se pudo sincronizar la sesión entre pestañas.", error);
        }
      }
    });
  }

  document.addEventListener("visibilitychange", updateCountdown);
  window.setInterval(updateCountdown, 1000);
  updateCountdown();
})();
