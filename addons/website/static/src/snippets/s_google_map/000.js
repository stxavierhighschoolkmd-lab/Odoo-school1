/** @odoo-module **/
/* global google */

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.GoogleMap = publicWidget.Widget.extend({
    selector: '.s_google_map',
    disabledInEditableMode: false,

    /**
     * @override
     */
    async start() {
        await this._super(...arguments);

        if (typeof google !== 'object' || typeof google.maps !== 'object') {
            await new Promise(resolve => {
                this.trigger_up('gmap_api_request', {
                    editableMode: this.editableMode,
                    onSuccess: () => resolve(),
                });
            });
        }

        const { Map } = await google.maps.importLibrary("maps");
        const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");

        // Default options, will be overwritten by the user
        const myOptions = {
            zoom: 12,
            center: new google.maps.LatLng(50.854975, 4.3753899),
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            panControl: false,
            zoomControl: false,
            mapTypeControl: false,
            streetViewControl: false,
            scrollwheel: false,
            mapId: this.el.dataset.mapId || "DEMO_MAP_ID",
        };

        // Render Map
        const mapC = this.$('.map_container');
        const map = new Map(mapC.get(0), myOptions);

        // Update GPS position
        const p = this.el.dataset.mapGps.substring(1).slice(0, -1).split(',');
        const gps = new google.maps.LatLng(p[0], p[1]);
        map.setCenter(gps);

        // Update Map on screen resize
        window.addEventListener('resize', () => {
            map.setCenter(gps);
        });

        // Create Marker & Infowindow
        const markerOptions = {
            map: map,
            position: new google.maps.LatLng(p[0], p[1])
        };
        if (this.el.dataset.pinStyle === 'flat') {
            const iconImgEl = document.createElement("img");
            iconImgEl.src = "/website/static/src/img/snippets_thumbs/s_google_map_marker.png";
            iconImgEl.alt = "Marker";
            markerOptions.content = iconImgEl;
        }
        new AdvancedMarkerElement(markerOptions);

        map.setMapTypeId(google.maps.MapTypeId[this.el.dataset.mapType]); // Update Map Type
        map.setZoom(parseInt(this.el.dataset.mapZoom)); // Update Map Zoom
    },

    /**
     * @override
     */
    destroy() {
        this._super(...arguments);
        this.$(".map_container").empty();
    },
});
