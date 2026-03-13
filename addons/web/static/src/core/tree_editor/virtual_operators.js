import {
    applyTransformations,
    areEqualTrees,
    cloneTree,
    condition,
    connector,
    expression,
    FALSE_TREE,
    isTree,
    normalizeValue,
    operate,
    rewriteNConsecutiveChildren,
    TRUE_TREE,
} from "./condition_tree";
import { parseRelativeValue } from "./utils";

function splitPath(path, is_property) {
    if (typeof path !== "string" || path === "") {
        return { initialPath: "", lastPart: "" };
    }

    const pathParts = path.split(".");
    if (is_property && pathParts.length >= 2) {
        return {
            initialPath: pathParts.slice(0, -2).join("."),
            lastPart: pathParts.slice(-2).join("."),
        };
    }

    const lastPart = pathParts.pop() || "";
    const initialPath = pathParts.join(".");
    return { initialPath, lastPart };
}

function isSimplePath(path, isProperty) {
    return typeof path === "string" && !splitPath(path, isProperty).initialPath;
}

function wrapInAny(tree, initialPath, negate) {
    let con = cloneTree(tree);
    if (initialPath) {
        con = condition(initialPath, "any", con);
    }
    con.negate = negate;
    return con;
}

function introduceSetOperators(tree, options = {}) {
    function _introduceSetOperator(c, options = {}) {
        const { negate, path, operator, value } = c;
        const fieldType = options.getFieldDef?.(path)?.type;
        if (["=", "!="].includes(operator)) {
            if (fieldType) {
                if (fieldType === "boolean" && value === true) {
                    return condition(path, operator === "=" ? "set" : "not set", value, negate);
                } else if (
                    !["many2one", "date", "datetime"].includes(fieldType) &&
                    value === false
                ) {
                    return condition(path, operator === "=" ? "not set" : "set", value, negate);
                }
            }
        }
    }
    return operate(_introduceSetOperator, tree, options);
}

function eliminateSetOperators(tree) {
    function _removeSetOperator(c) {
        const { negate, path, operator, value, isProperty } = c;
        if (["set", "not set"].includes(operator)) {
            if (value === true) {
                return condition(path, operator === "set" ? "=" : "!=", value, negate, isProperty);
            }
            return condition(path, operator === "set" ? "!=" : "=", value, negate, isProperty);
        }
    }
    return operate(_removeSetOperator, tree);
}

function introduceStartsWithOperators(tree, options) {
    function _introduceStartsWithOperator(c, options) {
        const { negate, path, operator, value, isProperty } = c;
        const fieldType = options.getFieldDef?.(path)?.type;
        if (
            ["char", "text", "html"].includes(fieldType) &&
            operator === "=ilike" &&
            typeof value === "string"
        ) {
            if (value.endsWith("%")) {
                return condition(path, "starts with", value.slice(0, -1), negate, isProperty);
            }
        }
    }
    return operate(_introduceStartsWithOperator, tree, options);
}

function eliminateStartsWithOperators(tree) {
    function _eliminateStartsWithOperator(c) {
        const { negate, path, operator, value, isProperty } = c;
        if (operator === "starts with") {
            return condition(path, "=ilike", `${value}%`, negate, isProperty);
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

function boundDate(delta) {
    if (!delta) {
        return expression(`context_today().strftime("%Y-%m-%d")`);
    }
    return expression(`(context_today() + relativedelta(${delta})).strftime('%Y-%m-%d')`);
}

function boundDatetime(delta) {
    if (!delta) {
        return expression(
            `datetime.datetime.combine(context_today(), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S")`
        );
    }
    return expression(
        `datetime.datetime.combine(context_today() + relativedelta(${delta}), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S")`
    );
}

const BOUNDS_SMART_DATES = [
    ["today", "today", "today +1d"],
    ["last7Days", "today -7d", "today"],
    ["last30Days", "today -30d", "today"],
    ["monthToDate", "today =1d", "today +1d"],
    ["lastMonth", "today =1d -1m", "today =1d"],
    ["yearToDate", "today =1m =1d", "today +1d"],
    ["last365Days", "today -365d", "today"],
];
const DELTAS = [
    ["today", "", "days = 1"],
    ["last7Days", "days = -7", ""],
    ["last30Days", "days = -30", ""],
    ["monthToDate", "day = 1", "days = 1"],
    ["lastMonth", "day = 1, months = -1", "day = 1"],
    ["yearToDate", "day = 1, month = 1", "days = 1"],
    ["last365Days", "days = -365", ""],
];
const BOUNDS_DATE = DELTAS.map(([k, l, r]) => [k, boundDate(l), boundDate(r)]);
const BOUNDS_DATETIME = DELTAS.map(([k, l, r]) => [k, boundDatetime(l), boundDatetime(r)]);

function getBounds(generateSmartDates, fieldType) {
    return generateSmartDates
        ? BOUNDS_SMART_DATES
        : fieldType === "date"
        ? BOUNDS_DATE
        : BOUNDS_DATETIME;
}

function introduceInRangeOperators(tree, options = {}) {
    function _introduceInRangeOperator(c, options) {
        const path = c.children[0].path;
        const fieldType = options.getFieldDef?.(path)?.type;
        const isProperty = c.children[0].isProperty;
        const isDate = ["date", "datetime"].includes(fieldType);
        if (!isSimpleAnd(c) || !isDate || !isSimplePath(c.children[0].path, isProperty)) {
            return;
        }
        const generateSmartDates = options.generateSmartDates ?? true;
        let res = isStrictBetween(c);
        if (res) {
            const bounds = getBounds(generateSmartDates, fieldType);
            for (const [valueType, leftBound, rightBound] of bounds) {
                if (
                    generateSmartDates
                        ? res.value1 === leftBound && res.value2 === rightBound
                        : res.value1._expr === leftBound._expr &&
                          res.value2._expr === rightBound._expr
                ) {
                    return condition(
                        path,
                        "in range",
                        [fieldType, valueType, false, false],
                        false,
                        isProperty
                    );
                }
            }
        }

        res = isRelativeBetween(c);
        if (res) {
            const value = [fieldType, "relativeRange", res.diff, res.unit];
            return condition(path, "in range", value);
        }
        res = isBetween(c);
        if (res) {
            const { path, value1, value2 } = res;
            return condition(
                path,
                "in range",
                [
                    fieldType,
                    "dateRange",
                    // @ts-ignore
                    ...normalizeValue([value1, value2]),
                ],
                false,
                isProperty
            );
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
        const { negate, path, operator, value, isProperty } = c;
        // @ts-ignore
        if (operator !== "in range") {
            return;
        }
        const { initialPath, lastPart } = splitPath(path, isProperty);
        const [fieldType, valueType, value1, value2] = value;
        const smartDates = options.generateSmartDates ?? true;
        let tree;
        if (valueType === "dateRange") {
            tree = makeBetween(lastPart, value1, value2, isProperty);
        } else if (valueType === "relativeRange") {
            tree = makeRelativeBetween(lastPart, value1, value2, isProperty, smartDates, fieldType);
        } else {
            const bounds = getBounds(smartDates, fieldType);
            const [, leftBound, rightBound] = bounds.find(([v]) => v === valueType);
            tree = makeStrictBetween(lastPart, leftBound, rightBound, isProperty);
        }
        return wrapInAny(tree, initialPath, negate);
    }
    return operate(_eliminateInRangeOperator, tree, options);
}

function introduceBetweenOperators(tree, options = {}) {
    function _introduceBetweenOperator(c, options) {
        const res = isBetween(c);
        if (!res) {
            return;
        }
        // @ts-ignore
        const { path, value1, value2 } = res;
        const fieldType = options.getFieldDef?.(path)?.type;
        if (["integer", "float", "monetary"].includes(fieldType) && isSimplePath(path)) {
            return condition(path, "between", normalizeValue([value1, value2]));
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
        const { negate, path, operator, value, isProperty } = c;
        // @ts-ignore
        if (operator !== "between") {
            return;
        }
        const { initialPath, lastPart } = splitPath(path, isProperty);
        return wrapInAny(
            makeBetween(lastPart, value[0], value[1], isProperty),
            initialPath,
            negate
        );
    }
    return operate(_eliminateBetweenOperator, tree);
}

function _eliminateAnyOperator(c) {
    const { path, operator, value, negate } = c;
    if (
        operator === "any" &&
        isTree(value) &&
        value.type === "condition" &&
        typeof path === "string" &&
        typeof value.path === "string" &&
        !negate &&
        !value.negate &&
        ["between", "in range"].includes(value.operator)
    ) {
        return condition(
            `${path}.${value.path}`,
            value.operator,
            value.value,
            false,
            value.isProperty
        );
    }
}

function eliminateAnyOperators(tree) {
    return operate(_eliminateAnyOperator, tree);
}

function removeFalseTrueLeaves(tree) {
    function _removeFalseTrueLeave(c) {
        const { path, operator, value, negate, isProperty } = c;
        if (areEqualTrees(condition(path, operator, value, false, isProperty), FALSE_TREE)) {
            return connector(negate ? "&" : "|", []);
        }
        if (areEqualTrees(condition(path, operator, value, false, isProperty), TRUE_TREE)) {
            return connector(negate ? "|" : "&", []);
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
