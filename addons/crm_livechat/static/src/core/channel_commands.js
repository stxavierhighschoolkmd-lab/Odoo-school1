import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

registry.category("discuss.channel_commands").add("lead", {
    /**
     * @param {Object} param0
     * @param {import("models").DiscussChannel} param0.channel
     */
    condition: ({ channel }) => channel.isAllowedToCreateLead,
    help: _t("Create a new lead (/lead lead title)"),
    methodName: "execute_command_lead",
});
