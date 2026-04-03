import { Component } from "@odoo/owl";
import { SelectMenu } from "@web/core/select_menu/select_menu";
import { _t } from "@web/core/l10n/translation";
import { useState } from "@web/owl2/utils";
import { BuilderComponent } from "@html_builder/core/building_blocks/builder_component";
import {
    basicContainerBuilderComponentProps,
    useBuilderComponent,
    getAllActionsAndOperations,
    useDomState,
} from "@html_builder/core/utils";

export class BuilderMultiSelect extends Component {
    static template = "html_builder.BuilderMultiSelect";
    static components = { BuilderComponent, SelectMenu };
    static defaultProps = {
        message: _t("Choose a record..."),
        onInput: () => {},
    };
    static props = {
        ...basicContainerBuilderComponentProps,
        choices: {
            type: Array,
            element: {
                type: Object,
                shape: {
                    id: { type: [String, Number] }, // Must be Unique values
                    name: { type: String },
                },
            },
        },
        onInput: { type: Function, optional: true },
        message: { type: String, optional: true },
    };

    setup() {
        useBuilderComponent();
        const { getAllActions, callOperation } = getAllActionsAndOperations(this);
        this.callOperation = callOperation;
        this.applyOperation = this.env.editor.shared.history.makePreviewableAsyncOperation(
            this.callApply.bind(this)
        );

        this.state = useState({
            previousSearchedString: "",
            choices: this.props.choices,
        });

        this.domState = useDomState((el) => {
            const getAction = this.env.editor.shared.builderActions.getAction;
            const actionWithGetValue = getAllActions().find(
                ({ actionId }) => getAction(actionId).getValue
            );
            const { actionId, actionParam } = actionWithGetValue;
            const actionValue = getAction(actionId).getValue({
                editingElement: el,
                params: actionParam,
            });
            return {
                selections: actionValue ? JSON.parse(actionValue) : [],
            };
        });
    }
    callApply(applySpecs) {
        const proms = [];
        for (const applySpec of applySpecs) {
            proms.push(
                applySpec.action.apply({
                    editingElement: applySpec.editingElement,
                    params: applySpec.actionParam,
                    value: applySpec.actionValue,
                    loadResult: applySpec.loadResult,
                    dependencyManager: this.env.dependencyManager,
                })
            );
        }
        return proms;
    }
    async onInput(searchString) {
        if (!searchString) {
            this.state.choices = this.props.choices;
            this.state.previousSearchedString = "";
            return;
        }
        if (searchString === this.state.previousSearchedString) {
            return;
        }
        this.state.choices = await this.props.onInput(searchString, this.domState.selections);
        this.state.previousSearchedString = searchString;
    }
    onSelect(newSelection) {
        const selectedValues = [...this.domState.selections, newSelection];
        this.callOperation(this.applyOperation.commit, {
            userInputValue: JSON.stringify(selectedValues),
        });
    }
    unselect(id) {
        const selectedValues = this.domState.selections.filter((selection) => selection.id !== id);
        this.callOperation(this.applyOperation.commit, {
            userInputValue: JSON.stringify(selectedValues),
        });
    }
    get filteredChoices() {
        return this.state.choices.filter(
            (choice) => !this.domState.selections.some((selection) => selection.id === choice.id)
        );
    }
}
