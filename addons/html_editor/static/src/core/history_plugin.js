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
 */
/**
 * @typedef { Object } HistoryShared
 * @property { HistoryPlugin['write'] } write
 * @property { HistoryPlugin['undo'] } undo
 * @property { HistoryPlugin['redo'] } redo
 * @property { HistoryPlugin['canUndo'] } canUndo
 * @property { HistoryPlugin['canRedo'] } canRedo
 * @property { HistoryPlugin['getHistoryCommits'] } getHistoryCommits
 * @property { HistoryPlugin['reset'] } reset
 * @property { HistoryPlugin['addExternalCommit'] } addExternalCommit
 * @property { HistoryPlugin['resetFromCommits'] } resetFromCommits
 * @property { HistoryPlugin['getCommitsUntil'] } getCommitsUntil
 * @property { HistoryPlugin['createSnapshotCommit'] } createSnapshotCommit
 */
/**
 * @typedef {(() => void)[]} on_external_commit_added_handlers
 * @typedef {(() => void)[]} on_history_cleaned_handlers
 * @typedef {(() => void)[]} on_history_reset_handlers
 * @typedef {(() => void)[]} on_history_reset_from_commits_handlers
 * @typedef {((revertedCommit: EditorCommit) => void)[]} on_undone_handlers
 * @typedef {((revertedCommit: EditorCommit) => void)[]} on_redone_handlers
 *
 * @typedef {((commit: EditorCommit) => boolean | undefined)[]} is_commit_reversible_predicates
 *
 * @typedef {((data: EditorCommitData) => EditorCommitData | undefined)[]} snapshot_commit_data_processors
 */

export const COMMIT_DEBOUNCE_DELAY = 250;

export class HistoryPlugin extends Plugin {
    static id = "history";
    static dependencies = ["selection"];
    static shared = [
        // Main public API
        "write",
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
        "getCommitsUntil",
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
        on_editor_started_handlers: () => {
            this.reset(this.config.content);
        },
        editor_commit_processors: (commit) => {
            commit.updateData("previousCommitId", this.commits.at(-1)?.id);
            return commit;
        },
    };

    setup() {
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
        this.authorTimestamp = Date.now();
        this.trigger("on_history_cleaned_handlers");
    }

    // ===============
    // Main public API
    // ===============

    /**
     * Create a commit from data and write it to history.
     *
     * @template { EditorCommitData } T
     * @param { Object } params
     * @param { EditorCommitType } params.type
     * @param { T } params.data
     * @param { EditorCommitMetadata } params.metadata
     * @returns { EditorCommit<T> }
     */
    write({ type, data, metadata }) {
        // Set the type of the commit here. That way, the state of undo and redo
        // is truly accessible when executing the `onChange` callback. It is
        // useful for external components if they execute `can(Undo|Redo)`.
        const commit = this.createCommit({ type, data, metadata });
        this.writeCommit(commit);
        return commit;
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
            this.trigger("on_single_commit_undone_handlers", revertedCommit);
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
            this.trigger("on_single_commit_redone_handlers", revertedCommit);
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
        this.writeCommit(this.createSnapshotCommit("reset"));
        this.trigger("on_history_reset_handlers", content);
    }

    // =======================
    // Commit creation/writing
    // =======================

    /**
     * @param { EditorCommit } commit
     * @returns { EditorCommit }
     */
    writeCommit(commit) {
        // Set the timestamp of the commit or keep the timestamp of the commit
        // it reverts (see `DomMutation`: `on_single_commit_(un|re)done_handlers`).
        commit.stamp();
        // @todo @phoenix should we allow to pause the making of a commit?
        // if (!this.commitsActive) {
        //     return;
        // }
        // @todo @phoenix link zws plugin
        // this._resetLinkZws();
        // @todo @phoenix sanitize plugin
        // this.sanitize();
        this.commits.push(commit);
        // @todo @phoenix add this in the linkzws plugin.
        // this._setLinkZws();
        this.authorTimestamp = Date.now();
        return commit;
    }

    /**
     * @param { Object } param0
     * @param { EditorCommitId } [param0.id]
     * @param { EditorCommitType } [param0.type]
     * @param { DomMutationCommitData } [param0.data]
     * @param { EditorCommitMetadata } [param0.metadata]
     * @returns { EditorCommit<DomMutationCommitData> }
     */
    createCommit({ id, type, data, metadata }) {
        return this.processThrough(
            "editor_commit_processors",
            new EditorCommit({
                id,
                type,
                data,
                metadata,
                authorTimestamp: this.authorTimestamp,
            })
        );
    }

    /**
     * @param { CommitType } [type = "original"]
     * @returns { EditorCommit }
     */
    createSnapshotCommit(type = "original") {
        const authorTimestamp = this.authorTimestamp || Date.now(); // TODO AGE: I don't think the || is needed.
        const data = this.processThrough("snapshot_commit_data_processors", {
            activeElementId: null,
            selection: {
                anchorNode: undefined,
                anchorOffset: undefined,
                focusNode: undefined,
                focusOffset: undefined,
            },
            selectionAfter: null,
        });
        return this.createCommit({
            id: this.commits.at(-1)?.id,
            type,
            authorTimestamp,
            data,
        });
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
    applyCommit(commit) {
        if (!this.delegateTo("apply_commit_overrides", commit)) {
            console.warn("Can't apply commit: no plugin responded.", commit);
        }
    }

    /**
     * Delegate the reversal of the changes in a given commit to the concerned
     * plugins.
     *
     * @param { EditorCommit } commit
     * @param { Object } [param1 = {}]
     * @param { boolean } [param1.ensureNewMutations = false]
     */
    revertCommit(commit, { ensureNewMutations = false } = {}) {
        if (!this.delegateTo("revert_commit_overrides", commit, { ensureNewMutations })) {
            console.warn("Can't revert commit: no plugin responded.", commit);
        }
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
        const regularTypes = ["original", "reset"];
        // Do not undo/redo the initial commit.
        for (let index = fromIndex - 1; index > 0; index--) {
            const commit = this.commits[index];
            if (this.isReversibleCommit(commit) && !this.discardedCommits.has(commit.id)) {
                if (type === "redo" && regularTypes.includes(commit.type)) {
                    return -1;
                } else if (
                    !this.revertedCommits.has(commit.id) &&
                    // Go back to first commit that can be undone.
                    ((type === "undo" && [...regularTypes, "redo"].includes(commit.type)) ||
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
        if (!commit1.metadata.batchable || !commit2.metadata.batchable) {
            return false;
        }
        // Keep only if close enough in time.
        if (
            Math.abs(commit1.metadata.commitTimestamp - commit2.metadata.commitTimestamp) >
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

    // TODO AGE: review the domMutation/history distribution of preview stuff.

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
