function initializeSignupPhoneCountry() {
    const phoneInput = document.getElementById("telephone");
    const countrySelect = document.getElementById("signupCountry");

    if (!(phoneInput instanceof HTMLInputElement) || !(countrySelect instanceof HTMLSelectElement)) {
        return;
    }

    phoneInput.addEventListener("input", () => {
        const internationalNumber = phoneInput.value.trim().replace(/[^\d+]/g, "");
        if (!internationalNumber.startsWith("+")) {
            return;
        }

        const matchingOption = Array.from(countrySelect.options)
            .filter((option) => option.dataset.callingCode)
            .sort((first, second) =>
                second.dataset.callingCode.length - first.dataset.callingCode.length,
            )
            .find((option) =>
                internationalNumber.startsWith(`+${option.dataset.callingCode}`),
            );

        if (matchingOption) {
            countrySelect.value = matchingOption.value;
        }
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeSignupPhoneCountry, { once: true });
} else {
    initializeSignupPhoneCountry();
}
