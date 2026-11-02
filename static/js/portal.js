document.addEventListener("DOMContentLoaded", () => {
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
});
