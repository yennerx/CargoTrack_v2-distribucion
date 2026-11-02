(function () {
  "use strict";

  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      window.location.reload();
    }
  });

  const shell = document.getElementById("app-shell");
  if (!shell || !document.body.classList.contains("authenticated")) {
    return;
  }

  const toggle = document.getElementById("sidebar-toggle");
  const reset = document.getElementById("sidebar-reset");
  const preferenceUrl = shell.dataset.preferenceUrl;
  const csrfToken = document.querySelector("input[name='csrfmiddlewaretoken']")?.value;
  let saveQueue = Promise.resolve();

  function collapsedSections() {
    return Array.from(shell.querySelectorAll("[data-navigation-section]"))
      .filter(function (panel) {
        return !panel.classList.contains("show");
      })
      .map(function (panel) {
        return panel.dataset.navigationSection;
      });
  }

  function savePreferences() {
    if (!preferenceUrl || !csrfToken) {
      return;
    }
    const payload = {
      collapsed_sections: collapsedSections(),
      sidebar_collapsed: shell.classList.contains("sidebar-collapsed"),
    };
    saveQueue = saveQueue.then(function () {
      return fetch(preferenceUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(payload),
      }).then(function (response) {
        if (!response.ok) {
          throw new Error("No se pudieron guardar las preferencias de navegación.");
        }
      });
    }).catch(function (error) {
      console.error(error);
    });
  }

  function setSidebarCollapsed(collapsed) {
    shell.classList.toggle("sidebar-collapsed", collapsed);
    if (toggle) {
      toggle.setAttribute("aria-expanded", String(!collapsed));
      toggle.setAttribute("aria-label", collapsed ? "Mostrar navegación" : "Minimizar navegación");
      toggle.setAttribute("title", collapsed ? "Mostrar navegación" : "Minimizar navegación");
    }
  }

  if (toggle) {
    toggle.setAttribute("aria-expanded", String(!shell.classList.contains("sidebar-collapsed")));
    toggle.addEventListener("click", function () {
      setSidebarCollapsed(!shell.classList.contains("sidebar-collapsed"));
      savePreferences();
    });
  }

  shell.addEventListener("shown.bs.collapse", function (event) {
    if (event.target.matches("[data-navigation-section]")) {
      savePreferences();
    }
  });
  shell.addEventListener("hidden.bs.collapse", function (event) {
    if (event.target.matches("[data-navigation-section]")) {
      savePreferences();
    }
  });

  if (reset) {
    reset.addEventListener("click", function () {
      setSidebarCollapsed(false);
      shell.querySelectorAll("[data-navigation-section]").forEach(function (panel) {
        window.bootstrap.Collapse.getOrCreateInstance(panel, { toggle: false }).show();
      });
      savePreferences();
    });
  }
})();
