import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class Many2ManyDropdownInteraction extends Interaction {
    static selector = ".s_website_form_m2m_dropdown";

    dynamicContent = {
        ".dropdown-item": { "t-on-click": this.onOptionClick },
        ".s_website_form_m2m_pill_remove": { "t-on-click": this.onPillRemove },
    };

    setup() {
        this.selectEl = this.el.querySelector("select.s_website_form_input");
        this.pillsContainer = this.el.querySelector(".s_website_form_m2m_pills_container");
        this.pillsContainer.dataset.bsToggle = "dropdown";
        this.pillsContainer.dataset.bsAutoClose = "outside";
        this.bsDropdown = window.Dropdown.getOrCreateInstance(this.pillsContainer);
        this.resizeObserver = new ResizeObserver(() => this.refreshOpenDropdownPosition());
        this.resizeObserver.observe(this.pillsContainer);
        this.registerCleanup(() => {
            this.resizeObserver.disconnect();
            this.bsDropdown.dispose();
            this.pillsContainer.removeAttribute("data-bs-toggle");
            this.pillsContainer.removeAttribute("data-bs-auto-close");
        });
    }

    queryOptionByValue(value) {
        return this.selectEl.querySelector(`option[value="${CSS.escape(String(value))}"]`);
    }

    refreshOpenDropdownPosition() {
        requestAnimationFrame(() => {
            if (!this.isDestroyed && this.bsDropdown) {
                this.bsDropdown.update();
            }
        });
    }

    toggleOption(optionEl, checkboxEl) {
        optionEl.selected = !optionEl.selected;
        checkboxEl.checked = optionEl.selected;
    }

    updatePlaceholder() {
        const placeholderEl = this.pillsContainer.querySelector(".s_website_form_m2m_placeholder");
        const hasPills = !!this.pillsContainer.querySelector(".s_website_form_m2m_pill");
        placeholderEl.classList.toggle("d-none", hasPills);
    }

    onOptionClick(ev) {
        ev.preventDefault();
        const dropdownEl = ev.currentTarget;
        const value = dropdownEl.dataset.value;
        const option = this.queryOptionByValue(value);
        const checkboxEl = dropdownEl.querySelector("input[type='checkbox']");
        this.toggleOption(option, checkboxEl);
        if (option.selected) {
            this.addPill(option);
        } else {
            this.removePill(option.value);
        }
        this.updatePlaceholder();
        this.refreshOpenDropdownPosition();
        this.selectEl.dispatchEvent(new Event("change", { bubbles: true }));
    }

    onPillRemove(ev) {
        ev.stopPropagation();
        const pill = ev.currentTarget.closest(".s_website_form_m2m_pill");
        const value = pill.dataset.value;
        if (value) {
            const option = this.queryOptionByValue(value);
            const checkboxEl = this.el.querySelector(
                `.dropdown-item[data-value="${CSS.escape(String(value))}"] input[type=checkbox]`
            );
            this.toggleOption(option, checkboxEl);
            this.removePill(value);
            this.updatePlaceholder();
            this.refreshOpenDropdownPosition();
            this.selectEl.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }

    addPill(option) {
        const spanEl = document.createElement("span");
        spanEl.className = "s_website_form_m2m_pill badge rounded-pill text-bg-primary";
        spanEl.dataset.value = option.value;
        const textEl = document.createElement("span");
        textEl.textContent = option.text;
        spanEl.appendChild(textEl);
        const removeBtnEl = document.createElement("i");
        removeBtnEl.className = "s_website_form_m2m_pill_remove fa fa-times ms-1 cursor-pointer";
        spanEl.appendChild(removeBtnEl);
        const placeholderEl = this.pillsContainer.querySelector(".s_website_form_m2m_placeholder");
        placeholderEl.insertAdjacentElement("beforebegin", spanEl);
    }

    removePill(value) {
        this.pillsContainer
            .querySelector(`.s_website_form_m2m_pill[data-value="${CSS.escape(String(value))}"]`)
            .remove();
    }
}

registry
    .category("public.interactions")
    .add("website.many2many_dropdown", Many2ManyDropdownInteraction);
