import { toolbarButtonProps } from "@html_editor/main/toolbar/toolbar";
import { Component } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useState } from "@web/owl2/utils";

export class ImageAlignSelector extends Component {
    static template = "html_editor.ImageAlignSelector";
    static components = { Dropdown };
    static props = {
        items: Array,
        getDisplay: Function,
        onSelected: Function,
        ...toolbarButtonProps,
    };

    setup() {
        this.state = useState(this.props.getDisplay());
    }
}
