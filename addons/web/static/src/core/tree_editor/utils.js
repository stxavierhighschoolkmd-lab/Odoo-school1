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
