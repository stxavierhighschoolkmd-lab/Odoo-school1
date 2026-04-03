import { registry } from "@web/core/registry";
import { CharField } from "@web/views/fields/char/char_field";
import {
    CopyClipboardCharField,
    copyClipboardCharField,
} from "@web/views/fields/copy_clipboard/copy_clipboard_field";

class ScriptExternalCharField extends CharField {
    get formattedValue() {
        return String(super.formattedValue);
    }
}

class ScriptExternalField extends CopyClipboardCharField {
    static components = { ...CopyClipboardCharField.components, Field: ScriptExternalCharField };
}

export const scriptExternalField = {
    ...copyClipboardCharField,
    component: ScriptExternalField,
    supportedTypes: ["html"],
};

registry.category("fields").add("script_external", scriptExternalField);
