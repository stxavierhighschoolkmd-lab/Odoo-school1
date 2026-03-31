import { Plugin } from "../plugin";
import { hasTouch } from "@web/core/browser/feature_detection";
import { withSequence } from "@html_editor/utils/resource";
import { _t } from "@web/core/l10n/translation";
import { EditorCommit } from "../utils/commit";

/**
 * @typedef { import("../utils/commit").EditorCommit } EditorCommit
 * @typedef { import("../utils/commit").EditorCommitType } EditorCommitType
 * @typedef { import("../utils/commit").EditorCommitData } EditorCommitData
 * @typedef { import("../utils/commit").EditorCommitMetadata } EditorCommitMetadata
 * @typedef { import("../utils/commit").EditorCommitId } EditorCommitId
 * @typedef { import("./selection_plugin").SerializedSelection } SerializedSelection
 *
 * @typedef { Object } HistoryCommitData
 * @property { number } authorTimestamp
 * @property { number } [commitTimestamp]
 * @property { EditorCommitId } [previousCommitId]
 * @property { boolean } [batchable]
 */
/**
 * @typedef { Object } HistoryShared
 * @property { HistoryPlugin['commit'] } commit
 * @property { HistoryPlugin['undo'] } undo
 * @property { HistoryPlugin['redo'] } redo
 * @property { HistoryPlugin['canUndo'] } canUndo
 * @property { HistoryPlugin['canRedo'] } canRedo
 * @property { HistoryPlugin['getHistoryCommits'] } getHistoryCommits
 * @property { HistoryPlugin['reset'] } reset
 * @property { HistoryPlugin['addExternalCommit'] } addExternalCommit
 * @property { HistoryPlugin['resetFromCommits'] } resetFromCommits
 * @property { HistoryPlugin['createSnapshotCommit'] } createSnapshotCommit
 * @property { HistoryPlugin['getIsPreviewing'] } getIsPreviewing
 * @property { HistoryPlugin['makePreviewableOperation'] } makePreviewableOperation
 * @property { HistoryPlugin['makePreviewableAsyncOperation'] } makePreviewableAsyncOperation
 * @property { HistoryPlugin['makeSavePoint'] } makeSavePoint
 */
/**
 * @typedef {(() => void)[]} on_external_commit_added_handlers
 * @typedef {(() => void)[]} on_history_cleaned_handlers
 * @typedef {(() => void)[]} on_history_reset_handlers
 * @typedef {(() => void)[]} on_history_reset_from_commits_handlers
 * @typedef {((commit: EditorCommit) => void)[]} on_history_committed_handlers
 * @typedef {((commit: EditorCommit, options?: { ensureNewMutations?: boolean }) => void)[]} on_apply_commit_handlers
 * @typedef {((commit: EditorCommit, options?: { ensureNewMutations?: boolean, restoreFocus?: boolean }) => void)[]} on_revert_commit_handlers
 * @typedef {((revertedCommit: EditorCommit) => void)[]} on_undone_handlers
 * @typedef {((revertedCommit: EditorCommit) => void)[]} on_redone_handlers
 * @typedef {(() => void)[]} on_preview_handlers
 * @typedef { (() => void)[] } on_restore_save_point_handlers
 * @typedef { (() => void)[] } on_commit_restored_handlers
 * @typedef { (() => void)[] } on_irreversible_commit_applied_handlers
 * @typedef { ((savePoint: Object) => void)[] } on_will_restore_save_point_handlers
 * @typedef { ((savePoint: Object, lastRevertedChanges: EditorCommitData) => void)[] } on_savepoint_restored_handlers
 * @typedef { ((lastRevertedChanges: EditorCommitData) => void)[] } on_restored_to_commit_handlers
 * @typedef { (() => void)[] } on_current_history_data_reset_handlers
 *
 * @typedef {((commit: EditorCommit) => boolean | undefined)[]} is_commit_reversible_predicates
 * @typedef {((commit: EditorCommit) => boolean | undefined)[]} has_commit_changes_predicates
 *
 * @typedef { ((data: EditorCommitData, origin?: EditorCommitData) => EditorCommitData | undefined)[] } pending_commit_data_processors
 * @typedef {((data: EditorCommitData) => EditorCommitData | undefined)[]} snapshot_commit_data_processors
 * @typedef { ((savePoint: Object) => Object | void)[] } save_point_data_processors
 */

export const COMMIT_DEBOUNCE_DELAY = 250;

export class HistoryPlugin extends Plugin {
    static id = "history";
    static dependencies = ["domReference", "selection"];
    static shared = [
        // Main public API
        "commit",
        "undo",
        "redo",
        "canUndo",
        "canRedo",
        "getHistoryCommits",
        "reset",

        // Commit creation
        "createSnapshotCommit",

        // Collaboration compatibility
        "addExternalCommit",
        "resetFromCommits",

        // Preview
        "getIsPreviewing",
        "makePreviewableOperation",
        "makePreviewableAsyncOperation",
        "makeSavePoint",
    ];
    /** @type {import("plugins").EditorResources} */
    resources = {
        user_commands: [
            {
                id: "historyUndo",
                description: _t("Undo"),
                icon: "fa-undo",
                run: this.undo.bind(this),
            },
            {
                id: "historyRedo",
                description: _t("Redo"),
                icon: "fa-repeat",
                run: this.redo.bind(this),
            },
        ],
        ...(hasTouch() && {
            toolbar_groups: withSequence(5, { id: "historyMobile" }),
            toolbar_items: [
                {
                    id: "undo",
                    groupId: "historyMobile",
                    commandId: "historyUndo",
                    isDisabled: () => !this.canUndo(),
                    namespaces: ["compact", "expanded"],
                },
                {
                    id: "redo",
                    groupId: "historyMobile",
                    commandId: "historyRedo",
                    isDisabled: () => !this.canRedo(),
                    namespaces: ["compact", "expanded"],
                },
            ],
        }),
        shortcuts: [
            { hotkey: "control+z", commandId: "historyUndo", global: true },
            { hotkey: "control+y", commandId: "historyRedo", global: true },
            { hotkey: "control+shift+z", commandId: "historyRedo", global: true },
        ],
        history_data_keys: ["authorTimestamp", "commitTimestamp", "batchable", "previousCommitId"],

        on_editor_started_handlers: () => {
            this.reset(this.config.content);
        },
    };

    setup() {
        /** @type { HistoryCommitData } */
        this.authorTimestamp = Date.now();
        this._onKeyupResetContenteditableNodes = [];
        this.addDomListener(this.document, "beforeinput", this.onDocumentBeforeInput.bind(this));
        this.addDomListener(this.document, "input", this.onDocumentInput.bind(this));
        this.clean();
    }

    clean() {
        /** @type { EditorCommit[] } */
        this.commits = [];
        /** @type {Set<EditorCommitId>} Commits reverted by undo/redo operations */
        this.revertedCommits = new Set();
        /** @type {Set<EditorCommitId>} Commits reverted by restoring to a save point */
        this.discardedCommits = new Set();
        this.resetCurrentData();
        this.trigger("on_history_cleaned_handlers");
    }

    resetCurrentData() {
        this.authorTimestamp = Date.now();
        this.trigger("on_current_history_data_reset_handlers");
    }

    // ===============
    // Main public API
    // ===============

    /**
     * Create a commit from data and write it to history.
     *
     * @template { EditorCommitData } T
     * @param { object } params
     * @param { boolean } [params.batchable = false]
     * @returns { EditorCommit<T> }
     */
    commit({ batchable = false } = {}) {
        // Set the type of the commit here. That way, the state of undo and redo
        // is truly accessible when executing the `onChange` callback. It is
        // useful for external components if they execute `can(Undo|Redo)`.
        const data = this.processCommitData({
            data: {
                batchable,
                authorTimestamp: this.authorTimestamp,
            },
        });
        const commit = new EditorCommit({ data });
        return this.writeCommit(commit);
    }

    /**
     * Undo the last undo-able batch of commits.
     */
    undo() {
        if (this.commits.length === 1) {
            return;
        }
        this.trigger("on_will_undo_handlers");
        let revertedCommit;
        for (revertedCommit of this.getNextRevisionCommits("undo")) {
            this.revertCommit(revertedCommit, { ensureNewMutations: true });
            this.revertedCommits.add(revertedCommit.id);
            const commitData = this.processCommitData({
                data: {
                    batchable: revertedCommit.data.batchable,
                    commitTimestamp: revertedCommit.data.commitTimestamp,
                },
                origin: revertedCommit,
            });
            this.writeCommit(
                new EditorCommit({
                    type: "undo",
                    data: commitData,
                })
            );
        }
        this.trigger("on_undone_handlers", revertedCommit);
    }

    /**
     * Redo the last redo-able batch of commits.
     */
    redo() {
        this.trigger("on_will_redo_handlers");
        let revertedCommit;
        for (revertedCommit of this.getNextRevisionCommits("redo")) {
            this.revertCommit(revertedCommit, { ensureNewMutations: true });
            this.revertedCommits.add(revertedCommit.id);
            const commitData = this.processCommitData({
                data: {
                    batchable: revertedCommit.data.batchable,
                    commitTimestamp: revertedCommit.data.commitTimestamp,
                },
                origin: revertedCommit,
            });
            this.writeCommit(
                new EditorCommit({
                    type: "redo",
                    data: commitData,
                })
            );
        }
        this.trigger("on_redone_handlers", revertedCommit);
    }

    /**
     * Return true if there is at least one commit in history that can be
     * undone, false otherwise.
     *
     * @returns { boolean }
     */
    canUndo() {
        return this.getNextRevisionIndex("undo") > 0;
    }

    /**
     * Return true if there is at least one commit in history that can be
     * redone, false otherwise.
     *
     * @returns { boolean }
     */
    canRedo() {
        return this.getNextRevisionIndex("redo") > 0;
    }

    /**
     * Return a copy of the list of commits in history.
     *
     * @returns { EditorCommit[] }
     */
    getHistoryCommits() {
        return [...this.commits];
    }

    /**
     * Reset the history.
     *
     * @param { string } content
     */
    reset(content) {
        this.clean();
        this.writeCommit(this.createSnapshotCommit(), true);
        this.trigger("on_history_reset_handlers", content);
    }

    // =======================
    // Commit creation/writing
    // =======================

    /**
     * @param { EditorCommit } commit
     * @param { boolean } [silent = false] if true, skips any outside notification.
     * @returns { EditorCommit }
     */
    writeCommit(commit, silent = false) {
        // Set the timestamp of the commit or keep the timestamp of the commit
        // it reverts:
        commit.data.commitTimestamp ??= Date.now();
        commit.data.authorTimestamp ??= this.authorTimestamp;
        commit.data.previousCommitId = this.commits.at(-1)?.id;
        // @todo @phoenix should we allow to pause the making of a commit?
        // if (!this.commitsActive) {
        //     return;
        // }
        // @todo @phoenix link zws plugin
        // this._resetLinkZws();
        // @todo @phoenix sanitize plugin
        // this.sanitize();
        if (silent || (this.checkPredicates("has_commit_changes_predicates", commit) ?? false)) {
            this.commits.push(commit);
            // @todo @phoenix add this in the linkzws plugin.
            // this._setLinkZws();
            this.resetCurrentData();
            if (!silent) {
                // Notify of changes.
                this.trigger("on_history_committed_handlers", commit);
                this.config.onChange?.({ isPreviewing: this.isPreviewing });
            }
            return commit;
        } else {
            return false;
        }
    }

    /**
     * @returns { EditorCommit }
     */
    createSnapshotCommit() {
        const data = this.processThrough("snapshot_commit_data_processors", {
            authorTimestamp: this.authorTimestamp || Date.now(), // TODO AGE: I don't think the || is needed.
        });
        return new EditorCommit({ id: this.commits.at(-1)?.id, data });
    }

    // ===========================
    // Commit application/reversal
    // ===========================

    /**
     * Delegate the application of the changes in a given commit to the
     * concerned plugins.
     *
     * @param { EditorCommit } commit
     */
    applyCommit(commit, { ensureNewMutations = false } = {}) {
        this.trigger("on_apply_commit_handlers", commit, { ensureNewMutations });
    }

    /**
     * Delegate the reversal of the changes in a given commit to the concerned
     * plugins.
     *
     * @param { EditorCommit } commit
     * @param { Object } [param1 = {}]
     * TODO AGE: get rid of both these options.
     * @param { boolean } [param1.ensureNewMutations = false]
     * @param { boolean } [param1.restoreFocus = true]
     */
    revertCommit(commit, { ensureNewMutations = false, restoreFocus = true } = {}) {
        this.trigger("on_revert_commit_handlers", commit, {
            ensureNewMutations,
            restoreFocus,
        });
    }

    // ============================
    // Revision (undo/redo) helpers
    // ============================

    /**
     * Return the index in the history of the next commit to undo or redo, or -1
     * if none could be found.
     *
     * @param {"undo" | "redo"} type
     * @param { number } [fromIndex = this.commits.length] commit index from which to search
     * @returns { number }
     */
    getNextRevisionIndex(type, fromIndex = this.commits.length) {
        // Do not undo/redo the initial commit.
        for (let index = fromIndex - 1; index > 0; index--) {
            const commit = this.commits[index];
            if (this.isReversibleCommit(commit) && !this.discardedCommits.has(commit.id)) {
                if (type === "redo" && commit.type === "standard") {
                    return -1;
                } else if (
                    !this.revertedCommits.has(commit.id) &&
                    // Go back to first commit that can be undone.
                    ((type === "undo" && ["standard", "redo"].includes(commit.type)) ||
                        // Look for an "undo" commit that has not yet been redone.
                        (type === "redo" && commit.type === "undo"))
                ) {
                    return index;
                }
            }
        }
        // There is no commits left to be undone/redone, return an index that
        // does not point to any commit
        return -1;
    }

    /**
     * Returns the commits to be reverted/redone by a single undo or redo.
     *
     * @param {"undo" | "redo"} type
     * @returns { EditorCommit[] }
     */
    getNextRevisionCommits(type) {
        let referenceCommitIndex = this.getNextRevisionIndex(type);
        // Do not undo/redo the initial commit.
        if (referenceCommitIndex <= 0) {
            return [];
        }
        let nextCommitIndex = this.getNextRevisionIndex(type, referenceCommitIndex);
        const result = [this.commits[referenceCommitIndex]];
        while (
            nextCommitIndex >= 0 &&
            this.canCommitsBeBatched(referenceCommitIndex, nextCommitIndex)
        ) {
            result.push(this.commits[nextCommitIndex]);
            referenceCommitIndex = nextCommitIndex;
            nextCommitIndex = this.getNextRevisionIndex(type, nextCommitIndex);
        }
        return result;
    }

    /**
     * Returns true if commits can be batched in a single revision (undo/redo),
     * false otherwise.
     * Currrently: commits with a single mutation on the same text node.
     *
     * @param { number } index1
     * @param { number } index2
     * @returns { boolean }
     */
    canCommitsBeBatched(index1, index2) {
        const commit1 = this.commits[index1];
        const commit2 = this.commits[index2];
        if (!commit1.data.batchable || !commit2.data.batchable) {
            return false;
        }
        // Keep only if close enough in time.
        if (
            Math.abs(commit1.data.commitTimestamp - commit2.data.commitTimestamp) >
            COMMIT_DEBOUNCE_DELAY
        ) {
            return false;
        }
        return true;
    }

    // ===========================
    // Collaboration compatibility
    // ===========================

    /**
     * Insert a commit in the history.
     *
     * @param { EditorCommit } newCommit
     * @param { number } index
     */
    addExternalCommit(newCommit, index) {
        this.trigger("on_will_add_external_commit_handlers");
        const commitsAfterNewCommit = this.commits.slice(index);
        for (const commitToRevert of commitsAfterNewCommit.slice().reverse()) {
            this.revertCommit(commitToRevert);
        }
        this.applyCommit(newCommit);
        let root;
        this.getResource("commit_root_providers").find((p) => {
            root = p(newCommit);
            return root;
        });
        this.processThrough("normalize_processors", root);
        this.commits.splice(index, 0, newCommit);
        for (const commitToApply of commitsAfterNewCommit) {
            this.applyCommit(commitToApply);
        }
        this.trigger("on_external_commit_added_handlers");
    }

    /**
     * @param { EditorCommit[] } commits
     */
    resetFromCommits(commits) {
        this.trigger("on_will_reset_history_from_commits_handlers");
        this.editable.replaceChildren();
        this.clean();
        commits.forEach(this.applyCommit.bind(this));
        this.commits = commits;
        // todo: to test
        this.trigger("on_history_reset_from_commits_handlers");
        // TODO AGE: all this was wrapped in a `domMutations.withObserverOff`,
        // and there was a dispatch to on_history_reset_from_commits_handlers at the
        // end of the callback _and_ after the call to `withObserverOff`. I
        // replaced the `withObserverOff` with disabling/enabling the observer
        // in the resources dispatched here. So I wasn't able to put this second
        // dispatch again. Why was it needed?
    }

    /**
     * Give a chance to other plugins to prevent the reversal of the given
     * commit. Return true if it's reversible, false otherwise.
     *
     * @param { EditorCommit } commit
     * @returns { boolean }
     */
    isReversibleCommit(commit) {
        return this.checkPredicates("is_commit_reversible_predicates", commit) ?? true;
    }

    // =======
    // Preview
    // =======

    /**
     * Returns a function that can be later called to revert history to the
     * current state.
     * @returns { Function }
     */
    makeSavePoint() {
        const savePoint = this.processThrough("save_point_data_processors", {
            commit: this.commits.at(-1),
            hasBeenRestored: false,
        });
        return () => {
            if (savePoint.hasBeenRestored) {
                return;
            }
            this.trigger("on_will_restore_save_point_handlers", savePoint);
            const lastRevertedChanges = this.restoreToCommit(savePoint.commit);
            savePoint.hasBeenRestored = true;
            this.trigger("on_savepoint_restored_handlers", savePoint, lastRevertedChanges);
        };
    }

    processCommitData({ data = {}, origin } = {}) {
        return this.processThrough("pending_commit_data_processors", data, origin);
    }

    /**
     * Restores the editable to the state of a previous commit.
     * It does so by discarding the current draft and reverting reversible commits
     * until the specified commit index, while ensuring that irreversible commits
     * are maintained. This will add a new "restore" commit and set the reverted
     * commits's state to "discarded".
     *
     * @param { EditorCommit } commit
     * @returns { EditorCommitData | undefined }
     */
    restoreToCommit(commit) {
        if (commit === this.commits.at(-1)) {
            return;
        }
        let lastRevertedChanges = this.processCommitData({
            data: { authorTimestamp: this.authorTimestamp },
        });
        const commitsToRestore = this.getCommitsUntil(commit.id);
        const irreversibleCommits = [];
        for (const commitToRestore of commitsToRestore) {
            // Savepoint restoration is used for previews, so keep focus on the
            // external UI (for example the color picker) while reverting the
            // underlying editor commit.
            this.revertCommit(commitToRestore, {
                ensureNewMutations: true,
                restoreFocus: false,
            });
            this.trigger("on_commit_restored_handlers");
            if (commitToRestore.discard) {
                commitToRestore.discard();
                lastRevertedChanges = commitToRestore.data;
            } else {
                irreversibleCommits.unshift(commitToRestore);
            }
        }
        // Re-apply every non reversible commit (typically collaborators commits).
        for (const irreversibleCommit of irreversibleCommits) {
            this.applyCommit(irreversibleCommit, { ensureNewMutations: true });
            this.trigger("on_irreversible_commit_applied_handlers");
        }
        this.trigger("on_restored_to_commit_handlers", lastRevertedChanges);
        // Register resulting mutations as a new "restore" commit (prevent
        // undo).
        const restoreCommit = new EditorCommit({
            type: "restore",
            data: this.processCommitData({ origin: commit }),
        });
        this.writeCommit(restoreCommit);
        return lastRevertedChanges;
    }

    /**
     * Creates a set of functions to preview, apply, and revert an operation.
     * @param { Function } operation
     * @returns { PreviewableOperation }
     */
    makePreviewableOperation(operation) {
        let revertOperation = () => {};

        return {
            preview: (...args) => {
                revertOperation();
                revertOperation = this.makeSavePoint();
                this.isPreviewing = true;
                this.trigger("on_preview_handlers");
                operation(...args);
                // todo: We should not add a commit on preview as it would send
                // unnecessary commits in collaboration and let the other peer
                // see what we preview.
                //
                // The operation should be similar to the 'commit' (normalize
                // etc...) hence the call to 'commit' (but we need to remove it
                // for the collaboration).
                this.commit();
            },
            commit: (...args) => {
                revertOperation();
                this.isPreviewing = false;
                operation(...args);
                this.commit();
            },
            revert: () => {
                revertOperation();
                revertOperation = () => {};
                this.isPreviewing = false;
            },
        };
    }

    /**
     * Creates a set of functions to preview, apply, and revert an async operation.
     * @param { Function } operation
     * @returns { PreviewableOperation }
     */
    makePreviewableAsyncOperation(operation) {
        let revertOperation = async () => {};

        return {
            preview: async (...args) => {
                await revertOperation();
                const { promise, resolve } = Promise.withResolvers();
                const revertSavePoint = this.makeSavePoint();
                revertOperation = async () => {
                    await promise;
                    revertSavePoint();
                };
                this.isPreviewing = true;
                try {
                    await operation(...args);
                } catch (error) {
                    revertSavePoint();
                    throw error;
                } finally {
                    resolve();
                }
                if (this.isDestroyed) {
                    return;
                }
                // todo: We should not add a commit on preview as it would send
                // unnecessary commits in collaboration and let the other peer
                // see what we preview.
                //
                // The operation should be similar to the 'commit' (normalize
                // etc...) hence the call to 'commit' (but we need to remove it
                // for the collaboration).
                this.commit();
            },
            commit: async (...args) => {
                await revertOperation();
                this.isPreviewing = false;
                const revertSavePoint = this.makeSavePoint();
                try {
                    await operation(...args);
                } catch (error) {
                    revertSavePoint();
                    throw error;
                }
                if (this.isDestroyed) {
                    return;
                }
                this.commit();
            },
            revert: async () => {
                await revertOperation();
                revertOperation = () => {};
                this.isPreviewing = false;
            },
        };
    }

    getIsPreviewing() {
        return !!this.isPreviewing;
    }

    /**
     * Get the commits saved in commits between the commit of given id (not
     * included) and the most recent one. If no commit id is given, return all
     * commits but the first.
     *
     * @param { EditorCommitId } [commitId]
     * // TODO AGE: review this.
     * @returns { { ...EditorCommit, discard: false | () => void }[] }
     */
    getCommitsUntil(commitId) {
        const commitIndex = this.commits.findLastIndex((commit) => commit?.id === commitId);
        return this.commits
            .slice(commitIndex === -1 ? 1 : commitIndex + 1)
            .map((commit) => {
                if (commit && this.isReversibleCommit(commit)) {
                    commit.discard = () => {
                        this.discardedCommits.add(commit.id);
                    };
                }
                return commit;
            })
            .filter(Boolean)
            .reverse();
    }

    // =============
    // DOM Listeners
    // =============

    /**
     * @param { InputEvent } ev
     */
    onDocumentBeforeInput(ev) {
        if (this.editable.contains(ev.target)) {
            return;
        }
        if (["historyUndo", "historyRedo"].includes(ev.inputType)) {
            this._onKeyupResetContenteditableNodes.push(
                ...this.editable.querySelectorAll("[contenteditable=true]")
            );
            if (this.editable.getAttribute("contenteditable") === "true") {
                this._onKeyupResetContenteditableNodes.push(this.editable);
            }

            for (const node of this._onKeyupResetContenteditableNodes) {
                node.setAttribute("contenteditable", false);
            }
        }
    }

    /**
     * @param { InputEvent } ev
     */
    onDocumentInput(ev) {
        if (
            ["historyUndo", "historyRedo"].includes(ev.inputType) &&
            this._onKeyupResetContenteditableNodes.length
        ) {
            for (const node of this._onKeyupResetContenteditableNodes) {
                node.setAttribute("contenteditable", true);
            }
            this._onKeyupResetContenteditableNodes = [];
        }
    }
}
