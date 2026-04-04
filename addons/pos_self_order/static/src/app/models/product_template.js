import { ProductTemplate } from "@point_of_sale/app/models/product_template";
import { patch } from "@web/core/utils/patch";

patch(ProductTemplate.prototype, {
    isConfigurable() {
        return this.attribute_line_ids.map((a) => a.product_template_value_ids).flat().length > 1;
    },
});
