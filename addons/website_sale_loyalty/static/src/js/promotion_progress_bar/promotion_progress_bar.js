import { Component } from "@odoo/owl";
import { formatCurrency } from "@web/core/currency";

export class PromotionProgressBar extends Component {
    static template = "website_sale_loyalty.PromotionProgressBar";
    static props = {
        bars: {
            type: Array,
            element: {
                type: Object,
                shape: {
                    program_id: Number,
                    reward_name: String,
                    minimum_amount: Number,
                    progress: Number,
                    just_matched: { type: Boolean, optional: true },
                },
            },
        },
        currency_id: Number,
    };

    getFormattedAmount(amount) {
        return formatCurrency(amount, this.props.currency_id);
    }
}
