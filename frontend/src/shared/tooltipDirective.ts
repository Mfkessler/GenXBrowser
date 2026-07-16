import {
  autoUpdate,
  computePosition,
  offset,
  flip,
  shift,
  arrow as arrowMiddleware,
  type Placement,
} from "@floating-ui/dom";
import type { Directive, DirectiveBinding } from "vue";

/**
 * Unified tooltip directive for consistent tooltip behavior across the app.
 *
 * Usage:
 *   v-tooltip="'Tooltip text'"                   → top placement (default)
 *   v-tooltip:right="'Tooltip text'"              → right placement
 *   v-tooltip:left="'Tooltip text'"               → left placement
 *   v-tooltip:bottom="'Tooltip text'"             → bottom placement
 *   v-tooltip="{ text: 'Tooltip', placement: 'right' }"  → object form
 *
 * All tooltips render into document.body via DOM manipulation (equivalent to
 * Teleport), so they are never clipped by parent overflow:hidden.
 *
 * Tooltips do NOT inherit parent opacity — they are independent DOM elements.
 */

interface TooltipState {
  tooltipEl: HTMLElement | null;
  arrowEl: HTMLElement | null;
  showTimer: ReturnType<typeof setTimeout> | null;
  hideTimer: ReturnType<typeof setTimeout> | null;
  removeTimer: ReturnType<typeof setTimeout> | null;
  text: string;
  placement: Placement;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onFocus: () => void;
  onBlur: () => void;
  onTouchStart: () => void;
  onTouchEnd: () => void;
  onTouchCancel: () => void;
  cleanup: (() => void) | null;
  touchTimer: ReturnType<typeof setTimeout> | null;
  touchTooltipShown: boolean;
  suppressFocusUntil: number;
}

const TOOLTIP_STATES = new WeakMap<HTMLElement, TooltipState>();
// Enumerable companion to the WeakMap above — needed so `destroyAllTooltips()`
// can force-clean every active tooltip when a modal/view is torn down without
// going through this element's own `unmounted` hook (e.g. a parent removed via
// a non-Vue-tracked path, or a route change while a tooltip is mid-transition).
const ACTIVE_ELEMENTS = new Set<HTMLElement>();
const SHOW_DELAY = 150;
const HIDE_DELAY = 50;
const LONG_TOUCH_DELAY = 550;
const TOUCH_FOCUS_SUPPRESS_MS = 800;

/** Fully tears down a tooltip's DOM node, timers, and autoUpdate listener. */
function destroyTooltipState(el: HTMLElement, state: TooltipState) {
  if (state.showTimer) clearTimeout(state.showTimer);
  if (state.hideTimer) clearTimeout(state.hideTimer);
  if (state.removeTimer) clearTimeout(state.removeTimer);
  if (state.touchTimer) clearTimeout(state.touchTimer);
  state.showTimer = null;
  state.hideTimer = null;
  state.removeTimer = null;
  state.touchTimer = null;

  if (state.cleanup) {
    state.cleanup();
    state.cleanup = null;
  }
  if (state.tooltipEl?.parentNode) {
    state.tooltipEl.parentNode.removeChild(state.tooltipEl);
  }
  ACTIVE_ELEMENTS.delete(el);
}

/**
 * Safety net for cases where a tooltip's trigger element is removed/hidden
 * without this directive's own `unmounted` hook firing (e.g. a parent modal
 * torn down by a non-reactive DOM operation, or a route change). Call this
 * whenever a modal/view closes to guarantee no orphaned tooltip is left
 * floating at its default top-left position.
 */
export function destroyAllTooltips() {
  for (const el of Array.from(ACTIVE_ELEMENTS)) {
    const state = TOOLTIP_STATES.get(el);
    if (state) destroyTooltipState(el, state);
  }
}

function createTooltipEl(): { tooltipEl: HTMLElement; arrowEl: HTMLElement } {
  const tooltipEl = document.createElement("div");
  tooltipEl.setAttribute("role", "tooltip");
  // Use only inline styles — no Tailwind classes, so nothing is tree-shaken away
  tooltipEl.style.cssText =
    "position:fixed;z-index:99999;pointer-events:none;opacity:0;transition:opacity 150ms;" +
    "background:#2563eb;color:#fff;font-size:0.75rem;line-height:1rem;border-radius:0.375rem;" +
    "padding:0.5rem 0.75rem;max-width:20rem;" +
    "box-shadow:0 10px 15px -3px rgb(0 0 0/.1),0 4px 6px -4px rgb(0 0 0/.1);" +
    "white-space:normal;word-wrap:break-word;top:0;left:0;width:max-content;";

  const arrowEl = document.createElement("div");
  arrowEl.style.cssText =
    "position:absolute;width:8px;height:8px;background:#2563eb;transform:rotate(45deg);";
  tooltipEl.appendChild(arrowEl);

  return { tooltipEl, arrowEl };
}

function updatePosition(
  triggerEl: HTMLElement,
  tooltipEl: HTMLElement,
  arrowEl: HTMLElement,
  placement: Placement,
) {
  // Defensive: if the trigger (or its own tooltip node) is no longer attached
  // to the document — e.g. its host modal was torn down without this
  // directive's `unmounted` hook running — force-destroy instead of
  // computing/leaving the tooltip pinned at its default top-left position.
  if (!triggerEl.isConnected || !tooltipEl.isConnected) {
    const state = TOOLTIP_STATES.get(triggerEl);
    if (state) destroyTooltipState(triggerEl, state);
    return;
  }

  computePosition(triggerEl, tooltipEl, {
    strategy: "fixed",
    placement,
    middleware: [
      offset(8),
      flip(),
      shift({ padding: 8 }),
      arrowMiddleware({ element: arrowEl }),
    ],
  }).then(({ x, y, placement: finalPlacement, middlewareData }) => {
    if (!triggerEl.isConnected || !tooltipEl.isConnected) {
      const state = TOOLTIP_STATES.get(triggerEl);
      if (state) destroyTooltipState(triggerEl, state);
      return;
    }
    Object.assign(tooltipEl.style, {
      left: `${x}px`,
      top: `${y}px`,
    });

    // Position arrow
    const arrowData = middlewareData.arrow;
    if (arrowData) {
      const side = finalPlacement.split("-")[0];
      const staticSide: Record<string, string> = {
        top: "bottom",
        right: "left",
        bottom: "top",
        left: "right",
      };
      const opposingSide = staticSide[side] || "bottom";

      Object.assign(arrowEl.style, {
        left: arrowData.x != null ? `${arrowData.x}px` : "",
        top: arrowData.y != null ? `${arrowData.y}px` : "",
        [opposingSide]: "-4px",
        // Reset other sides
        ...(opposingSide !== "top" && { top: arrowData.y != null ? `${arrowData.y}px` : "" }),
        ...(opposingSide !== "left" && { left: arrowData.x != null ? `${arrowData.x}px` : "" }),
        ...(opposingSide !== "bottom" && { bottom: "" }),
        ...(opposingSide !== "right" && { right: "" }),
      });
    }
  }).catch(() => {
    // If positioning fails (e.g. the reference got detached mid-calculation),
    // destroy rather than leave the tooltip visible at its unpositioned
    // top-left default.
    const state = TOOLTIP_STATES.get(triggerEl);
    if (state) destroyTooltipState(triggerEl, state);
  });
}

function showTooltip(el: HTMLElement) {
  const state = TOOLTIP_STATES.get(el);
  if (!state || !state.text) return;

  // Clear any pending hide
  if (state.hideTimer) {
    clearTimeout(state.hideTimer);
    state.hideTimer = null;
  }

  state.showTimer = setTimeout(() => {
    // The trigger may have been removed from the DOM while this delayed show
    // was pending (e.g. its host modal closed) without this directive's
    // `unmounted` hook running for it. Bail out rather than creating/showing
    // a tooltip for a dead element.
    if (!state.text || !el.isConnected) return;

    // Create tooltip if needed
    if (!state.tooltipEl) {
      const { tooltipEl, arrowEl } = createTooltipEl();
      state.tooltipEl = tooltipEl;
      state.arrowEl = arrowEl;
    }

    // Set text content (insert before the arrow)
    const textNode = state.tooltipEl.firstChild;
    if (textNode && textNode !== state.arrowEl) {
      textNode.textContent = state.text;
    } else {
      state.tooltipEl.insertBefore(
        document.createTextNode(state.text),
        state.arrowEl,
      );
    }

    // Append to body
    if (!state.tooltipEl.parentNode) {
      document.body.appendChild(state.tooltipEl);
    }
    ACTIVE_ELEMENTS.add(el);

    // Position the tooltip and keep it in sync with scroll/resize
    if (state.cleanup) {
      state.cleanup();
      state.cleanup = null;
    }
    state.cleanup = autoUpdate(
      el,
      state.tooltipEl,
      () => {
        // autoUpdate keeps firing on scroll/resize/mutation while the
        // tooltip is visible — use each tick as an extra chance to notice
        // the trigger going away and self-destruct instead of drifting to
        // the unpositioned top-left default.
        if (!el.isConnected) {
          destroyTooltipState(el, state);
          return;
        }
        updatePosition(el, state.tooltipEl!, state.arrowEl!, state.placement);
      },
    );
    updatePosition(el, state.tooltipEl, state.arrowEl!, state.placement);

    // Show with animation
    requestAnimationFrame(() => {
      if (state.tooltipEl && el.isConnected) {
        state.tooltipEl.style.opacity = "1";
      }
    });
  }, SHOW_DELAY);
}

function hideTooltip(el: HTMLElement) {
  const state = TOOLTIP_STATES.get(el);
  if (!state) return;

  // Clear any pending show
  if (state.showTimer) {
    clearTimeout(state.showTimer);
    state.showTimer = null;
  }

  state.hideTimer = setTimeout(() => {
    // Stop autoUpdate listener
    if (state.cleanup) {
      state.cleanup();
      state.cleanup = null;
    }
    if (state.tooltipEl) {
      state.tooltipEl.style.opacity = "0";
      // Remove from DOM after transition. Tracked on state so a later
      // `unmounted`/`destroyTooltipState` call can cancel it instead of it
      // firing independently against an already-handled element.
      if (state.removeTimer) clearTimeout(state.removeTimer);
      state.removeTimer = setTimeout(() => {
        state.removeTimer = null;
        if (state.tooltipEl?.parentNode) {
          state.tooltipEl.parentNode.removeChild(state.tooltipEl);
        }
        ACTIVE_ELEMENTS.delete(el);
      }, 150);
    }
  }, HIDE_DELAY);
}

function parseBinding(binding: DirectiveBinding): {
  text: string;
  placement: Placement;
} {
  let text = "";
  let placement: Placement = "top";

  if (typeof binding.value === "string") {
    text = binding.value;
  } else if (binding.value && typeof binding.value === "object") {
    text = binding.value.text || "";
    placement = binding.value.placement || "top";
  }

  // Arg overrides object placement
  if (binding.arg) {
    placement = binding.arg as Placement;
  }

  return { text, placement };
}

export const vTooltip: Directive<HTMLElement> = {
  mounted(el, binding) {
    const { text, placement } = parseBinding(binding);

    const onMouseEnter = () => showTooltip(el);
    const onMouseLeave = () => hideTooltip(el);
    const onFocus = () => {
      const state = TOOLTIP_STATES.get(el);
      if (state && Date.now() < state.suppressFocusUntil) return;
      showTooltip(el);
    };
    const onBlur = () => hideTooltip(el);
    const onTouchStart = () => {
      const state = TOOLTIP_STATES.get(el);
      if (!state) return;
      state.suppressFocusUntil = Date.now() + TOUCH_FOCUS_SUPPRESS_MS;
      state.touchTooltipShown = false;
      if (state.touchTimer) clearTimeout(state.touchTimer);
      state.touchTimer = setTimeout(() => {
        state.touchTimer = null;
        state.touchTooltipShown = true;
        showTooltip(el);
      }, LONG_TOUCH_DELAY);
    };
    const onTouchEnd = () => {
      const state = TOOLTIP_STATES.get(el);
      if (!state) return;
      state.suppressFocusUntil = Date.now() + TOUCH_FOCUS_SUPPRESS_MS;
      if (state.touchTimer) {
        clearTimeout(state.touchTimer);
        state.touchTimer = null;
      }
      if (state.touchTooltipShown) {
        hideTooltip(el);
      }
      state.touchTooltipShown = false;
    };
    const onTouchCancel = onTouchEnd;

    const state: TooltipState = {
      tooltipEl: null,
      arrowEl: null,
      showTimer: null,
      hideTimer: null,
      removeTimer: null,
      text,
      placement,
      onMouseEnter,
      onMouseLeave,
      onFocus,
      onBlur,
      onTouchStart,
      onTouchEnd,
      onTouchCancel,
      cleanup: null,
      touchTimer: null,
      touchTooltipShown: false,
      suppressFocusUntil: 0,
    };

    TOOLTIP_STATES.set(el, state);

    el.addEventListener("mouseenter", onMouseEnter);
    el.addEventListener("mouseleave", onMouseLeave);
    el.addEventListener("focus", onFocus);
    el.addEventListener("blur", onBlur);
    el.addEventListener("touchstart", onTouchStart, { passive: true });
    el.addEventListener("touchend", onTouchEnd, { passive: true });
    el.addEventListener("touchcancel", onTouchCancel, { passive: true });
  },

  updated(el, binding) {
    const state = TOOLTIP_STATES.get(el);
    if (!state) return;

    const { text, placement } = parseBinding(binding);
    state.text = text;
    state.placement = placement;

    // If tooltip is currently visible, update position and text
    if (state.tooltipEl?.parentNode) {
      const textNode = state.tooltipEl.firstChild;
      if (textNode && textNode !== state.arrowEl) {
        textNode.textContent = text;
      }
      updatePosition(el, state.tooltipEl, state.arrowEl!, placement);
    }
  },

  unmounted(el) {
    const state = TOOLTIP_STATES.get(el);
    if (!state) return;

    // Remove event listeners
    el.removeEventListener("mouseenter", state.onMouseEnter);
    el.removeEventListener("mouseleave", state.onMouseLeave);
    el.removeEventListener("focus", state.onFocus);
    el.removeEventListener("blur", state.onBlur);
    el.removeEventListener("touchstart", state.onTouchStart);
    el.removeEventListener("touchend", state.onTouchEnd);
    el.removeEventListener("touchcancel", state.onTouchCancel);

    // Clear timers, stop autoUpdate, and remove any live tooltip node.
    destroyTooltipState(el, state);
    TOOLTIP_STATES.delete(el);
  },
};
