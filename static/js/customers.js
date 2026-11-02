(function () {
  "use strict";

  const addButton = document.getElementById("add-contact");
  const formsContainer = document.getElementById("contact-forms");
  const emptyTemplate = document.getElementById("empty-contact-form");
  const form = addButton && addButton.closest("form");
  const totalForms = form && form.querySelector('input[name$="-TOTAL_FORMS"]');

  if (!addButton || !formsContainer || !emptyTemplate || !totalForms) {
    return;
  }

  addButton.addEventListener("click", function () {
    const formIndex = Number(totalForms.value);
    const formHtml = emptyTemplate.innerHTML.replaceAll("__prefix__", formIndex);
    const wrapper = document.createElement("div");
    wrapper.className = "contact-form border-top pt-3 mt-3";
    wrapper.innerHTML = formHtml;
    formsContainer.appendChild(wrapper);
    totalForms.value = formIndex + 1;
  });
})();
