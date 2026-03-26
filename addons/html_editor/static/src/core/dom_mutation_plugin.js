import { Plugin } from "../plugin";
import { trackOccurrences, trackOccurrencesPair } from "@html_editor/utils/tracking";
import { treeToNodes, nodeToTree } from "@html_editor/utils/dom_info";
import { childNodes, getCommonAncestor } from "@html_editor/utils/dom_traversal";
import { omit, pick } from "@web/core/utils/objects";
import { toggleClass } from "@html_editor/utils/dom";
import { withSequence } from "@html_editor/utils/resource";

/**
 * DOM
 */
/**
 * @typedef { import("./dom_reference_plugin").NodeId } NodeId
 * @typedef { import("./dom_reference_plugin").Tree } Tree
 * @typedef { import("./dom_reference_plugin").SerializedNode } SerializedNode
 */

/**
 * COMMITS
 */
/**
 * @typedef { import("../utils/commit").EditorCommit } EditorCommit
 * @typedef { import("../utils/commit").EditorCommitType } EditorCommitType
 * @typedef { import("@html_editor/utils/commit").EditorCommitId } EditorCommitId
 * @typedef { import("@html_editor/utils/commit").EditorCommitMetadata } EditorCommitMetadata
 *
 * @typedef { Object } DomMutationCommitData
 * @property { SerializedMutation[] } mutations      // the mutations to apply/revert
 */

/**
 * MUTATIONS
 */
/**
 * @typedef { "attributes" | "characterData" | "childList" } NativeMutationType
 */
/**
 * Native Mutations
 * ----------------
 *
 * Narrowed typing for the native `MutationRecord` type, to differentiate between
 * each mutation type, omitting all properties that are always `null` for the
 * given type of mutation.
 *
 * @template { NativeMutationType } [T=NativeMutationType]
 * @typedef { Extract<|
 *    (Pick<MutationRecord, "target" | "attributeName" | "attributeNamespace" | "oldValue"> & { type: "attributes" })
 *  | (Pick<MutationRecord, "target" | "oldValue"> & { type: "characterData" })
 *  | (Pick<MutationRecord, "target" | "addedNodes" | "removedNodes" | "previousSibling" | "nextSibling"> & { type: "childList" }),
 * { type: T }
 * > } NativeMutation
 */
/**
 * @typedef { Exclude<NativeMutationType, "childList"> | "classList" | "add" | "remove" } EditorMutationType
 */
/**
 * Editor Mutations
 * ----------------
 *
 * Expanded mutation object, with extra information that is helpful for our
 * purposes in the editor.
 *
 * @template { EditorMutationType } [T=EditorMutationType]
 * @typedef { Extract<|
 *    (NativeMutation<"attributes"> | { value: string })
 *  | (Omit<NativeMutation<"attributes">, "attributeName" | "attributeNamespace" | "type"> & { type: "classList", className: string, value: boolean })
 *  | (NativeMutation<"characterData"> | { value: string })
 *  | (Pick<NativeMutation<"childList">, "previousSibling" | "nextSibling"> | { tree: Tree, parent: Node } & { type: "add" })
 *  | (Pick<NativeMutation<"childList">, "previousSibling" | "nextSibling"> | { tree: Tree, parent: Node } & { type: "remove" }),
 * { type: T }
 * > } EditorMutation
 */
/**
 * Serialized Mutations
 * --------------------
 *
 * Serialized version of `EditorMutation`s for safely passing around the editor
 * without losing references and to allow as JSON payload.
 *
 * @template { EditorMutationType } [T=EditorMutationType]
 * @typedef { Extract<|
 *     (Omit<EditorMutation<"attributes">, "target"> & { nodeId: NodeId })
 *   | (Omit<EditorMutation<"classList">, "target"> & { nodeId: NodeId })
 *   | (Omit<EditorMutation<"characterData">, "target"> & { nodeId: NodeId })
 *   | (Omit<EditorMutation<"classList">, "target"> & { nodeId: NodeId })
 *   | (Omit<EditorMutation<"add">, "target" | "previousSibling" | "nextSibling" | "tree" | "parent"> & { nodeId: NodeId, previousNodeId: NodeId, nextNodeId: NodeId, serializedNode: SerializedNode, parentNodeId: NodeId })
 *   | (Omit<EditorMutation<"remove">, "target" | "previousSibling" | "nextSibling" | "tree" | "parent"> & { nodeId: NodeId, previousNodeId: NodeId, nextNodeId: NodeId, serializedNode: SerializedNode, parentNodeId: NodeId }),
 *   { type: T }
 * > } SerializedMutation
 */

/**
 * @typedef { Object } PreviewableOperation
 * @property { Function } commit
 * @property { Function } preview
 * @property { Function } revert
 */
/**
 * @typedef { Object } ObservedState
 * @property { Map<string, string> } attributes
 * @property { Map<string, boolean> } classList
 * @property { Map<string, string> } characterData
 */
/**
 * @typedef { WeakMap<NativeMutation<"childList">, { added: Tree[], removed: Tree[] }> } ChildListToTreesMap
 */

/**
 * @typedef { Object } DomMutationShared
 * @property { DomMutationPlugin['discard'] } discard
 * @property { DomMutationPlugin['stage'] } stage
 * @property { DomMutationPlugin['stash'] } stash
 * @property { DomMutationPlugin['unstash'] } unstash
 * @property { DomMutationPlugin['stageCustomMutation'] } stageCustomMutation
 * @property { DomMutationPlugin['applyCustomMutation'] } applyCustomMutation
 * @property { DomMutationPlugin['hasStagedMutations'] } hasStagedMutations
 * @property { DomMutationPlugin['ignoreDOMMutations'] } ignoreDOMMutations
 */

/**
 * @typedef { ((
 *    mutation: SerializedMutation<"attributes">,
 *    options: { ensureNewMutations: boolean, wasReversed: boolean }
 *  ) => arg)[] } attribute_change_processors
 * @typedef {((node: Node, attributeName: string, attributeValue: string) => boolean)[]} set_attribute_overrides
 * @typedef { ((root: HTMLElement) => void)[] } on_content_updated_handlers
 * @typedef { ((record: SerializedMutation[]) => void)[] } on_attribute_changed_handlers
 * @typedef { ((record: SerializedMutation[], currentOperation: EditorCommitType) => void)[] } on_new_records_handled_handlers
 * @typedef { ((node: Node, childTreesToSerialize: Tree[]) => Tree[])[] } serializable_descendants_processors
 * @typedef { ((isRevision: boolean) => void)[] } on_flushed_mutations_handlers
 * @typedef { ((isRevision: boolean) => void)[] } on_normalized_flushed_mutations_handlers
 * @typedef { ((records: NativeMutation[]) => void)[] } on_will_filter_mutation_record_handlers
 * @typedef { ((record: NativeMutation) => boolean | undefined)[] } is_mutation_savable_predicates
 * @typedef { ((record: EditorMutation<"classList">) => boolean | undefined)[] } is_classlist_mutation_savable_predicates
 */
export class DomMutationPlugin extends Plugin {
    static id = "domMutation";
    static dependencies = ["domReference", "history", "sanitize"];
    static shared = [
        // Main public API
        "discard",
        "stage",
        "stash",
        "unstash",

        // Observer on/off
        "ignoreDOMMutations",

        // Staging
        "stageCustomMutation",
        "hasStagedMutations",

        // Commit application/reversal
        "applyCustomMutation",
    ];
    /** @type {import("plugins").EditorResources} */
    resources = {
        history_data_keys: ["mutations"],

        on_editor_started_handlers: withSequence(9, this.enableObserver.bind(this)),
        on_will_reset_history_from_commits_handlers: () => {
            // TODO AGE: this is only to replace the `withObserverOff` call in
            // `history.resetFromCommits` but it's not useful for `history.reset`,
            // and assumes a call to `history_reset_from_commits_handlers` after.
            this.lastEnableObserverCallback = this.disableObserver();
        },
        on_history_reset_from_commits_handlers: () => {
            // See above.
            this.lastEnableObserverCallback?.();
            this.lastEnableObserverCallback = undefined;
        },
        on_prepare_drag_handlers: this.disableHasStagedMutationsWarning.bind(this),
        on_history_cleaned_handlers: this.clean.bind(this),
        on_will_add_external_commit_handlers: () => {
            // The last commit is an uncommited draft, revert it first.
            this.stash();
        },
        on_external_commit_added_handlers: () => {
            // Reapply the uncommited draft, since this is not an operation
            // which should cancel it.
            this.unstash();
        },
        on_apply_commit_handlers: (commit, { ensureNewMutations = false } = {}) => {
            if (commit.data.mutations) {
                this.applyMutations(commit.data.mutations, { ensureNewMutations });
                // TODO AGE: check why reverting a commit involves also setting
                // its serialized focus and selection, and updating the state,
                // while _applying_ a commit doesn't. Couldn't we make this more
                // coherent?
            }
        },
        on_revert_commit_handlers: (commit, { ensureNewMutations = false } = {}) => {
            if (commit.data.mutations) {
                this.revertMutations(commit.data.mutations, { ensureNewMutations });
            }
        },
        on_will_undo_handlers: this.discard.bind(this),
        on_will_redo_handlers: this.discard.bind(this),
        revision_commit_data_processors: (data) => {
            this.flush(true);
            return { ...data, mutations: [...this.mutations] };
        },
        restoration_commit_data_processors: (data) => {
            this.flush(true);
            return { ...data, mutations: [...this.mutations] };
        },
        on_commit_restored_handlers: () => {
            // Process and stage mutations so that the attribute comparison for
            // the state change is done with the intermediate attribute value
            // and not with the final value in the DOM after all commits were
            // reverted then applied again.
            this.processAndStageMutations({ dispatch: false });
        },
        on_irreversible_commit_applied_handlers: () => {
            this.processAndStageMutations({ dispatch: false });
        },
        commit_root_providers: (commit) =>
            this.getMutationsRoot(commit.data.mutations || []) || this.editable,
        snapshot_commit_data_processors: (data) => {
            data.mutations = childNodes(this.editable)
                .filter((node) => this.dependencies.domReference.hasNode(node))
                .map((node) => ({
                    type: "add",
                    parentNodeId: "root",
                    nodeId: this.dependencies.domReference.getNodeId(node),
                    serializedNode: this.dependencies.domReference.serializeTree(nodeToTree(node)),
                    nextNodeId: null,
                }));
            return data;
        },
        on_current_history_data_reset_handlers: () => {
            this.mutations = [];
        },
        pending_commit_data_processors: (data) => {
            this.flush();
            return { ...data, mutations: [...this.mutations] };
        },
        save_point_data_processors: (savePoint) => {
            this.processAndStageMutations();
            return { ...savePoint, mutations: [...this.mutations] };
        },
        on_will_restore_save_point_handlers: withSequence(0, () => {
            this.discard();
        }),
        on_savepoint_restored_handlers: withSequence(0, (savePoint) => {
            // Apply draft mutations to recover the same mutations state as before.
            this.applyMutations(savePoint.mutations, { ensureNewMutations: true });
            this.processAndStageMutations();
            this.dispatchContentUpdated();
        }),
        has_commit_changes_predicates: (commit) => {
            if ("mutations" in commit.data) {
                return !!commit.data.mutations.length;
            }
        },
    };

    setup() {
        /** @type { SerializedMutation[] } */
        this.mutations = [];
        this.mutationFilteredClasses = new Set(this.getResource("system_classes"));
        this.mutationFilteredAttributes = new Set(this.getResource("system_attributes"));
        this.observer = new MutationObserver((records) =>
            this.processAndStageMutations({ records })
        );
        this.enableObserverCallbacks = new Set();
        this._cleanups.push(() => this.observer.disconnect());
        this.clean();
        /** @type { DomMutationCommitData[] } */
        this.currentStash = [];
    }

    clean() {
        // TODO AGE: rename to clarify what it is.
        /** @type { WeakMap<Node, ObservedState } */
        this.lastObservedState = new WeakMap();
    }

    // ===============
    // Main public API
    // ===============

    discard() {
        const mutations = [...this.mutations];
        // Discard current draft.
        this.processAndStageMutations();
        this.revertMutations([...this.mutations]);
        this.observer.takeRecords();
        this.mutations = [];
        return mutations;
    }

    stash() {
        this.currentStash.push(this.discard());
    }

    unstash(index = -1) {
        if (this.currentStash.length > index) {
            const mutations = this.currentStash.splice(index, 1)[0];
            this.applyMutations(mutations);
            // TODO AGE: this condition is theoretically insufficient because
            // the observer could also be disconnected. I guess best would be to
            // reactivate it before calling `applyMutation` and disable it
            // again. See about that when looking into
            // `disableObserver`/`withObserverOff`.
            if (this.isObserverDisabled) {
                // Make sure the unstashed mutations are recorded.
                this.stage(mutations);
            }
            // TODO AGE: shouldn't this also apply other changes?
        }
    }

    /**
     * Add the given serialized mutation(s) to `this.mutations`, which will
     * be used in the next commit.
     *
     * @param { SerializedMutation | SerializedMutation[] } mutations
     */
    stage(mutations) {
        mutations = Array.isArray(mutations) ? mutations : [mutations];
        this.mutations.push(...mutations);
    }

    // ===============
    // Observer on/off
    // ===============

    enableObserver() {
        this.observer.observe(this.editable, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeOldValue: true,
            characterData: true,
            characterDataOldValue: true,
        });
    }

    /**
     * Disable the mutation observer.
     *
     * /!\ This method should be used with extreme caution. Not observing some
     * mutations could lead to mutations that are impossible to undo/redo.
     */
    disableObserver() {
        const enableObserver = () => {
            this.enableObserverCallbacks.delete(enableObserver);
            if (this.enableObserverCallbacks.size > 0) {
                return;
            }
            this.processAndStageMutations();
            this.isObserverDisabled = false;
        };
        this.enableObserverCallbacks.add(enableObserver);
        this.processAndStageMutations();
        this.isObserverDisabled = true;
        return enableObserver;
    }

    /**
     * This is not shared as it is only used internally by the DOM mutation plugin.
     * Other plugins should use {@link ignoreDOMMutations} instead.
     * TODO AGE: why do we need this _and_ disableObserver?
     */
    withObserverOff(callback) {
        this.processAndStageMutations();
        this.observer.disconnect();
        callback();
        this.enableObserver();
    }

    /**
     * Execute {@link callback} while the MutationObserver is disabled.
     *
     * /!\ This method should be used with extreme caution. Not observing some
     * mutations could lead to mutations that are impossible to undo/redo.
     *
     * /!\ Do not re-introduce nodes that had been already added to the DOM in
     * a commit. @see isObservedNode
     *
     * @param { Function } callback
     */
    ignoreDOMMutations(callback) {
        const enableObserver = this.disableObserver();
        try {
            return callback();
        } finally {
            enableObserver();
        }
    }

    /**
     * Any node that was added to the DOM without a mutation record in a commit
     * (typically due to {@link ignoreDOMMutations}) is considered an unobserved
     * node.
     *
     * A known limitation to this approach is when a node that had been present
     * in the editable before (and thus has an entry in the nodeMap) is re-added
     * with {@link ignoreDOMMutations}. Such node will not be flagged as
     * unobserved and history might become inconsistent.
     *
     * @param { Node } node
     * @returns { boolean }
     */
    isObservedNode(node) {
        return this.dependencies.domReference.hasNode(node);
    }

    // =======
    // Staging
    // =======

    /**
     * Update `this.mutations` to set the correct mutations on the next commit,
     * by processing and staging all new mutations, normalizing the mutated
     * nodes, and updating any other data that needs updating, including by
     * letting other plugins respond.
     *
     * @param { boolean } [isRevision = false]
     */
    flush(isRevision = false) {
        // Stage the observer's current changes.
        this.processAndStageMutations({ dispatch: true, isRevision });
        const currentMutationsCount = this.mutations.length;
        if (currentMutationsCount === 0) {
            return;
        }

        // Normalize the mutated nodes. Note: this can cause other commits to be written.
        const commitRoot = this.getMutationsRoot(this.mutations) || this.editable;
        this.processThrough("normalize_processors", commitRoot);
        this.trigger("on_normalized_flushed_mutations_handlers", isRevision);
        this.processAndStageMutations({ dispatch: false, isRevision });
        if (currentMutationsCount === this.mutations.length) {
            // If there was no registered mutation during the normalization
            // commit, force the dispatch of a content_updated to allow i.e. the
            // hint plugin to react to non-observed changes (i.e. a div becoming
            // a baseContainer).
            this.dispatchContentUpdated();
        }

        // Give a chance to other plugins to update the current changes'
        // external data before we create the commit object.
        this.trigger("on_flushed_mutations_handlers", isRevision);
    }

    /**
     * Process the given native mutation records (or take the observer's current
     * mutation records by default) and stage them.
     *
     * @param { Object } [params]
     * @param { NativeMutation[] } [params.records = this.observer.takeRecords()]
     * @param { boolean } [params.dispatch = true]
     * @param { CommitType } [params.isRevision]
     *
     * TODO AGE: see if I can get rid of all these arguments. Should this be
     * called `stage`?
     */
    processAndStageMutations({
        records = this.observer.takeRecords(),
        dispatch = true,
        isRevision = false,
    } = {}) {
        if (this.observer.takeRecords().length) {
            throw new Error("MutationObserver has pending records");
        }

        // First process the records:
        const processedRecords = this.processNativeMutations(records);
        const serializedRecords = this.serializeEditorMutations(processedRecords);

        // Then stage them.
        this.stage(serializedRecords);

        // And finally, inform other plugins of changes.
        if (serializedRecords.length) {
            for (const mutation of serializedRecords) {
                if (mutation.type === "attributes") {
                    this.trigger("on_attribute_changed_handlers", mutation);
                }
            }
            // TODO modify `handleMutations` of web_studio to handle `undoOperation`.
            if (dispatch) {
                this.trigger("on_new_records_handled_handlers", serializedRecords, isRevision);
                // Process potential new mutations caused by the handlers.
                this.processAndStageMutations({ dispatch: false });
            }
            this.dispatchContentUpdated();
        }
    }

    stageCustomMutation({ apply, revert }) {
        const customMutation = {
            type: "custom",
            // Note AGE: this definitely fails in collaborative since it's not
            // serializable. Do we need it in collaborative?
            apply: () => {
                apply();
                this.stageCustomMutation({ apply, revert });
            },
            revert: () => {
                revert();
                this.stageCustomMutation({ apply: revert, revert: apply });
            },
        };
        this.stage(customMutation);
    }

    /**
     * Disable the warning in @see hasStagedMutations and return a function that
     * re-enables it.
     *
     * @returns { () => void }
     */
    disableHasStagedMutationsWarning() {
        this.ignoreHasStagedMutations = true;
        return () => {
            this.ignoreHasStagedMutations = false;
        };
    }

    /**
     * Return true if the staged changes include mutations of types
     * `characterData`, `remove` or `add`, false otherwise.
     *
     * @returns { boolean }
     */
    hasStagedMutations() {
        if (this.ignoreHasStagedMutations) {
            return false;
        }
        return !!this.mutations.find((m) => ["characterData", "remove", "add"].includes(m.type));
    }

    // ===================
    // Mutation processing
    // ===================

    /**
     * Filter through a batch of `NativeMutation`s then turn them into
     * `EditorMutation`s by adding information to them and splitting them so we
     * have individual records for each class change, each added node and each
     * removed nodes, and assign an ID to any added node.
     *
     * @param { NativeMutation[] } mutations
     * @returns { EditorMutation[] }
     */
    processNativeMutations(mutations) {
        this.trigger("on_will_filter_mutation_record_handlers", mutations);

        // Filter out same-textContent mutations. This needs to happen
        // first because it could affect the siblings computations below.
        mutations = mutations.filter((mutation) => {
            if (mutation.type === "childList") {
                // Check if a mutation consists of removing and adding a single
                // text node with the same text content, which occurs in Firefox
                // but is optimized away in Chrome.
                const { addedNodes, removedNodes } = mutation;
                const [firstAdded, firstRemoved] = [addedNodes[0], removedNodes[0]];
                if (
                    [addedNodes, removedNodes].every((nodes) => nodes.length === 1) &&
                    [firstAdded, firstRemoved].every((node) => node.nodeType === Node.TEXT_NODE) &&
                    firstAdded.textContent === firstRemoved.textContent
                ) {
                    const oldId = this.dependencies.domReference.getNodeId(firstRemoved);
                    if (oldId) {
                        this.dependencies.domReference.set(oldId, firstAdded);
                        return false;
                    }
                }
            }
            return true;
        });

        // Build a map of childList trees for all the mutations.
        const childListToTrees = this.createChildListToTreesMap(mutations);

        // Track the attributes/characterData mutation occurrences.
        const [isFirstAttribute, isFirstCharData] = [trackOccurrencesPair(), trackOccurrences()];
        const isFirstOccurrence = (mutation) =>
            mutation.type === "attributes"
                ? isFirstAttribute(mutation.target, mutation.attributeName)
                : isFirstCharData(mutation.target);

        // Now do the processing.
        return mutations
            .flatMap((mutation) => {
                if (!this.isObservedNode(mutation.target)) {
                    return false;
                }
                const isSavable =
                    !this.isObserverDisabled &&
                    (this.checkPredicates("is_mutation_savable_predicates", mutation) ?? true);
                switch (mutation.type) {
                    case "attributes":
                    case "characterData": {
                        if (isSavable) {
                            // Keep only the first mutation record for each
                            // (node, attribute) pair. Mutation records of type
                            // "attribute" and "characterData" provide the old
                            // value, but not the new value. When multiple
                            // mutations occur in the same batch for an
                            // element's attribute or characterData, we only
                            // know the final value of the accumulated changes,
                            // which is the DOM's current state. The oldValue
                            // provided by mutations after the first one are
                            // intermediate states that we do not care about.
                            // Discarding them allows us to store a single
                            // record representing the accumulated changes,
                            // instead of reconstructing the new value
                            // introduced by each mutation.
                            if (isFirstOccurrence(mutation)) {
                                if (mutation.type === "attributes") {
                                    return this.processAttributesMutation(mutation);
                                } else if (mutation.type === "characterData") {
                                    return this.processCharacterDataMutation(mutation);
                                }
                            }
                        } else {
                            // If the observer is disabled, store the last
                            // observed state of the target's affected property
                            // (attribute/class/textContent) and drop the
                            // record.
                            this.storeOldValue(mutation);
                        }
                        return false;
                    }
                    case "childList": {
                        return (
                            isSavable && this.processChildListMutation(mutation, childListToTrees)
                        );
                    }
                }
            })
            .filter(Boolean);
    }

    /**
     * Process a native mutation of type "attributes" by returning `false` if it
     * should be ignored, or turning it into one or several `EditorMutation`s.
     *
     * This involves:
     * - splitting a change on the "class" attribute into an array of mutations
     *   of type "classList" @see createClassListMutations
     * - giving it a `value` property
     * - updating its `oldValue` property @see updateOldValue
     *
     * @param { NativeMutation<"attributes"> } mutation
     * @returns { |
     *        EditorMutation<"attributes">
     *      | EditorMutation<"classList">[]
     *      | false }
     */
    processAttributesMutation(mutation) {
        if (
            // Skip the attributes change on the dom.
            mutation.target === this.editable ||
            mutation.attributeName === "contenteditable" ||
            // Skip system mutations.
            this.mutationFilteredAttributes.has(mutation.attributeName)
        ) {
            return false;
        }
        if (mutation.attributeName === "class") {
            return (
                this.createClassListMutations(mutation)
                    .map(this.updateOldValue.bind(this))
                    // Filter out no-op.
                    .filter((classRecord) => classRecord.value !== classRecord.oldValue)
            );
        } else {
            const processedMutation = this.updateOldValue(
                /** @type { EditorMutation<"attributes"> } */ {
                    ...pick(mutation, "type", "target", "attributeName", "oldValue"),
                    value: mutation.target.getAttribute(mutation.attributeName),
                }
            );
            if (processedMutation.value === processedMutation.oldValue) {
                // Filter out no-op.
                return false;
            }
            return processedMutation;
        }
    }

    /**
     * Process a native mutation of type "characterData" by returning `false` if
     * it should be ignored, or turning it into one an `EditorMutation`.
     *
     * This involves:
     * - giving it a `value` property
     * - updating its `oldValue` property @see updateOldValue
     *
     * @param {NativeMutation<"characterData">} mutation
     * @returns {EditorMutation<"characterData"> | false}
     */
    processCharacterDataMutation(mutation) {
        const processedMutation = this.updateOldValue(
            /** @type { EditorMutation<"characterData"> } */ {
                ...pick(mutation, "type", "target", "oldValue"),
                value: mutation.target.textContent,
            }
        );
        // Filter out no-ops.
        return processedMutation.value === processedMutation.oldValue ? false : processedMutation;
    }

    /**
     * Process a native mutation of type "childList" by returning `false` if it
     * should be ignored, or turning it into an array of single-node
     * `EditorMutation`s of types "add" and/or "remove".
     *
     * This involves:
     * - assigning IDs to all added nodes
     * - splitting the record into one record per item in the `addedNodes` and
     *   `removedNodes` arrays
     * - giving each newly created record the native mutation's target as
     *   `parent` property
     * - giving each newly created record a `tree` property containing the tree
     *   of the record's corresponding `addedNodes` or `removedNodes` item.
     *
     * Note: Splitting the record requires having build a `ChildListToTreesMap`
     * with @see createChildListToTreesMap using all the records in the batch.
     *
     * @param { NativeMutation<"childList"> } mutation
     * @param { ChildListToTreesMap } childListToTrees
     * @returns { EditorMutation<"add" | "remove">[] | false }
     */
    processChildListMutation(mutation, childListToTrees) {
        if (!this.dependencies.domReference.hasNode(mutation.target)) {
            throw new Error("Unknown parent node");
        }

        const trees = childListToTrees.get(mutation);

        // Filter out unobserved nodes in the removed trees.
        const removeUnobservedNodes = (tree) =>
            this.isObservedNode(tree.node)
                ? {
                      node: tree.node,
                      children: tree.children.map(removeUnobservedNodes).filter(Boolean),
                  }
                : null;
        trees.removed = trees.removed.map(removeUnobservedNodes).filter(Boolean);
        childListToTrees.set(mutation, trees); // TODO AGE: probably not necessary.

        // Invalidate sibling references to unobserved nodes
        const previousSibling =
            mutation.previousSibling === null || this.isObservedNode(mutation.previousSibling)
                ? mutation.previousSibling
                : undefined;
        const nextSibling =
            mutation.nextSibling === null || this.isObservedNode(mutation.nextSibling)
                ? mutation.nextSibling
                : undefined;

        if (
            // Filter out no-op
            (!trees.added.length && !trees.removed.length) ||
            // Filter out mutation without a valid position for node insertion
            (previousSibling === undefined && nextSibling === undefined)
        ) {
            return false;
        }

        // Assign ids to newly added childList nodes early so later records in
        // the same `MutationObserver` batch can resolve them (notably in
        // `isObservedNode`).
        trees.added
            .flatMap(treeToNodes)
            .filter((node) => !this.dependencies.domReference.hasNode(node))
            .forEach((node) => this.dependencies.domReference.setNodeId(node, false));

        // Split the mutation into single node mutations.
        return [
            ...trees.removed.map((tree, index) => ({
                type: "remove",
                tree,
                parent: mutation.target,
                previousSibling,
                nextSibling: trees.removed[index + 1]?.node || nextSibling,
            })),
            ...trees.added.map((tree, index) => ({
                type: "add",
                tree,
                parent: mutation.target,
                previousSibling: trees.added[index - 1]?.node || previousSibling,
                nextSibling,
            })),
        ];
    }

    /**
     * Break down a single class attribute `NativeMutation` into individual
     * class addition/removal `EditorMutation`s for more precise history
     * tracking.
     *
     * @param { NativeMutation<"attributes"> } mutation
     * @returns { EditorMutation<"classList">[] }
     */
    createClassListMutations(mutation) {
        // oldValue can be nullish, or have extra spaces
        const classesBefore = new Set(mutation.oldValue?.split(" ").filter(Boolean));
        const classesAfter = new Set(mutation.target.classList);
        const addedClasses = classesAfter.difference(classesBefore);
        const removedClasses = classesBefore.difference(classesAfter);

        /** @type { (className: string, isAdded: boolean) => EditorMutation<"classList"> } */
        const createClassRecord = (className, isAdded) => ({
            type: "classList",
            target: mutation.target,
            className,
            value: isAdded,
            oldValue: !isAdded,
        });
        // Generate records for each class change, skipping system mutations.
        return [
            ...[...addedClasses].map((cls) => createClassRecord(cls, true)),
            ...[...removedClasses].map((cls) => createClassRecord(cls, false)),
        ].filter(
            (classRecord) =>
                !this.mutationFilteredClasses.has(classRecord.className) &&
                (this.checkPredicates("is_classlist_mutation_savable_predicates", classRecord) ??
                    true)
        );
    }

    /**
     * `NativeMutation` records of type "childList" do not contain information
     * about the descendants of the added/removed nodes at the time of the
     * mutation. This returns a map from the "childList" mutations in a batch to
     * their respective added/removed trees.
     *
     * @param { NativeMutation[] } mutations
     * @returns { ChildListToTreesMap }
     */
    createChildListToTreesMap(mutations) {
        /** @type { ChildListToTreesMap } */
        const childListToTreesMap = new WeakMap();
        /** @type { WeakMap<Node, Node[]> } */
        const childListSnapshot = new WeakMap();
        /**
         * @param {Node} node
         * @returns {Node[]}
         */
        const getChildListSnapshot = (node) => childListSnapshot.get(node) || childNodes(node);
        /**
         * @param {Node} node
         * @returns {Tree}
         */
        const makeSnapshotTree = (node) => ({
            node,
            children: getChildListSnapshot(node).map(makeSnapshotTree),
        });
        /**
         * Reconstructs the child list before a mutation based on the state
         * after it and the child list modifications
         *
         * @param {Node[]} childListAfter
         * @param {NativeMutation} record
         * @returns {Node[]}
         */
        const reconstructChildList = (childListAfter, record) => {
            const { removedNodes, previousSibling, nextSibling } = record;
            const previousSiblingNodes = previousSibling
                ? childListAfter.slice(0, childListAfter.indexOf(previousSibling) + 1)
                : [];
            const nextSiblingNodes = nextSibling
                ? childListAfter.slice(childListAfter.indexOf(nextSibling))
                : [];
            return [...previousSiblingNodes, ...removedNodes, ...nextSiblingNodes];
        };
        mutations.toReversed().forEach((/** @type { NativeMutation } */ record) => {
            if (record.type === "childList") {
                childListToTreesMap.set(record, {
                    added: [...record.addedNodes].map(makeSnapshotTree),
                    removed: [...record.removedNodes].map(makeSnapshotTree),
                });
                // Update snapshot for previous mutations
                const childListAfterMutation = getChildListSnapshot(record.target);
                const childListBefore = reconstructChildList(childListAfterMutation, record);
                childListSnapshot.set(record.target, childListBefore);
            }
        });
        return childListToTreesMap;
    }

    // TODO AGE: I feel like it should be possible to get rid of the following
    // three functions with some changes in `processNativeMutations`: investigate.

    /**
     * This function, alongside @see updateOldValue, ensures mutation records
     * have the correct historical "oldValue" by checking against the last
     * observed state.
     *
     * When the observer is disabled, we store the record's `oldValue` for a
     * node's attribute/class/textContent as the last observed value.
     *
     * As multiple mutations to the same node-attribute/class/textContent can
     * happen with the observer disabled, we store only the first value
     * encountered for each node-attribute/class/text. This way, we capture the
     * state as it was before any modifications in the disabled observer
     * sequence began.
     *
     * @see updateOldValue
     *
     * @param { NativeMutation<"attributes"|"characterData"> } record
     */
    storeOldValue(record) {
        /** @type { (NativeMutation<"attributes"|"characterData"> | EditorMutation<"classList">)[] } */
        let mutations = [record];
        if (record.type === "attributes" && record.attributeName === "class") {
            // If the record is a change in a class attribute, first split it so
            // we can handle the old value of each class individually.
            mutations = this.createClassListMutations(record);
        }
        for (const mutation of mutations) {
            const { stateMap, key } = this.getObservedStateStorage(mutation);
            // Only store it if not already stored.
            if (!stateMap.has(key)) {
                stateMap.set(key, mutation.oldValue);
            }
        }
    }

    /**
     * @template { "attributes" | "characterData" } T
     * @param { |
     *        NativeMutation<T>
     *      | EditorMutation<T | "childList">
     * } record
     * @returns { {
     *      stateMap: ObservedState[T | "childList"],
     *      key: string
     * } }
     */
    getObservedStateStorage(record) {
        // Add entry for current target if not already present.
        if (!this.lastObservedState.has(record.target)) {
            this.lastObservedState.set(record.target, {
                attributes: new Map(),
                classList: new Map(),
                characterData: new Map(),
            });
        }
        const stateMap = this.lastObservedState.get(record.target)[record.type];
        switch (record.type) {
            case "attributes":
                return { stateMap, key: record.attributeName };
            case "classList":
                return { stateMap, key: record.className };
            case "characterData":
                return { stateMap, key: "textContent" };
            default:
                throw new Error(`Unsupported mutation type: ${record.type}`);
        }
    }

    /**
     * This function, alongside @see storeOldValue, ensures mutation records
     * have the correct historical "oldValue" by checking against the last
     * observed state.
     *
     * When the observer is enabled, it updates a record's `oldValue` with the
     * last observed state, and removes the entry to prevent reuse. Without
     * removing the entry, the same historical value might be incorrectly
     * applied to future mutation records targeting the same
     * attribute/class of the same element, which would create incorrect
     * history mutations.
     *
     * @template { NativeMutationType } T
     * @param { EditorMutation<T>} record
     * @returns { EditorMutation<T> }
     */
    updateOldValue(record) {
        const { stateMap, key } = this.getObservedStateStorage(record);
        if (!stateMap.has(key)) {
            return record;
        }
        const lastObservedValue = stateMap.get(key);
        // Remove entry, so it won't be used again.
        stateMap.delete(key);
        return { ...record, oldValue: lastObservedValue };
    }

    /**
     * Turn `EditorMutation`s into `SerializedMutation`s by replacing their
     * references to nodes with node IDs and serialized trees.
     *
     * @param { EditorMutation[] } records
     * @returns { SerializedMutation[] }
     */
    serializeEditorMutations(records) {
        return records.flatMap((record) => {
            switch (record.type) {
                case "characterData":
                case "classList":
                case "attributes": {
                    const nodeId = this.dependencies.domReference.getNodeId(record.target);
                    return { ...omit(record, "target"), nodeId };
                }
                case "add":
                case "remove": {
                    const [nextNodeId, previousNodeId] = [
                        record.nextSibling,
                        record.previousSibling,
                    ].map((sibling) =>
                        // Preserve undefined and null values
                        sibling ? this.dependencies.domReference.getNodeId(sibling) : sibling
                    );
                    // Note: IDs are assigned to added nodes in
                    // `processChildListMutation`.
                    return {
                        type: record.type,
                        nodeId: this.dependencies.domReference.getNodeId(record.tree.node),
                        parentNodeId: this.dependencies.domReference.getNodeId(record.parent),
                        serializedNode: this.dependencies.domReference.serializeTree(record.tree),
                        nextNodeId,
                        previousNodeId,
                    };
                }
                default: {
                    return record;
                }
            }
        });
    }

    // ===========================
    // Commit application/reversal
    // ===========================

    /**
     * @param { SerializedMutation[] } mutations
     * @param { Object } options
     * @param { boolean } options.ensureNewMutations whether to ensure new
     *        mutations are generated when applying the mutations
     * @param { boolean } options.areReversed whether the mutations are the
     *        reverse of other mutations
     */
    applyMutations(mutations, { ensureNewMutations = false, areReversed = false } = {}) {
        if (ensureNewMutations) {
            this.fixClassListMutationsToEnsureNewMutations(mutations);
        }
        for (const mutation of mutations) {
            switch (mutation.type) {
                case "custom": {
                    mutation.apply();
                    break;
                }
                case "characterData": {
                    const node = this.dependencies.domReference.getNodeById(mutation.nodeId);
                    if (node) {
                        node.textContent = mutation.value;
                    }
                    break;
                }
                case "classList": {
                    const node = this.dependencies.domReference.getNodeById(mutation.nodeId);
                    if (node) {
                        toggleClass(node, mutation.className, mutation.value);
                    }
                    break;
                }
                case "attributes": {
                    const options = { ensureNewMutations, wasReversed: areReversed };
                    this.applyAttributesMutation(mutation, options);
                    break;
                }
                case "remove": {
                    this.applyRemoveMutation(mutation);
                    break;
                }
                case "add": {
                    this.applyAddMutation(mutation);
                    break;
                }
            }
        }
    }

    /**
     * @param { SerializedMutation<"attributes"> } mutation
     * @param { Object } options
     * TODO AGE: rename and re-document this param:
     * @param { boolean } [options.ensureNewMutations = false] whether the mutation is being used
     *        to create a new commit and requires to ensure new mutations are generated
     * @param { boolean } [options.wasReversed = false] whether the change was reversed
     */
    applyAttributesMutation(mutation, options = {}) {
        const node = this.dependencies.domReference.getNodeById(mutation.nodeId);
        if (node) {
            const { value } = this.processThrough("attribute_change_processors", mutation, options);
            if (!this.delegateTo("set_attribute_overrides", node, mutation.attributeName, value)) {
                if (value === null) {
                    node.removeAttribute(mutation.attributeName);
                } else {
                    node.setAttribute(mutation.attributeName, value);
                }
            }
        }
    }

    /**
     * @param { SerializedMutation<"add"> } mutation
     */
    applyAddMutation(mutation) {
        const { nodeId, serializedNode, parentNodeId, nextNodeId, previousNodeId } = mutation;

        const toAdd =
            this.dependencies.domReference.getNodeById(nodeId) ||
            this.dependencies.domReference.unserializeNode(serializedNode);
        if (!toAdd) {
            return;
        }

        const parent = this.dependencies.domReference.getNodeById(parentNodeId);
        if (!parent) {
            console.warn("Mutation could not be applied, parent node is missing.", mutation);
            return;
        }
        if (previousNodeId === null) {
            parent.prepend(toAdd);
            return;
        }
        if (nextNodeId === null) {
            parent.append(toAdd);
            return;
        }
        const isValid = (node) => node?.parentNode === parent;
        const previousNode = this.dependencies.domReference.getNodeById(previousNodeId);
        if (isValid(previousNode)) {
            previousNode.after(toAdd);
            return;
        }
        const nextNode = this.dependencies.domReference.getNodeById(nextNodeId);
        if (isValid(nextNode)) {
            nextNode.before(toAdd);
            return;
        }
        console.warn("Mutation could not be applied, reference nodes are invalid.", mutation);
    }

    /**
     * @param { SerializedMutation<"remove"> } mutation
     */
    applyRemoveMutation(mutation) {
        const parent = this.dependencies.domReference.getNodeById(mutation.parentNodeId);
        const toRemove = this.dependencies.domReference.getNodeById(mutation.nodeId);
        if (!toRemove) {
            console.warn("Mutation could not be applied, node to remove is unknown.", mutation);
            return;
        }
        if (toRemove.parentElement !== parent) {
            console.warn("Mutation could not be applied, parent node does not match.", mutation);
            return;
        }
        toRemove.remove();
    }

    applyCustomMutation({ apply, revert }) {
        apply();
        this.stageCustomMutation({ apply, revert });
    }

    /**
     * Take a batch of mutations, reverse both their effect and their order,
     * then apply that.
     *
     * @param { SerializedMutation[] } mutations
     * @param { Object } options
     * @param { boolean } options.ensureNewMutations whether to ensure new
     *        mutations are generated when applying the mutations
     */
    revertMutations(mutations, { ensureNewMutations = false } = {}) {
        const reversedMutations = mutations.map((mutation) => {
            switch (mutation.type) {
                case "characterData":
                case "classList":
                case "attributes":
                    return { ...mutation, value: mutation.oldValue, oldValue: mutation.value };
                case "remove":
                    return { ...mutation, type: "add" };
                case "add":
                    return { ...mutation, type: "remove" };
                case "custom":
                    return { ...mutation, apply: mutation.revert, revert: mutation.apply };
                default:
                    throw new Error(`Unknown mutation type: ${mutation.type}`);
            }
        });
        this.applyMutations(reversedMutations.toReversed(), {
            ensureNewMutations,
            areReversed: true,
        });
    }

    /**
     * When applying mutations for a new commit, we expect them to produce
     * observable mutations, which will then be stored in a new commit. However,
     * there are situations where applying a classList mutation would not
     * produce an observable mutation:
     * - adding a class that is already present
     * - removing a class that is already absent
     * These scenarios might happen due to the class having been already added
     * or removed by a previous unobserved mutation. We want, nevertheless to
     * produce the observable mutation of adding/removing this class, as this
     * does correspond to a state change in observable history and should be
     * included in the new commit. In order to produce such observable
     * mutations, we set the dom state to the one that would produce the desired
     * result. This is equivalent to restoring the dom to the observed state in
     * recorded history before applying a mutation, that is, oldValue (as
     * oldValue is always !value for staged classList records).
     *
     * @param { EditorMutation[] } mutations
     */
    fixClassListMutationsToEnsureNewMutations(mutations) {
        const isFirstOcurrence = trackOccurrencesPair();
        // Mutations that when applied would not produce observable classList mutations
        const nonObservableClassMutations = mutations
            .filter((mutation) => mutation.type === "classList")
            .filter(({ nodeId, className }) => isFirstOcurrence(nodeId, className))
            .map((mutation) => ({
                ...mutation,
                node: this.dependencies.domReference.getNodeById(mutation.nodeId),
            }))
            .filter(({ node, className, value }) => value === node?.classList.contains(className));
        if (nonObservableClassMutations.length) {
            const setToOldValue = ({ node, className, oldValue }) =>
                toggleClass(node, className, oldValue);
            this.withObserverOff(() => nonObservableClassMutations.forEach(setToOldValue));
        }
    }

    // =============
    // Miscellaneous
    // =============

    /**
     * Returns the deepest common ancestor element of the given mutations.
     * @param { (EditorMutation)[] } mutations - The array of mutations.
     * @returns { HTMLElement | null } - The common ancestor element.
     */
    getMutationsRoot(mutations) {
        const nodes = mutations
            .map((m) => this.dependencies.domReference.getNodeById(m.parentNodeId || m.nodeId))
            .filter((node) => this.editable.contains(node));
        let commonAncestor = getCommonAncestor(nodes, this.editable);
        if (commonAncestor?.nodeType === Node.TEXT_NODE) {
            commonAncestor = commonAncestor.parentElement;
        }
        return commonAncestor;
    }

    dispatchContentUpdated() {
        if (this.mutations.length) {
            // @todo @phoenix remove this?
            // @todo @phoenix this includes previous mutations that were already
            // stored in the current commit. Ideally, it should only include the new ones.
            const root = this.getMutationsRoot(this.mutations);
            if (root) {
                this.trigger("on_content_updated_handlers", root);
            }
        }
    }
}
