import { useComponent, useLayoutEffect, useRef } from "@web/owl2/utils";
import { getActiveHotkey } from "@web/core/hotkeys/hotkey_service";
import { useBus } from "@web/core/utils/hooks";

/**
 * This hook is meant to be used by field components that use an input or
 * textarea to edit their value. Its purpose is to prevent that value from being
 * erased by an update of the model (typically coming from an onchange) when the
 * user is currently editing it.
 *
 * @param {Object} params
 * @param {() => string} params.getValue a function that returns the value to write in
 *   the input, if the user isn't currently editing it
 * @param {(value: string) => any} [params.parse] a function that parses the value of the input.
 * @param {Ref<HTMLInputElement | HTMLTextAreaElement>} [params.ref] a ref containing the input/textarea
 * @param {string} [params.refName="input"] the ref name of the input/textarea
 * @param {boolean} [params.preventLineBreaks] Prevent line breaks in input when set
 * @param {string} [params.fieldName]
 * @param {() => boolean} [params.shouldSave] if true, save the record with the new value
 */
export function useInputField(params) {
    const component = useComponent();
    const fieldName = params.fieldName || component.props.name;
    const shouldSave = params.shouldSave ?? (() => false);

    const { inputRef, forceUpdate } = useInput({
        ref: params.ref,
        refName: params.refName,
        parse: params.parse,
        preventLineBreaks: params.preventLineBreaks,
        checkValueInvalid: () => component.props.record.isFieldInvalid(fieldName),
        onSetDirty: (isDirty) => {
            component.props.record.model.bus.trigger("FIELD_IS_DIRTY", isDirty);
            if (!component.props.record.isValid) {
                component.props.record.resetFieldValidity(fieldName);
            }
        },
        onParseFailure: () => {
            component.props.record.setInvalidField(fieldName);
        },
        getValue: () => component.props.record.data[fieldName],
        getFormattedValue: () => params.getValue(),
        setValue: async (val) => {
            await component.props.record.update({ [fieldName]: val }, { save: shouldSave() });
            component.props.record.model.bus.trigger("FIELD_IS_DIRTY", false);
        },
    });

    const { model } = component.props.record;
    useBus(model.bus, "WILL_SAVE_URGENTLY", () => forceUpdate(true));
    useBus(model.bus, "NEED_LOCAL_CHANGES", (ev) => ev.detail.proms.push(forceUpdate()));

    return inputRef;
}

export function useInput(params) {
    const inputRef = params.ref || useRef(params.refName || "input");

    /*
     * A field is dirty if it is no longer sync with the model
     * More specifically, a field is no longer dirty after it has *tried* to update the value in the model.
     * An invalid value will thefore not be dirty even if the model will not actually store the invalid value.
     */
    let isDirty = false;

    /**
     * The last value that has been commited to the model.
     * Not changed in case of invalid field value.
     */
    let lastSetValue = null;

    /**
     * Track the fact that there is a change sent to the model that hasn't been acknowledged yet
     * (e.g. because the onchange is still pending). This is necessary if we must do an urgent save,
     * as we have to re-send that change for the write that will be done directly.
     * FIXME: this could/should be handled by the model itself, when it will be rewritten
     */
    let pendingUpdate = false;

    /**
     * When a user types, we need to set the field as dirty.
     */
    function onInput(ev) {
        isDirty = ev.target.value !== lastSetValue;
        if (params.preventLineBreaks && ev.inputType === "insertFromPaste") {
            ev.target.value = ev.target.value.replace(/[\r\n]+/g, " ");
        }
        params.onSetDirty?.(isDirty);
    }

    /**
     * On blur, we consider the field no longer dirty, even if it were to be invalid.
     * However, if the field is invalid, the new value will not be committed to the model.
     */
    async function onChange(ev) {
        if (isDirty) {
            isDirty = false;
            let isInvalid = false;
            let val = ev.target.value;
            if (params.parse) {
                try {
                    val = params.parse(val);
                } catch {
                    params.onParseFailure?.();
                    isInvalid = true;
                }
            }

            if (!isInvalid) {
                if (val !== params.getValue()) {
                    lastSetValue = inputRef.el.value;
                    pendingUpdate = true;
                    await params.setValue(val);
                    pendingUpdate = false;
                } else {
                    inputRef.el.value = params.getFormattedValue();
                }
            }
        }
    }
    function onKeydown(ev) {
        const hotkey = getActiveHotkey(ev);
        const keys = ["tab", "shift+tab"];
        if (ev.target.tagName.toLowerCase() !== "textarea") {
            keys.push("enter");
        }
        if (keys.includes(hotkey)) {
            forceUpdate(false);
        }
        if (params.preventLineBreaks && ["enter", "shift+enter"].includes(hotkey)) {
            ev.preventDefault();
        }
    }

    useLayoutEffect(
        (inputEl) => {
            if (inputEl) {
                inputEl.addEventListener("input", onInput);
                inputEl.addEventListener("change", onChange);
                inputEl.addEventListener("keydown", onKeydown);
                return () => {
                    inputEl.removeEventListener("input", onInput);
                    inputEl.removeEventListener("change", onChange);
                    inputEl.removeEventListener("keydown", onKeydown);
                };
            }
        },
        () => [inputRef.el]
    );

    /**
     * Sometimes, a patch can happen with possible a new value for the field
     * If the user was typing a new value (isDirty) or the field is still invalid,
     * we need to do nothing.
     * If it is not such a case, we update the field with the new value.
     */
    useLayoutEffect(() => {
        // We need to call getValue before the condition to always observe
        // the corresponding value in the record. Otherwise, in some cases,
        // if the value in the record change the useLayoutEffect isn't triggered.
        const value = params.getFormattedValue();
        if (!inputRef.el) {
            return;
        }
        if (inputRef.el.value === value) {
            isDirty = false;
        }
        const editingField =
            isDirty || (params.checkValueInvalid ? params.checkValueInvalid() : false);
        if (!editingField) {
            inputRef.el.value = value;
            lastSetValue = inputRef.el.value;
        }
    });

    async function forceUpdate(urgent) {
        if (!inputRef.el) {
            return;
        }

        isDirty = inputRef.el.value !== lastSetValue;
        if (isDirty || (urgent && pendingUpdate)) {
            let isInvalid = false;
            isDirty = false;
            let val = inputRef.el.value;
            if (params.parse) {
                try {
                    val = params.parse(val);
                } catch {
                    isInvalid = true;
                    if (urgent) {
                        return;
                    } else {
                        params.onParseFailure?.();
                    }
                }
            }

            if (isInvalid) {
                return;
            }

            if ((val || false) !== (params.getValue() || false)) {
                lastSetValue = inputRef.el.value;
                await params.setValue(val);
            } else {
                inputRef.el.value = params.getFormattedValue();
            }
        }
    }

    return { inputRef, forceUpdate };
}
