import { registry } from "@web/core/registry";
import { rpc } from '@web/core/network/rpc';
import { Interaction } from "@web/public/interaction";

export const recordRE = /^([^(]+)\((\d+)/;

export class OdooTracker extends Interaction {
    static selector = "#wrapwrap";

    start() {
        const docEl = document.documentElement;
        const trackingEnabled = docEl.dataset.trackingEnabled;
        const mainObjectRepr = docEl.dataset.mainObject;
        const matches = mainObjectRepr.match(recordRE);
        if (trackingEnabled && matches) {
            rpc('/website/odoo_track', {
                url: window.location.href,
                res_model: matches[1],
                res_id: matches[2],
            });
        }
    }
}


registry.category("public.interactions").add("website.tracker", OdooTracker);
