import {
    defineLivechatModels,
    loadDefaultEmbedConfig,
} from "@im_livechat/../tests/livechat_test_helpers";
import { click, start, startServer } from "@mail/../tests/mail_test_helpers";
import { describe, expect, mockDate, test } from "@odoo/hoot";
import { press, waitFor } from "@odoo/hoot-dom";
import { contains, getService, onRpc, serverState } from "@web/../tests/web_test_helpers";

import { expirableStorage } from "@im_livechat/core/common/expirable_storage";

describe.current.tags("desktop");
defineLivechatModels();

test("Handle livechat history command", async () => {
    mockDate("2023-06-07T06:07:00");
    const pyEnv = await startServer();
    await loadDefaultEmbedConfig();
    expirableStorage.setItem(
        "im_livechat_history",
        JSON.stringify([
            "/legacy-page",
            { url: "/superheroes/batman", title: "Batman", visited_at: "2023-06-07 06:07:00" },
        ]),
        60 * 60 * 24
    );
    onRpc("/im_livechat/history", async (request) => {
        expect.step(new URL(request.url).pathname);
        const { params } = await request.json();
        expect(params.page_history).toEqual([
            {
                title: "/legacy-page",
                url: "/legacy-page",
                visited_at: null,
            },
            {
                url: "/superheroes/batman",
                title: "Batman",
                visited_at: "2023-06-07 06:07:00",
            },
            {
                url: "/",
                title: "/",
                visited_at: "2023-06-07 06:07:00",
            },
        ]);
        return true;
    });
    await start({ authenticateAs: false });
    await click(".o-livechat-LivechatButton");
    await contains(".o-mail-Composer-input").edit("Hello World!", { confirm: false });
    await press("Enter");
    await waitFor(".o-mail-Message:contains(Hello World!)");
    const thread = Object.values(getService("mail.store")["mail.thread"].records).at(-1);
    const guestId = pyEnv.cookie.get("dgid");
    const [guest] = pyEnv["mail.guest"].read(guestId);
    pyEnv["bus.bus"]._sendone(guest, "im_livechat.history_command", {
        id: thread.id,
        partner_id: serverState.partnerId,
    });
    await expect.waitForSteps(["/im_livechat/history"]);
});
