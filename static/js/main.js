
document.addEventListener("DOMContentLoaded", function () {

    // Automatically close flash messages after 5 seconds.
    const alerts = document.querySelectorAll(".alert-dismissible");

    alerts.forEach(function (alertElement) {
        window.setTimeout(function () {
            if (alertElement.isConnected) {
                const closeButton = alertElement.querySelector(".btn-close");

                if (closeButton) {
                    closeButton.click();
                }
            }
        }, 5000);
    });

    // Prevent accidental multiple submissions.
    const forms = document.querySelectorAll("form");

    forms.forEach(function (form) {
        form.addEventListener("submit", function (event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                form.reportValidity();
                return;
            }

            const submitButton = form.querySelector(
                'button[type="submit"], input[type="submit"]'
            );

            if (submitButton && !form.dataset.confirmed) {
                submitButton.disabled = true;
                submitButton.dataset.originalText =
                    submitButton.textContent;

                submitButton.textContent = "Please wait...";
            }
        });
    });

    // Confirm actions that could change or disable data.
    const confirmForms = document.querySelectorAll(
        'form[onsubmit*="confirm("]'
    );

    confirmForms.forEach(function (form) {
        form.addEventListener("submit", function (event) {
            // The inline confirmation in the template handles this action.
            // Do not add a second confirmation dialog here.
        });
    });

    // Add a small visual indication to food images that fail to load.
    document.querySelectorAll("img").forEach(function (image) {
        image.addEventListener("error", function () {
            image.classList.add("image-load-error");
        });
    });

});
