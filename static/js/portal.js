document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-sidebar-toggle]").forEach((control) => {
    control.addEventListener("click", () => {
      const open = document.body.classList.toggle("sidebar-open");
      document.querySelectorAll("[data-sidebar-toggle]").forEach((item) => {
        item.setAttribute("aria-expanded", String(open));
      });
    });
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) {
        event.preventDefault();
        return;
      }
      const button = form.querySelector('button[type="submit"]');
      if (button) {
        button.disabled = true;
        button.textContent = form.dataset.loadingLabel || "Procesando…";
      }
    });
  });

  const benefitType = document.querySelector("#id_tipo_beneficio");
  const prefix = document.querySelector("[data-benefit-prefix]");
  const suffix = document.querySelector("[data-benefit-suffix]");
  if (benefitType && prefix && suffix) {
    const updateBenefitAffix = () => {
      const percentage = benefitType.value === "PORCENTAJE";
      prefix.hidden = percentage;
      suffix.hidden = !percentage;
    };
    benefitType.addEventListener("change", updateBenefitAffix);
    updateBenefitAffix();
  }

  const workbookInput = document.querySelector(".upload-field input[type='file']");
  if (workbookInput) {
    const uploadLabel = workbookInput.closest(".upload-field");
    const title = uploadLabel.querySelector("strong");
    workbookInput.addEventListener("change", () => {
      title.textContent = workbookInput.files.length
        ? workbookInput.files[0].name
        : "Seleccionar archivo .xlsx";
    });
  }
});
