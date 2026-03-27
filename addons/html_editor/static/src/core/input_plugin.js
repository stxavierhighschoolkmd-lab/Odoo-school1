import { Plugin } from "../plugin";

/**
 * @typedef {((ev: InputEvent) => void)[]} on_beforeinput_handlers
 * @typedef {((ev: InputEvent) => void)[]} on_input_handlers
 */

export class InputPlugin extends Plugin {
    static id = "input";
    static dependencies = ["history", "selection"];
    setup() {
        this.addDomListener(this.editable, "beforeinput", this.onBeforeInput);
        this.addDomListener(this.editable, "input", this.onInput);
    }

    onBeforeInput(ev) {
        this.dependencies.selection.stageSelection();
        this.trigger("on_beforeinput_handlers", ev);
    }

    onInput(ev) {
        this.dependencies.history.write({ batchable: ev.inputType === "insertText" });
        this.trigger("on_input_handlers", ev);
    }
}
