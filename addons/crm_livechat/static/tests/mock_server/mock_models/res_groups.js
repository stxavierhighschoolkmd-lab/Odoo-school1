import { livechatModels } from "@im_livechat/../tests/livechat_test_helpers";
import { serverState } from "@web/../tests/web_test_helpers";

export class ResGroups extends livechatModels.ResGroups {
    _records = [
        ...this._records,
        {
            id: serverState.groupSalesTeamId,
            name: "Sale Salesman",
            privilege_id: false,
        },
    ];
}
