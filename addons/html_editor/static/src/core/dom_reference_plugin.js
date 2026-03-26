import { Plugin } from "@html_editor/plugin";
import { NodeMap } from "@html_editor/utils/dom_info";
import { descendants } from "@html_editor/utils/dom_traversal";

/**
 * @typedef { string } NodeId
 *
 * @typedef { Object } Tree
 * @property { Node } node
 * @property { Tree[] } children
 *
 * @typedef { Object } SerializedNode
 * @property { number } nodeType
 * @property { NodeId } nodeId
 * @property { string } textValue
 * @property { string } tagName
 * @property { SerializedNode[] } children
 * @property { Record<string, string> } attributes
 */
/**
 * @property { DomReferencePlugin['getNodeById'] } getNodeById
 * @property { DomReferencePlugin['getNodeId'] } getNodeId
 */
export class DomReferencePlugin extends Plugin {
    static id = "domReference";
    static dependencies = ["sanitize"];
    static shared = [
        "reset",
        "hasNode",
        "setNodeId",
        "set",
        "getNodeById",
        "getNodeId",
        "serializeTree",
        "unserializeNode",
    ];
    resources = {
        on_history_cleaned_handlers: this.reset.bind(this),
    };

    setup() {
        this.reset();
    }

    reset() {
        this.nodeMap = new NodeMap();
        this.setNodeId(this.editable);
    }

    /**
     * @param { Node } node
     * @returns { boolean }
     */
    hasNode(node) {
        return this.nodeMap.hasNode(node);
    }

    /**
     * @param { Node } node
     * @returns { NodeId }
     */
    setNodeId(node, setDescendentsIds = true) {
        let id = this.getNodeId(node);
        if (!id) {
            id = node === this.editable ? "root" : this.generateId();
            this.set(id, node);
            if (setDescendentsIds) {
                node = node.firstChild;
                while (node) {
                    this.setNodeId(node);
                    node = node.nextSibling;
                }
            }
        }
        return id;
    }

    /**
     * @param { NodeId } id
     * @param { Node } node
     */
    set(id, node) {
        this.nodeMap.set(id, node);
    }

    /**
     * @param { NodeId } id
     * @returns { Node | undefined }
     */
    getNodeById(id) {
        return this.nodeMap.getNode(id);
    }

    /**
     * @param {Node} node
     * @returns {NodeId}
     */
    getNodeId(node) {
        return this.nodeMap.getId(node);
    }

    /**
     * @param { Tree } tree
     * @returns { SerializedNode | null }
     */
    serializeTree(tree) {
        const node = tree.node;
        const nodeId = this.getNodeId(node);
        if (!nodeId) {
            return null;
        }
        const result = {
            nodeType: node.nodeType,
            nodeId: nodeId,
        };
        if (node.nodeType === Node.TEXT_NODE) {
            result.textValue = node.nodeValue;
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            const childTreesToSerialize = this.processThrough(
                "serializable_descendants_processors",
                tree.children,
                node
            );
            result.tagName = node.tagName;
            result.attributes = Object.fromEntries(
                [...node.attributes].map((attr) => [attr.name, attr.value])
            );
            result.children = childTreesToSerialize
                .map((tree) => this.serializeTree(tree))
                .filter(Boolean);
        }
        return result;
    }

    /**
     * Unserialize a node and its children.
     *
     * @param { SerializedNode } node
     * @param { NodeMap } [nodeMap = this.nodeMap]
     * @returns { Node | null }
     */
    unserializeNode(node, nodeMap = this.nodeMap) {
        /** @type { Map<Node, string> } */
        const newNodesMap = new Map();
        /**
         * Recursive helper.
         *
         * @param { SerializedNode } serializedNode
         * @returns { Node | null }
         */
        const unserialize = (serializedNode) => {
            let node = nodeMap.getNode(serializedNode.nodeId);
            if (!node) {
                if (serializedNode.nodeType === Node.TEXT_NODE) {
                    node = this.document.createTextNode(serializedNode.textValue);
                } else if (serializedNode.nodeType === Node.ELEMENT_NODE) {
                    node = this.document.createElement(serializedNode.tagName);
                    for (const key in serializedNode.attributes) {
                        node.setAttribute(key, serializedNode.attributes[key]);
                    }
                    node.append(...serializedNode.children.map(unserialize).filter(Boolean));
                } else {
                    console.warn(`Can't unserialize a node of type ${serializedNode.nodeType}.`);
                    return null;
                }
                newNodesMap.set(node, serializedNode.nodeId);
            }
            return node;
        };

        let unserializedNode = unserialize(node, nodeMap);
        if (unserializedNode) {
            const fakeNode = this.document.createElement("fake-el");
            // TODO AGE: this next line has the effect of REMOVING THE NODE FROM
            // THE DOM! But changing it for a clone breaks a bunch of tests.
            fakeNode.appendChild(unserializedNode);
            this.dependencies.sanitize.sanitize(fakeNode);
            unserializedNode = fakeNode.firstChild;
            if (unserializedNode) {
                // Only assing id to the remaining nodes, otherwise the removed
                // nodes will still be accessible through the nodeMap and could
                // lead to security issues.
                for (const node of [unserializedNode, ...descendants(unserializedNode)]) {
                    if (!this.nodeMap.hasNode(node)) {
                        const id = newNodesMap.get(node);
                        if (id) {
                            this.nodeMap.set(id, node);
                        }
                    }
                }
                return unserializedNode;
            }
        }
        return null;
    }

    /**
     * @returns { NodeId  }
     */
    generateId() {
        // No need for secure random number.
        return Math.floor(Math.random() * Math.pow(2, 52)).toString();
    }
}
