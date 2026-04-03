import { kanbanView } from "@web/views/kanban/kanban_view";
import { registry } from "@web/core/registry";

import { ProductImageKanbanRenderer } from "./kanban_renderer";

export const productImageKanbanView = {
    ...kanbanView,
    Renderer: ProductImageKanbanRenderer,
};

console.log(ProductImageKanbanRenderer);


registry.category("views").add("product_kanban_image", productImageKanbanView);
