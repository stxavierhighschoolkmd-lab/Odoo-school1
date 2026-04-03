import { CrmControlPanel } from "@crm/views/crm_control_panel/crm_control_panel";
import { CrmGraphModel } from "@crm/views/crm_graph/crm_graph_model";
import { CrmSearchModel } from "@crm/views/crm_search_model";
import { graphView } from "@web/views/graph/graph_view";
import { registry } from "@web/core/registry";

export const crmGraphView = {
    ...graphView,
    ControlPanel: CrmControlPanel,
    Model: CrmGraphModel,
    SearchModel: CrmSearchModel,
}

registry.category("views").add("crm_graph", crmGraphView);
