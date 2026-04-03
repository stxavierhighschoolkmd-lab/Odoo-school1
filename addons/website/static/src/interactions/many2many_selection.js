import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class Many2ManySelection extends Interaction {
    static selector = ".s_website_form_m2m_selection";

    dynamicContent = {
        ".dropdown-item": { "t-on-click": this.onOptionClick },
        ".s_website_form_m2m_pill_remove": { "t-on-click": this.onPillRemove },
    };

    setup() {
        this.selectEl = this.el.querySelector("select.s_website_form_input");
        this.pillsContainer = this.el.querySelector(".s_website_form_m2m_pills_container");
        this.initialPillsHTML = this.pillsContainer.innerHTML;
        this.initialSelectedStates = [...this.selectEl.options].map((opt) =>
            opt.hasAttribute("selected")
        );
        this.initialCheckboxStates = [
            ...this.el.querySelectorAll(".dropdown-item input[type=checkbox]"),
        ].map((cb) => cb.hasAttribute("checked"));
        this.pillsContainer.dataset.bsToggle = "dropdown";
        this.pillsContainer.dataset.bsAutoClose = "outside";
        this.bsDropdown = Dropdown.getOrCreateInstance(this.pillsContainer);
        this.resizeObserver = new ResizeObserver(() => this.onPillsContainerResize());
        this.resizeObserver.observe(this.pillsContainer);
        this.registerCleanup(() => {
            this.resizeObserver.disconnect();
            this.bsDropdown.dispose();
            this.pillsContainer.removeAttribute("data-bs-toggle");
            this.pillsContainer.removeAttribute("data-bs-auto-close");
            this.pillsContainer.innerHTML = this.initialPillsHTML;
            [...this.selectEl.options].forEach((opt, i) => {
                opt.selected = this.initialSelectedStates[i];
            });
            const checkboxes = this.el.querySelectorAll(".dropdown-item input[type=checkbox]");
            checkboxes.forEach((cb, i) => {
                cb.checked = this.initialCheckboxStates[i];
            });
        });
    }

    /**
     * Toggles the selected state of an option and updates the corresponding
     * pill in the pills container. Dispatches a change event on the hidden
     * select element to notify the form of the value change.
     *
     * @param {string} value
     * @param {boolean} selected
     */
    toggleValue(value, selected) {
        const optionEl = this.selectEl.querySelector(
            `option[value="${CSS.escape(String(value))}"]`
        );
        const checkboxEl = this.el.querySelector(
            `.dropdown-item[data-value="${CSS.escape(String(value))}"] input[type=checkbox]`
        );
        optionEl.selected = selected;
        checkboxEl.checked = selected;
        if (selected) {
            this.addPill(optionEl);
        } else {
            this.removePill(value);
        }
        this.updatePlaceholder();
        this.selectEl.dispatchEvent(new Event("change", { bubbles: true }));
    }

    /**
     * Shows or hides the placeholder text depending on whether any pills
     * are present in the container.
     */
    updatePlaceholder() {
        const placeholderEl = this.pillsContainer.querySelector(".s_website_form_m2m_placeholder");
        const hasPills = !!this.pillsContainer.querySelector(".s_website_form_m2m_pill");
        placeholderEl.classList.toggle("d-none", hasPills);
    }

    /**
     * Handles clicking on a dropdown item to toggle its selection state.
     *
     * @param {Event} ev
     */
    onOptionClick(ev) {
        ev.preventDefault();
        const dropdownItemEl = ev.currentTarget;
        const checkboxEl = dropdownItemEl.querySelector("input[type=checkbox]");
        this.toggleValue(dropdownItemEl.dataset.value, !checkboxEl.checked);
    }

    /**
     * Handles clicking the remove button on a pill to deselect the
     * corresponding option.
     *
     * @param {Event} ev
     */
    onPillRemove(ev) {
        ev.stopPropagation();
        const pillEl = ev.currentTarget.closest(".s_website_form_m2m_pill");
        this.toggleValue(pillEl.dataset.value, false);
    }

    /**
     * Inserts a pill element for the given option before the placeholder.
     *
     * @param {HTMLOptionElement} optionEl
     */
    addPill(optionEl) {
        const pillEl = document.createElement("span");
        pillEl.className = "s_website_form_m2m_pill badge rounded-pill text-bg-primary";
        pillEl.dataset.value = optionEl.value;
        const textEl = document.createElement("span");
        textEl.textContent = optionEl.text;
        pillEl.appendChild(textEl);
        const removeBtnEl = document.createElement("i");
        removeBtnEl.className = "s_website_form_m2m_pill_remove fa fa-times ms-1 cursor-pointer";
        pillEl.appendChild(removeBtnEl);
        const placeholderEl = this.pillsContainer.querySelector(".s_website_form_m2m_placeholder");
        placeholderEl.insertAdjacentElement("beforebegin", pillEl);
    }

    /**
     * Removes the pill element matching the given value from the container.
     *
     * @param {string} value
     */
    removePill(value) {
        this.pillsContainer
            .querySelector(`.s_website_form_m2m_pill[data-value="${CSS.escape(String(value))}"]`)
            .remove();
    }

    /**
     * Updates the Bootstrap dropdown position when the pills container
     * changes size (e.g. after adding/removing pills).
     */
    onPillsContainerResize() {
        requestAnimationFrame(() => {
            if (!this.isDestroyed && this.bsDropdown) {
                this.bsDropdown.update();
            }
        });
    }
}

registry.category("public.interactions").add("website.many2many_selection", Many2ManySelection);
