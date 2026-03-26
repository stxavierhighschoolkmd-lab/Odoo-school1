import { expression } from "./condition_tree";

export function disambiguate(value, displayNames) {
    if (!Array.isArray(value)) {
        return value === "";
    }
    let hasSomeString = false;
    let hasSomethingElse = false;
    for (const val of value) {
        if (val === "") {
            return true;
        }
        if (typeof val === "string" || (displayNames && isId(val))) {
            hasSomeString = true;
        } else {
            hasSomethingElse = true;
        }
    }
    return hasSomeString && hasSomethingElse;
}

export function isId(value) {
    return Number.isInteger(value) && value >= 1;
}

export function getResModel(fieldDef) {
    if (fieldDef) {
        return fieldDef.is_property ? fieldDef.comodel : fieldDef.relation;
    }
    return null;
}

const SPECIAL_FIELDS = ["country_id", "user_id", "partner_id", "stage_id", "id"];

export function getDefaultPath(fieldDefs) {
    for (const name of SPECIAL_FIELDS) {
        const fieldDef = fieldDefs[name];
        if (fieldDef) {
            return fieldDef.name;
        }
    }
    const name = Object.keys(fieldDefs)[0];
    if (name) {
        return name;
    }
    throw new Error(`No field found`);
}

// --- Date range utils, used by ExpressionEditor --- //

export function boundDate(delta) {
    if (!delta) {
        return expression(`context_today().strftime("%Y-%m-%d")`);
    }
    return expression(`(context_today() + relativedelta(${delta})).strftime('%Y-%m-%d')`);
}

export function boundDatetime(delta) {
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

export function getBounds(generateSmartDates, fieldType) {
    if (generateSmartDates) {
        return BOUNDS_SMART_DATES;
    }
    return fieldType === "date" ? BOUNDS_DATE : BOUNDS_DATETIME;
}

/**
 * Parses a relative date string or domain expression into a standardized diff and unit.
 * eg. parseRelativeValue("today - 5d", true) --> returns: { diff: -5, unit: "day" }
 * eg. parseRelativeValue({ _expr: "relativedelta(months=-2)" }, false) -> returns: { diff: -2, unit: "month" }
 * eg. parseRelativeValue("today") --> returns: { diff: 0, unit: "day" }
 */
export function parseRelativeValue(val, smartDates) {
    if (typeof val === "string") {
        const match = val.trim().match(/^today\s*([+-])\s*(\d+)\s*([dwmy])$/);
        if (match) {
            const diff = Number(match[1] + match[2]); // match[1] is the sign, match[2] the value
            const unit = { d: "day", w: "week", m: "month", y: "year" }[match[3]];
            return { diff, unit };
        } else if (val.trim() === "today") {
            return { diff: 0, unit: "day" };
        }
    } else if (val && typeof val === "object" && typeof val._expr === "string") {
        const relRegex = /relativedelta\(\s*(days|weeks|months|years)\s*=\s*([+-]?\d+)\s*\)/;
        const relDate = val._expr.match(relRegex);
        if (relDate) {
            const unit = relDate[1].slice(0, -1); // (eg. days -> day)
            const diff = Number(relDate[2]);
            return { diff, unit };
        } else if (val._expr.includes("context_today()")) {
            return { diff: 0, unit: "day" };
        }
    }
    return null;
}
