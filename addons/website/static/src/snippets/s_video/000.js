/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.video = publicWidget.Widget.extend({
    selector: ".media_iframe_video",

    /**
     * @override
     */
    start() {
        const iframe = this.el.querySelector("iframe");
        if (!iframe) {
            return this._super(...arguments);
        }
        const src = "//www.youtube.com/embed/nbso3NVz3p8?rel=0&autoplay=0";
        // Update the iframe source only if old the default placeholder video.
        if (iframe.getAttribute("src") === "//www.youtube.com/embed/G8b4UZIcTfg?rel=0&amp;autoplay=0") {
            // TODO: Remove this entire file starting from Odoo 19.0.
            iframe.src = src;  // !compatibility.
            this.el.dataset.oeExpression = src; // !compatibility.
        }

        return this._super(...arguments);
    },
});