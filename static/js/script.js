document.addEventListener("DOMContentLoaded", () => {
    const goalTabs = document.querySelectorAll(".goal-tab");
    const goalPanels = document.querySelectorAll(".goal-panel");
    const goalTypeSelect = document.querySelector(".goal-type-select");

    const setActiveGoalType = (goalType) => {
        goalTabs.forEach((tab) => {
            const isActive = tab.dataset.goalTab === goalType;
            tab.classList.toggle("active", isActive);
        });

        goalPanels.forEach((panel) => {
            const isActive = panel.dataset.goalPanel === goalType;
            panel.classList.toggle("active", isActive);
        });

        if (goalTypeSelect) {
            goalTypeSelect.value = goalType;
        }
    };

    goalTabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            setActiveGoalType(tab.dataset.goalTab);
        });
    });

    if (goalTypeSelect) {
        goalTypeSelect.addEventListener("change", (event) => {
            setActiveGoalType(event.target.value);
        });
    }

    const autoSubmitForms = document.querySelectorAll(".auto-submit-form");
    autoSubmitForms.forEach((form) => {
        const checkbox = form.querySelector('input[type="checkbox"]');
        if (checkbox) {
            checkbox.addEventListener("change", () => {
                form.submit();
            });
        }
    });

    const deleteForms = document.querySelectorAll(".delete-form");
    deleteForms.forEach((form) => {
        form.addEventListener("submit", (event) => {
            const shouldDelete = window.confirm("Delete this goal?");
            if (!shouldDelete) {
                event.preventDefault();
            }
        });
    });

    const flashMessages = document.querySelectorAll(".flash-message");
    flashMessages.forEach((message) => {
        setTimeout(() => {
            message.style.opacity = "0";
            message.style.transform = "translateY(-6px)";
            setTimeout(() => {
                message.remove();
            }, 300);
        }, 3500);
    });

    if (goalTabs.length > 0) {
        setActiveGoalType("daily");
    }
});
