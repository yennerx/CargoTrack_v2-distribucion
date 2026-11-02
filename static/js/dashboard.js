(() => {
  const form = document.getElementById("dashboard-preferences-form");
  const orderList = document.getElementById("dashboard-widget-order");
  const widgets = document.getElementById("dashboard-widgets");
  if (!form || !orderList || !widgets) return;

  const status = document.getElementById("dashboard-preference-status");
  const cards = new Map(
    [...widgets.querySelectorAll("[data-widget-id]")].map((card) => [
      card.dataset.widgetId,
      card,
    ]),
  );
  const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]")?.value;

  const synchronize = () => {
    for (const item of orderList.querySelectorAll("[data-widget-id]")) {
      const checkbox = item.querySelector(".dashboard-widget-visibility");
      const card = cards.get(item.dataset.widgetId);
      if (!card) continue;
      card.hidden = !checkbox.checked;
      widgets.append(card);
    }
  };

  orderList.addEventListener("click", (event) => {
    const button = event.target.closest(".dashboard-move-widget");
    if (!button) return;
    const item = button.closest("[data-widget-id]");
    const sibling = button.dataset.direction === "up" ? item.previousElementSibling : item.nextElementSibling;
    if (!sibling) return;
    if (button.dataset.direction === "up") orderList.insertBefore(item, sibling);
    else orderList.insertBefore(sibling, item);
    synchronize();
  });

  orderList.addEventListener("change", (event) => {
    if (event.target.matches(".dashboard-widget-visibility")) synchronize();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const items = [...orderList.querySelectorAll("[data-widget-id]")];
    const visibleWidgets = items
      .filter((item) => item.querySelector(".dashboard-widget-visibility").checked)
      .map((item) => item.dataset.widgetId);
    if (!visibleWidgets.length) {
      status.textContent = "Mantén al menos un indicador visible.";
      return;
    }

    status.textContent = "Guardando…";
    try {
      const response = await fetch(form.dataset.preferenceUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          widget_order: items.map((item) => item.dataset.widgetId),
          visible_widgets: visibleWidgets,
        }),
      });
      if (!response.ok) throw new Error("No fue posible guardar las preferencias.");
      status.textContent = "Preferencias guardadas.";
    } catch {
      status.textContent = "No se guardaron las preferencias. Intenta nuevamente.";
    }
  });
})();
