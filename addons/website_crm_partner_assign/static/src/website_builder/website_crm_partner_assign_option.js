import { useState } from "@web/owl2/utils";
import { BaseOptionComponent } from "@html_builder/core/base_option_component";
import { onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

export class WebsiteCRMPartnersPageOption extends BaseOptionComponent {
    static id = "website_crm_partners_page_option"
    static template = "website_crm_partner_assign.PartnersPageOption";
    static hasApiKeyCache = null;

    setup() {
        super.setup();
        this.googleMaps = useService("google_maps");
        this.state = useState({
            has_google_maps_api_key: false,
        });

        onMounted(async () => {
            if (WebsiteCRMPartnersPageOption.hasApiKeyCache !== null) {
                this.state.has_google_maps_api_key = WebsiteCRMPartnersPageOption.hasApiKeyCache;
                return;
            }

            const hasKey = !!(await this.googleMaps.getGMapsAPIKey(true));
            this.state.has_google_maps_api_key = hasKey;

            if (hasKey) {
                WebsiteCRMPartnersPageOption.hasApiKeyCache = true;
            }
        });
    }
}

registry.category("website-options").add(WebsiteCRMPartnersPageOption.id, WebsiteCRMPartnersPageOption);

