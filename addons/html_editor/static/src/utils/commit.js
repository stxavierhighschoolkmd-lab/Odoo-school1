/**
 * @typedef { string } EditorCommitId
 * @typedef { "original" | "undo" | "redo" | "restore" | "reset" } EditorCommitType
 * @typedef { { [key: string]: any } } EditorCommitData
 */

/**
 * @template { Object } [T=EditorCommitData]
 */
export class EditorCommit {
    /**
     * @param { Object } [param0 = {}]
     * @param { EditorCommitId } [param0.id = this.generateId()]
     * @param { EditorCommitType } [param0.type = "original"]
     * @param { T } [param0.data = {}]
     */
    constructor({ id = this.generateId(), type = "original", data = {} } = {}) {
        /** @type { EditorCommitId } */
        this.id = id;
        /** @type { EditorCommitType } */
        this.type = type;
        /** @type { EditorCommitData & T } */
        this.data = data;
    }

    /**
     * @param {keyof (EditorCommitData & T)} key
     * @param {any} value
     */
    updateData(key, value) {
        this.data[key] = value;
    }

    /**
     * @returns { EditorCommitId }
     */
    generateId() {
        // No need for secure random number.
        return Math.floor(Math.random() * Math.pow(2, 52)).toString();
    }
}
