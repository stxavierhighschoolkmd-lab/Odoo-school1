import { useDomState } from "@html_builder/core/utils";
import { registry } from "@web/core/registry";
import { BaseOptionComponent } from "@html_builder/core/base_option_component";

export class ClickableBlockOption extends BaseOptionComponent {
    static id = "clickable_block_option";
    static template = "website.ClickableBlockOption";

    setup() {
        super.setup();
        this.state = useDomState((editingElement) => ({
            hasHref: editingElement.querySelector("a.stretched-link")?.hasAttribute("href"),
        }));
    }
}

registry.category("builder-options").add(ClickableBlockOption.id, ClickableBlockOption);
