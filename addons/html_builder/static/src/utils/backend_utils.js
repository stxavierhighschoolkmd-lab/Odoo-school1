import { browser } from "@web/core/browser/browser";
import { getActiveHotkey } from "@web/core/hotkeys/hotkey_service";
import { localization } from "@web/core/l10n/localization";
import { Cache } from "@web/core/utils/cache";

/**
 * Makes a 2D matrix of elements from left to right and from top to bottom.
 *
 * @param {HTMLElement} containerEl
 * @param {string} selector - selector for descendants of containerEl
 * @returns {Array<Array<HTMLElement>>} matrix
 */
function makeElementsPositionMatrix(containerEl, selector) {
    const leftMap = new Map();
    for (const el of containerEl.querySelectorAll(selector)) {
        if (!leftMap.has(el.offsetLeft)) {
            leftMap.set(el.offsetLeft, [el]);
        } else {
            leftMap.get(el.offsetLeft).push(el);
        }
    }
    const matrix = [...leftMap.keys()]
        .sort((a, b) => a - b)
        .map((leftPos) => leftMap.get(leftPos).sort((a, b) => a.offsetTop - b.offsetTop));

    return matrix;
}

const matrixCache = new Cache(
    (containerEl, selector) => makeElementsPositionMatrix(containerEl, selector),
    (containerEl) => `${containerEl.className}_${containerEl.scrollHeight}`
);

/**
 * Handles navigation keys (arrows, home, end, page up, page down) on a 2D
 * layout.
 *
 * @param {KeyboardEvent} ev
 * @param {Object} options
 * @param {HTMLElement} options.containerEl - common container ancestor.
 * @param {string} options.focusedItemSelector - selector to target the elements
 * to use for the navigation logic. The selector will be queried both up
 * (`ev.currentTarget.closest`) and down (`containerEl.querySelectorAll`).
 * @param {string} [options.focusableElSelector] - selector used if the
 * focusable selector is different from `focusedItemSelector`.
 */
export function handleMatrixKeyNavigation(
    ev,
    { containerEl, focusedItemSelector, focusableElSelector }
) {
    const hotkey = getActiveHotkey(ev);
    const focusedEl = ev.currentTarget.closest(focusedItemSelector);
    let matrix = matrixCache.read(containerEl, focusedItemSelector);
    if (!matrix[0][0].isConnected) {
        matrixCache.clear(containerEl);
        matrix = matrixCache.read(containerEl, focusedItemSelector);
    }
    if (
        [
            "arrowup",
            "arrowdown",
            "arrowleft",
            "arrowright",
            "home",
            "end",
            "pagedown",
            "pageup",
        ].includes(hotkey)
    ) {
        ev.preventDefault(); // Do not scroll.
        let nextFocusedEl;
        const elMatrixColIdx = matrix.findIndex((col) => col.includes(focusedEl));
        if (["home", "end"].includes(hotkey)) {
            const isRTL = localization.direction === "rtl";
            const firstCol = isRTL ? matrix.at(-1) : matrix[0];
            const lastCol = isRTL ? matrix[0] : matrix.at(-1);
            nextFocusedEl = hotkey === "home" ? firstCol[0] : lastCol.at(-1);
        } else if (["arrowup", "arrowdown"].includes(hotkey)) {
            const elMatrixColumn = matrix[elMatrixColIdx];
            const elIdx = elMatrixColumn.indexOf(focusedEl);
            if (hotkey === "arrowup") {
                nextFocusedEl = elMatrixColumn[Math.max(elIdx - 1, 0)];
            } else if (hotkey === "arrowdown") {
                nextFocusedEl = elMatrixColumn[Math.min(elIdx + 1, elMatrixColumn.length - 1)];
            }
        } else if (["arrowleft", "arrowright"].includes(hotkey)) {
            const rect = focusedEl.getBoundingClientRect();
            let nextCol;
            if (hotkey === "arrowleft") {
                if (elMatrixColIdx === 0) {
                    return;
                }
                nextCol = matrix[elMatrixColIdx - 1];
            } else if (hotkey === "arrowright") {
                if (elMatrixColIdx === matrix.length - 1) {
                    return;
                }
                nextCol = matrix[elMatrixColIdx + 1];
            }
            nextFocusedEl = nextCol.findLast(
                (el) => rect.y + rect.height / 2 >= el.getBoundingClientRect().y
            );
        } else if (["pageup", "pagedown"].includes(hotkey)) {
            return;
        }
        if (focusableElSelector) {
            nextFocusedEl = nextFocusedEl.querySelector(focusableElSelector);
        }
        const reducedMotion = browser.matchMedia("(prefers-reduced-motion: reduce)").matches;
        nextFocusedEl.scrollIntoView({
            block: "nearest",
            behavior: reducedMotion ? "instant" : "smooth",
        });
        nextFocusedEl.focus();
    }
}
