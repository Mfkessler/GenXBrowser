import {
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
  text: string;
  placement: Placement;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onFocus: () => void;
  onBlur: () => void;
  cleanup: (() => void) | null;
}

const TOOLTIP_STATES = new WeakMap<HTMLElement, TooltipState>();
const SHOW_DELAY = 150;
const HIDE_DELAY = 50;

// Shared CSS classes
const TOOLTIP_CLASSES = [
  "fixed",
  "z-[99999]",
  "pointer-events-none",
  "opacity-0",
  "transition-opacity",
  "duration-150",
].join(" ");

function createTooltipEl(): { tooltipEl: HTMLElement; arrowEl: HTMLElement } {
  const tooltipEl = document.createElement("div");
  tooltipEl.setAttribute("role", "tooltip");
  tooltipEl.className = TOOLTIP_CLASSES;
  tooltipEl.style.cssText =
    "background:#2563eb;color:#fff;font-size:0.75rem;line-height:1rem;border-radius:0.375rem;padding:0.5rem 0.75rem;max-width:20rem;box-shadow:0 10px 15px -3px rgb(0 0 0/.1),0 4px 6px -4px rgb(0 0 0/.1);white-space:normal;word-wrap:break-word;top:0;left:0;width:max-content;";

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
  computePosition(triggerEl, tooltipEl, {
    placement,
    middleware: [
      offset(8),
      flip(),
      shift({ padding: 8 }),
      arrowMiddleware({ element: arrowEl }),
    ],
  }).then(({ x, y, placement: finalPlacement, middlewareData }) => {
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
    if (!state.text) return;

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

    // Position the tooltip
    updatePosition(el, state.tooltipEl, state.arrowEl!, state.placement);

    // Show with animation
    requestAnimationFrame(() => {
      if (state.tooltipEl) {
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
    if (state.tooltipEl) {
      state.tooltipEl.style.opacity = "0";
      // Remove from DOM after transition
      setTimeout(() => {
        if (state.tooltipEl?.parentNode) {
          state.tooltipEl.parentNode.removeChild(state.tooltipEl);
        }
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
    const onFocus = () => showTooltip(el);
    const onBlur = () => hideTooltip(el);

    const state: TooltipState = {
      tooltipEl: null,
      arrowEl: null,
      showTimer: null,
      hideTimer: null,
      text,
      placement,
      onMouseEnter,
      onMouseLeave,
      onFocus,
      onBlur,
      cleanup: null,
    };

    TOOLTIP_STATES.set(el, state);

    el.addEventListener("mouseenter", onMouseEnter);
    el.addEventListener("mouseleave", onMouseLeave);
    el.addEventListener("focus", onFocus);
    el.addEventListener("blur", onBlur);
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

    // Clear timers
    if (state.showTimer) clearTimeout(state.showTimer);
    if (state.hideTimer) clearTimeout(state.hideTimer);

    // Remove event listeners
    el.removeEventListener("mouseenter", state.onMouseEnter);
    el.removeEventListener("mouseleave", state.onMouseLeave);
    el.removeEventListener("focus", state.onFocus);
    el.removeEventListener("blur", state.onBlur);

    // Remove tooltip element
    if (state.tooltipEl?.parentNode) {
      state.tooltipEl.parentNode.removeChild(state.tooltipEl);
    }

    // Cleanup
    if (state.cleanup) state.cleanup();
    TOOLTIP_STATES.delete(el);
  },
};
