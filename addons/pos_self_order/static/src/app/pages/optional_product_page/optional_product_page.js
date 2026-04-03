import { Component, useRef, useState } from "@odoo/owl";
import { useSelfOrder } from "@pos_self_order/app/services/self_order_service";
import { useService } from "@web/core/utils/hooks";
import { useScrollShadow } from "../../utils/scroll_shadow_hook";
import { useStickyTitleObserver } from "@pos_self_order/app/utils/sticky_title_observer";
import { ProductCard } from "@pos_self_order/app/components/product_card/product_card";
import { browser } from "@web/core/browser/browser";

export class OptionalProductPage extends Component {
    static template = "pos_self_order.OptionalProductPage";
    static components = { ProductCard };
    static props = ["productTemplate"];

    setup() {
        this.selfOrder = useSelfOrder();
        this.router = useService("router");

        if (!this.productTemplate || !this.optionalProducts.length) {
            this.goBack();
            return;
        }

        this.state = useState({
            showStickyTitle: false,
            optionalProductQtyById: history.state.optionalProductQtys || {},
        });

        this.scrollContainerRef = useRef("scrollContainer");
        this.productNameRef = useRef("productName");
        this.scrollShadow = useScrollShadow(this.scrollContainerRef);

        useStickyTitleObserver(
            "productName",
            (isSticky) => (this.state.showStickyTitle = isSticky)
        );
    }

    get productTemplate() {
        return this.props.productTemplate;
    }

    get optionalProducts() {
        return this.productTemplate.pos_optional_product_ids;
    }

    get isOptionalProductSelected() {
        return Object.values(this.state.optionalProductQtyById).some((qty) => qty > 0);
    }

    onClickOptionalProduct(product) {
        setTimeout(() => {
            history.pushState(
                {
                    redirectPage: "optional_product",
                    params: { id: this.productTemplate.id },
                    state: {
                        optionalProductQtys: { ...this.state.optionalProductQtyById },
                    },
                },
                "",
                new URL(browser.location.href)
            );
            const newQty = (this.state.optionalProductQtyById[product.id] || 0) + 1;
            this.state.optionalProductQtyById[product.id] = newQty;
        }, 0);
    }

    goBack() {
        this.router.navigate("product_list");
    }
}
