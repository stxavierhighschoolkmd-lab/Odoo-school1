import { LinkPopover } from "@html_editor/main/link/link_popover";

export class WebsiteLinkPopover extends LinkPopover {
    setup() {
        super.setup();
        const currentRelValues = this.props.linkElement.rel.split(" ");
        const currentTargetValue = this.props.linkElement.getAttribute("target");
        this.state.advancedAttributeOptions = Object.fromEntries(
            this.props.advancedAttributeOptions.map((option) => [
                option.id,
                {
                    ...option,
                    isChecked:
                        (option.attribute === "rel" && currentRelValues.includes(option.value)) ||
                        currentTargetValue === option.value,
                },
            ])
        );
    }

    prepareLinkParams() {
        const base = super.prepareLinkParams();
        const relValues = [];
        const attributes = { ...base.attributes };
        for (const opt of Object.values(this.state.advancedAttributeOptions)) {
            if (opt.attribute === "rel" && opt.isChecked) {
                relValues.push(opt.value);
            } else {
                attributes[opt.attribute] = opt.isChecked ? opt.value : null;
            }
        }
        attributes.rel = relValues.join(" ");
        return {
            ...base,
            attributes,
        };
    }
}
