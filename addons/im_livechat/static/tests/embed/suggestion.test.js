import { LivechatButton } from "@im_livechat/embed/common/livechat_button";
import {
    defineLivechatModels,
    loadDefaultEmbedConfig,
} from "@im_livechat/../tests/livechat_test_helpers";
import { describe, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { click, contains, insertText, start } from "@mail/../tests/mail_test_helpers";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
defineLivechatModels();

test("Visitor cannot use @ mentions in livechat", async () => {
    await loadDefaultEmbedConfig();
    await start({ authenticateAs: false });
    await mountWithCleanup(LivechatButton);
    await click(".o-livechat-LivechatButton");
    await contains(".o-mail-Message", { text: "Hello, how may I help you?" });
    await insertText(".o-mail-Composer-input", "@");
    await animationFrame();
    await animationFrame();
    await animationFrame();
    await contains(".o-mail-Composer-suggestion", { count: 0 });
});
