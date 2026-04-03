import { Component } from "@odoo/owl";
import { useSelfOrder } from "@pos_self_order/app/services/self_order_service";
import { ProductNameWidget } from "@pos_self_order/app/components/product_name_widget/product_name_widget";
import { flyToCart } from "@pos_self_order/app/utils/ui_animations";

export class ProductCard extends Component {
    static template = "pos_self_order.ProductCard";
    static props = ["product", "onClickCallback?", "qty?"];
    static components = { ProductNameWidget };

    setup() {
        this.selfOrder = useSelfOrder();
    }

    get isProductAvailable() {
        return this.selfOrder.isProductAvailable(this.props.product);
    }

    get isProductSnoozed() {
        return this.selfOrder.snoozedProductTracker.isProductSnoozed(this.props.product);
    }

    showComboSelectionPage() {
        const product = this.props.product;
        const selectedCombos = [];
        for (const combo of product.combo_ids) {
            const { combo_item_ids } = combo;
            if (
                combo_item_ids.length > 1 ||
                combo.qty_max > 1 ||
                combo_item_ids[0]?.product_id.isConfigurable()
            ) {
                return { show: true, selectedCombos: [] };
            }
            const item = this.selfOrder.models["product.combo.item"].get(combo_item_ids[0].id);
            selectedCombos.push({
                combo_item_id: item,
                configuration: {
                    attribute_custom_values: [],
                    attribute_value_ids: [],
                    price_extra: 0,
                },
            });
        }
        return { show: false, selectedCombos };
    }

    selectProduct(target) {
        const historyState = history.state;
        const product = this.props.product;
        if (!product.self_order_available || !this.isProductAvailable || this.isProductSnoozed) {
            return;
        }

        this.props.onClickCallback && this.props.onClickCallback(product);
        const router = this.selfOrder.router;
        if (product.isCombo()) {
            const { show, selectedCombos } = this.showComboSelectionPage();
            if (show) {
                router.navigate("combo_selection", { id: product.id }, historyState);
                return;
            }

            flyToCart(target);
            this.selfOrder.addToCart(
                product,
                1,
                "",
                {},
                {},
                selectedCombos.map((combo) => ({
                    ...combo,
                    qty: 1,
                }))
            );
            return;
        }

        if (this.selfOrder.ordering && !product.isConfigurable()) {
            flyToCart(target);
            this.selfOrder.addToCart(product, 1);
        }

        if (product.isConfigurable()) {
            router.navigate("product", { id: product.id }, historyState);
        } else if (product.pos_optional_product_ids.length && !historyState?.redirectPage) {
            router.navigate("optional_product", { id: product.id }, historyState);
        }
    }
}
