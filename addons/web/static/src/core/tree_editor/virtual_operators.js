import {
    applyTransformations,
    areEqualTrees,
    cloneTree,
    condition,
    updateCondition,
    connector,
    isTree,
    normalizeValue,
    operate,
    rewriteNConsecutiveChildren,
} from "./condition_tree";
import { boundDate, boundDatetime, getBounds, parseRelativeValue } from "./utils";

function splitPath(c) {
    if (typeof c.path !== "string" || c.path === "") {
        return { initialPath: "", lastPart: "" };
    }

    const pathParts = c.path.split(".");
    if (c.isProperty && pathParts.length >= 2) {
        return {
            initialPath: pathParts.slice(0, -2).join("."),
            lastPart: pathParts.slice(-2).join("."),
        };
    }

    const lastPart = pathParts.pop() || "";
    const initialPath = pathParts.join(".");
    return { initialPath, lastPart };
}

function isSimplePath(c) {
    return typeof c.path === "string" && !splitPath(c).initialPath;
}

function wrapInAny(tree, initialPath, negate) {
    if (initialPath) {
        return condition(initialPath, "any", cloneTree(tree), negate);
    }
    return { ...cloneTree(tree), negate };
}

function introduceSetOperators(tree, options = {}) {
    function _introduceSetOperator(c, options = {}) {
        const fieldType = options.getFieldDef?.(c.path)?.type;
        if (!["=", "!="].includes(c.operator) || !fieldType) {
            return;
        }
        if (fieldType === "boolean" && c.value === true) {
            return updateCondition(c, { operator: c.operator === "=" ? "set" : "not set" });
        } else if (!["many2one", "date", "datetime"].includes(fieldType) && c.value === false) {
            return updateCondition(c, { operator: c.operator === "=" ? "not set" : "set" });
        }
    }
    return operate(_introduceSetOperator, tree, options);
}

function eliminateSetOperators(tree) {
    function _removeSetOperator(c) {
        if (["set", "not set"].includes(c.operator)) {
            const op = c.operator === "set" ? (c.value ? "=" : "!=") : c.value ? "!=" : "=";
            return updateCondition(c, { operator: op });
        }
    }
    return operate(_removeSetOperator, tree);
}

function introduceStartsWithOperators(tree, options) {
    function _introduceStartsWithOperator(c, options) {
        const fieldType = options.getFieldDef?.(c.path)?.type;
        if (
            ["char", "text", "html"].includes(fieldType) &&
            c.operator === "=ilike" &&
            typeof c.value === "string"
        ) {
            if (c.value.endsWith("%")) {
                return updateCondition(c, { operator: "starts with", value: c.value.slice(0, -1) });
            }
        }
    }
    return operate(_introduceStartsWithOperator, tree, options);
}

function eliminateStartsWithOperators(tree) {
    function _eliminateStartsWithOperator(c) {
        if (c.operator === "starts with") {
            return updateCondition(c, { operator: "=ilike", value: `${c.value}%` });
        }
    }
    return operate(_eliminateStartsWithOperator, tree);
}

function isSimpleAnd(c) {
    if (
        c.type === "connector" &&
        c.value === "&" &&
        !c.negate &&
        c.children.length === 2 &&
        c.children.every((child) => child.type === "condition" && !child.negate)
    ) {
        return true;
    }
    return false;
}

function isBetween(c) {
    const [{ path: p1, operator: op1, value: value1 }, { path: p2, operator: op2, value: value2 }] =
        c.children;
    if (p1 === p2 && op1 === ">=" && op2 === "<=") {
        return { path: p1, value1, value2 };
    }
    return false;
}

function makeBetween(path, value1, value2, isProperty) {
    return connector("&", [
        condition(path, ">=", value1, false, isProperty),
        condition(path, "<=", value2, false, isProperty),
    ]);
}

function isStrictBetween(c) {
    const [{ path: p1, operator: op1, value: value1 }, { path: p2, operator: op2, value: value2 }] =
        c.children;
    if (p1 === p2 && op1 === ">=" && op2 === "<") {
        return { path: p1, value1, value2 };
    }
    return false;
}

function makeStrictBetween(path, value1, value2, isProperty) {
    return connector("&", [
        condition(path, ">=", value1, false, isProperty),
        condition(path, "<", value2, false, isProperty),
    ]);
}

/**
 * Returns the relative range the domain matches (by checking if the range is today +/- xxx d/w/m/y)
 * PAST relativity: PATH >= "today -Xd" AND < "today" OR Future relativity: PATH > "today" AND <= "today +Xd"
 * @param {Condition} c
 * @returns {boolean|Object} returns false if not a relative range compared to today
 */
function isRelativeBetween(c) {
    const [c1, c2] = c.children;
    const p1 = parseRelativeValue(c1.value);
    const p2 = parseRelativeValue(c2.value);
    const oneToday = p1?.diff === 0 || p2?.diff === 0; // (Both 0 is supported as relative range on purpose as well)

    if (c1.path !== c2.path || !p1 || !p2 || !oneToday) {
        return false;
    }

    const [todayCond, diffCond] = [p1.diff === 0 ? c1 : c2, p1?.diff === 0 ? c2 : c1];
    const offsetParsed = p1.diff === 0 ? p2 : p1;
    if (todayCond.operator === "<" && diffCond.operator === ">=" && offsetParsed.diff < 0) {
        // Return the negative diff directly so the widget gets -5
        return { diff: offsetParsed.diff, unit: offsetParsed.unit };
    } else if (todayCond.operator === ">" && diffCond.operator === "<=" && offsetParsed.diff >= 0) {
        // Return the positive diff directly so the widget gets +5
        return { diff: offsetParsed.diff, unit: offsetParsed.unit };
    }
    return false;
}

function makeRelativeBetween(path, value1, value2, isProperty, smartDates, fieldType) {
    const isFuture = value1 >= 0;
    const absVal = Math.abs(value1);
    let leftBound, rightBound;

    if (smartDates) {
        const unit = { week: "w", month: "m", year: "y" }[value2] || "d";
        const diff = `${absVal}${unit}`;
        leftBound = isFuture ? "today" : `today -${diff}`;
        rightBound = isFuture ? `today +${diff}` : "today";
    } else {
        const boundFn = fieldType === "date" ? boundDate : boundDatetime;
        const unit = `${value2}s`; // converts "day" to "days" for relativedelta
        leftBound = isFuture ? boundFn("") : boundFn(`${unit} = -${absVal}`);
        rightBound = isFuture ? boundFn(`${unit} = ${absVal}`) : boundFn("");
    }
    return connector("&", [
        condition(path, isFuture ? ">" : ">=", leftBound, false, isProperty),
        condition(path, isFuture ? "<=" : "<", rightBound, false, isProperty),
    ]);
}

function introduceInRangeOperators(tree, options = {}) {
    function _introduceInRangeOperator(c, options) {
        const path = c.children[0].path;
        const fieldType = options.getFieldDef?.(path)?.type;
        const isProperty = c.children[0].isProperty;
        const isDate = ["date", "datetime"].includes(fieldType);
        if (!isSimpleAnd(c) || !isDate || !isSimplePath(c.children[0])) {
            return;
        }
        const generateSmartDates = options.generateSmartDates ?? true;
        const base = condition(path, "in range", "dummy", false, isProperty);

        let res = isStrictBetween(c);
        if (res) {
            const bounds = getBounds(generateSmartDates, fieldType);
            const match = bounds.find(([, left, right]) =>
                generateSmartDates
                    ? res.value1 === left && res.value2 === right
                    : res.value1._expr === left._expr && res.value2._expr === right._expr
            );
            if (match) {
                return updateCondition(base, { value: [fieldType, match[0], false, false] });
            }
        }

        res = isRelativeBetween(c);
        if (res) {
            return updateCondition(base, {
                value: [fieldType, "relativeRange", res.diff, res.unit],
            });
        }
        res = isBetween(c);
        if (res) {
            return updateCondition(base, {
                value: [fieldType, "dateRange", ...normalizeValue([res.value1, res.value2])],
            });
        }
    }
    return operate(
        rewriteNConsecutiveChildren(_introduceInRangeOperator),
        tree,
        options,
        "connector"
    );
}

function eliminateInRangeOperators(tree, options = {}) {
    function _eliminateInRangeOperator(c, options) {
        if (c.operator !== "in range") {
            return;
        }
        const { initialPath, lastPart } = splitPath(c);
        const [fieldType, valueType, v1, v2] = c.value;
        const smartDates = options.generateSmartDates ?? true;
        let tree;
        if (valueType === "dateRange") {
            tree = makeBetween(lastPart, v1, v2, c.isProperty);
        } else if (valueType === "relativeRange") {
            tree = makeRelativeBetween(lastPart, v1, v2, c.isProperty, smartDates, fieldType);
        } else {
            const bounds = getBounds(smartDates, fieldType);
            const [, leftBound, rightBound] = bounds.find(([v]) => v === valueType);
            tree = makeStrictBetween(lastPart, leftBound, rightBound, c.isProperty);
        }
        return wrapInAny(tree, initialPath, c.negate);
    }
    return operate(_eliminateInRangeOperator, tree, options);
}

function introduceBetweenOperators(tree, options = {}) {
    function _introduceBetweenOperator(c, options) {
        const res = isBetween(c);
        if (!res) {
            return;
        }
        const { path, value1, value2 } = res;
        const fieldType = options.getFieldDef?.(path)?.type;
        const isProperty = c.children[0].isProperty;
        if (["integer", "float", "monetary"].includes(fieldType) && isSimplePath(c.children[0])) {
            return condition(path, "between", normalizeValue([value1, value2]), false, isProperty);
        }
    }
    return operate(
        rewriteNConsecutiveChildren(_introduceBetweenOperator),
        tree,
        options,
        "connector"
    );
}

function eliminateBetweenOperators(tree) {
    function _eliminateBetweenOperator(c) {
        if (c.operator !== "between") {
            return;
        }
        const { initialPath, lastPart } = splitPath(c);
        return wrapInAny(
            makeBetween(lastPart, c.value[0], c.value[1], c.isProperty),
            initialPath,
            c.negate
        );
    }
    return operate(_eliminateBetweenOperator, tree);
}

function eliminateAnyOperators(tree) {
    function _eliminateAnyOperator(c) {
        if (
            c.operator === "any" &&
            isTree(c.value) &&
            c.value.type === "condition" &&
            typeof c.path === "string" &&
            typeof c.value.path === "string" &&
            !c.negate &&
            !c.value.negate &&
            ["between", "in range"].includes(c.value.operator)
        ) {
            return updateCondition(c.value, { path: `${c.path}.${c.value.path}` });
        }
    }
    return operate(_eliminateAnyOperator, tree);
}

function removeFalseTrueLeaves(tree) {
    function _removeFalseTrueLeave(c) {
        if (c.operator !== "=" || c.value !== 1) {
            return;
        }
        if (c.path === 0) {
            return connector(c.negate ? "&" : "|", []);
        }
        if (c.path === 1) {
            return connector(c.negate ? "|" : "&", []);
        }
    }
    return operate(_removeFalseTrueLeave, tree);
}

export function introduceVirtualOperators(tree, options = {}) {
    return applyTransformations(
        [
            eliminateAnyOperators,
            introduceSetOperators,
            introduceStartsWithOperators,
            introduceBetweenOperators,
            introduceInRangeOperators,
        ],
        tree,
        options
    );
}

export function eliminateVirtualOperators(tree, options = {}) {
    return applyTransformations(
        [
            eliminateInRangeOperators,
            eliminateBetweenOperators,
            eliminateStartsWithOperators,
            eliminateSetOperators,
        ],
        tree,
        options
    );
}

export function areEquivalentTrees(tree, otherTree) {
    const simplifiedTree = removeFalseTrueLeaves(eliminateVirtualOperators(tree));
    const otherSimplifiedTree = removeFalseTrueLeaves(eliminateVirtualOperators(otherTree));
    return areEqualTrees(simplifiedTree, otherSimplifiedTree);
}
