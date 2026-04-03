import { LinkPopover } from "@html_editor/main/link/link_popover";
import { _t } from "@web/core/l10n/translation";

/**
 * List of paths the URL of which will not have any effect when using the `notracking` option.
 *
 * @constant {string[]}
 */
const NON_TRACKABLE_URLS = ["/unsubscribe_from_list", "/view", "/cards"];

export class MassMailingLinkPopover extends LinkPopover {
    static template = "mass_mailing.MailingLinkPopover";
    static props = {
        ...LinkPopover.props,
    };
    setup() {
        super.setup();
        this.linkElement = this.props.linkElement;
        this.state.noTracking = {
            label: "Disable Link Tracking",
            description: _t("Send the original url instead of wrapping it into a tracking url."),
            isChecked: Boolean(this.linkElement.dataset.noTracking) || false,
        };
    }

    toggleDisableLinkTracking() {
        this.state.noTracking.isChecked = !this.state.noTracking.isChecked;
    }

    shouldDisplayNoTrackingOption() {
        return !NON_TRACKABLE_URLS.includes(this.state.url);
    }

    onClickApply() {
        const relOptions = this.state.relAttributeOptions;
        const relValue = Object.keys(relOptions)
            .filter((key) => relOptions[key].isChecked)
            .join(" ");
        this.state.editing = false;
        this.applyDeducedUrl();
        this.props.onApply(
            this.state.url,
            this.state.label,
            this.classes,
            this.state.linkTarget,
            this.state.attachmentId,
            relValue,
            this.state.noTracking.isChecked ? "1" : "0"
        );
    }
}
