<template>
  <Teleport to="body">
    <div
      v-if="isOpen"
      class="fixed inset-0 z-[110] flex bg-black/85 backdrop-blur-sm outline-none"
      data-html2canvas-ignore="true"
      ref="modalEl"
      tabindex="-1"
    >
      <!-- Preview area (left / centre) -->
      <div class="flex-1 flex items-center justify-center p-6 min-w-0 overflow-hidden">
        <div
          ref="previewWrapperEl"
          class="relative overflow-hidden rounded select-none shadow-2xl"
          :style="{
            width: previewW + 'px',
            height: previewH + 'px',
            cursor: 'crosshair',
          }"
          @mousedown.prevent="onMouseDown"
        >
          <!-- Static screenshot of the viewport -->
          <canvas
            ref="previewCanvasEl"
            class="block pointer-events-none"
            :width="previewW"
            :height="previewH"
          />

          <!-- Crop selection — box-shadow dims the area outside the rect -->
          <div
            v-if="cropRect"
            class="absolute pointer-events-none rounded-sm"
            :style="cropOverlayStyle"
          />
        </div>
      </div>

      <!-- Settings panel (right) -->
      <div
        class="w-72 flex-shrink-0 bg-slate-900 border-l border-white/10 p-5 flex flex-col gap-4 text-white overflow-y-auto"
        data-html2canvas-ignore="true"
      >
        <!-- Header -->
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold tracking-wide">Export Figure</h2>
          <button
            @click="close"
            class="text-slate-400 hover:text-white transition-colors text-2xl leading-none cursor-pointer"
            aria-label="Close export modal"
          >
            &times;
          </button>
        </div>

        <p class="text-xs text-slate-400 leading-relaxed -mt-1">
          Drag on the preview to select a region, or leave empty to export the full viewport.
        </p>

        <!-- Format toggle -->
        <div>
          <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            Format
          </label>
          <div class="grid grid-cols-2 gap-2">
            <button
              v-for="fmt in formats"
              :key="fmt.id"
              @click="selectedFormat = fmt.id"
              class="py-2 px-3 rounded border text-sm font-medium transition-all cursor-pointer"
              :class="
                selectedFormat === fmt.id
                  ? 'bg-blue-600 border-blue-500 text-white'
                  : 'bg-slate-800 border-slate-600 text-slate-300 hover:border-slate-400'
              "
            >
              {{ fmt.label }}
            </button>
          </div>
        </div>

        <!-- Resolution (PNG only) -->
        <Transition name="slide-fade">
          <div v-if="selectedFormat === 'png'" key="scale-panel">
            <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Resolution
            </label>
            <div class="flex flex-col gap-1">
              <label
                v-for="opt in scaleOptions"
                :key="opt.value"
                class="flex items-center gap-3 cursor-pointer rounded px-2 py-1.5 hover:bg-slate-800 transition-colors"
              >
                <input
                  type="radio"
                  :value="opt.value"
                  v-model="selectedScale"
                  class="accent-blue-500 cursor-pointer"
                />
                <span class="text-sm">
                  <span class="font-medium">{{ opt.label }}</span>
                  <span class="text-slate-400 text-xs ml-2">{{ opt.description }}</span>
                </span>
              </label>
            </div>
          </div>
        </Transition>

        <!-- Status / error message -->
        <div
          v-if="statusMessage"
          class="text-xs rounded px-3 py-2 bg-amber-900/40 border border-amber-600/30 text-amber-200"
        >
          {{ statusMessage }}
        </div>

        <div class="flex-1" />

        <!-- Action buttons -->
        <div class="flex flex-col gap-2">
          <button
            @click="doExport"
            :disabled="isExporting"
            class="w-full py-2.5 px-4 rounded text-sm font-semibold transition-colors cursor-pointer"
            :class="
              isExporting
                ? 'bg-blue-900/50 text-blue-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-500 text-white'
            "
          >
            {{ isExporting ? 'Exporting…' : 'Export & Download' }}
          </button>
          <button
            @click="clearCrop"
            class="w-full py-2 px-4 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm transition-colors cursor-pointer"
          >
            Clear Selection
          </button>
          <button
            @click="close"
            class="w-full py-2 px-4 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm transition-colors cursor-pointer"
          >
            Cancel
          </button>
        </div>

        <!-- Keyboard hints -->
        <p class="text-xs text-slate-600 text-center leading-relaxed">
          <kbd class="px-1 py-0.5 bg-slate-800 border border-slate-700 rounded text-xs font-mono"
            >Ctrl+Shift+P</kbd
          >
          to toggle &nbsp;·&nbsp;
          <kbd class="px-1 py-0.5 bg-slate-800 border border-slate-700 rounded text-xs font-mono"
            >Esc</kbd
          >
          to close
        </p>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import html2canvasPro from 'html2canvas-pro'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

// ── State ────────────────────────────────────────────────────────────────────
const isOpen = ref(false)
const isCapturing = ref(false)
const isExporting = ref(false)
const statusMessage = ref('')

/** 1× capture of the viewport, used only to paint the preview */
const capturedCanvas = ref<HTMLCanvasElement | null>(null)
const captureViewportW = ref(0)
const captureViewportH = ref(0)
/** window.scrollY at the moment of capture — used to align the export re-render */
const captureScrollY = ref(0)

/** Preview canvas dimensions inside the modal */
const previewW = ref(0)
const previewH = ref(0)
/** How many viewport-space px correspond to one preview-canvas px */
const previewScale = ref(1)

// DOM refs
const modalEl = ref<HTMLDivElement | null>(null)
const previewWrapperEl = ref<HTMLDivElement | null>(null)
const previewCanvasEl = ref<HTMLCanvasElement | null>(null)

// Crop drag state (preview-space pixels)
const isDragging = ref(false)
const dragStart = ref<{ x: number; y: number } | null>(null)
const dragEnd = ref<{ x: number; y: number } | null>(null)

// Format & scale selection
const selectedFormat = ref<'png' | 'svg'>('png')
const selectedScale = ref(4)

const formats = [
  { id: 'png' as const, label: 'PNG (Raster)' },
  { id: 'svg' as const, label: 'SVG (Vector)' },
]

const scaleOptions = [
  { value: 1, label: 'Scale 1×', description: 'Web standard' },
  { value: 3, label: 'Scale 3×', description: '~300 DPI' },
  { value: 4, label: 'Scale 4×', description: '~400 DPI' },
  { value: 6, label: 'Scale 6×', description: '~600 DPI' },
]

// ── Crop rect (preview-space) ─────────────────────────────────────────────────
const cropRect = computed(() => {
  if (!dragStart.value || !dragEnd.value) return null
  const x = Math.min(dragStart.value.x, dragEnd.value.x)
  const y = Math.min(dragStart.value.y, dragEnd.value.y)
  const w = Math.abs(dragEnd.value.x - dragStart.value.x)
  const h = Math.abs(dragEnd.value.y - dragStart.value.y)
  if (w < 4 || h < 4) return null
  return { x, y, w, h }
})

const cropOverlayStyle = computed(() => {
  if (!cropRect.value) return {}
  return {
    left: `${cropRect.value.x}px`,
    top: `${cropRect.value.y}px`,
    width: `${cropRect.value.w}px`,
    height: `${cropRect.value.h}px`,
    border: '2px solid rgba(96, 165, 250, 0.9)',
    backgroundColor: 'rgba(96, 165, 250, 0.06)',
    // Large box-shadow dims everything outside the selection rect
    boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.45)',
  }
})

// ── DOM style snapshot / restore ─────────────────────────────────────────────
/**
 * Snapshots every inline `style` attribute in the body (plus <html>/<body>
 * themselves and <head> <style> nodes) before a html2canvas-pro call, and
 * returns a cleanup function that fully restores the DOM to that state.
 *
 * Why this is necessary: html2canvas-pro v1.5 directly mutates inline style
 * attributes on live DOM elements (adds margin/padding/vertical-align for
 * measurement, line-height for font metrics, etc.) and does NOT clean them
 * up afterwards. These mutations persist and break CSS rendering (e.g. text
 * appears at the top of input fields instead of centred).
 */
function snapshotStyles(): () => void {
  // Snapshot <html> and <body> inline style attributes
  const htmlAttr = document.documentElement.getAttribute('style') ?? ''
  const bodyAttr = document.body.getAttribute('style') ?? ''

  // Snapshot every element in <body> that currently has an inline style
  const elementStyles = new Map<Element, string>()
  document.body.querySelectorAll('[style]').forEach((el) => {
    elementStyles.set(el, el.getAttribute('style') ?? '')
  })

  // Snapshot <style> elements in <head>
  const headStyles = new Set(Array.from(document.head.querySelectorAll('style')))

  return () => {
    // Restore <html> and <body>
    if (htmlAttr) document.documentElement.setAttribute('style', htmlAttr)
    else document.documentElement.removeAttribute('style')

    if (bodyAttr) document.body.setAttribute('style', bodyAttr)
    else document.body.removeAttribute('style')

    // Restore / remove inline styles on all body elements that were changed
    document.body.querySelectorAll('[style]').forEach((el) => {
      const original = elementStyles.get(el)
      if (original === undefined) {
        // html2canvas added a style that wasn't there before — strip it
        el.removeAttribute('style')
      } else if (el.getAttribute('style') !== original) {
        // html2canvas modified an existing inline style — restore it
        el.setAttribute('style', original)
      }
    })
    // Also restore elements whose style attribute was outright removed
    elementStyles.forEach((style, el) => {
      if (style && !el.getAttribute('style')) {
        el.setAttribute('style', style)
      }
    })

    // Remove any <style> elements html2canvas-pro injected into <head>
    document.head.querySelectorAll('style').forEach((el) => {
      if (!headStyles.has(el)) el.remove()
    })

    // Remove orphaned html2canvas-container iframes
    document.querySelectorAll('iframe.html2canvas-container').forEach((el) => el.remove())

    // Force a synchronous reflow so the browser re-paints with the restored styles
    void document.body.offsetHeight
  }
}

// ── html2canvas rendering fixes ───────────────────────────────────────────────
const TEXT_INPUT_TYPES = new Set([
  '', 'text', 'search', 'email', 'url', 'tel', 'password', 'number',
])

/**
 * Passed as the `onclone` callback to html2canvas-pro.
 *
 * Problem: html2canvas-pro's built-in <input>/<textarea> text renderer has a
 * vertical-centering bug — it positions the text baseline at
 * `contentBoxTop + contentBoxHeight/2 + 1`, which is too close to the top for
 * most fonts, so glyph ascenders get clipped by the element's own top edge.
 * This is intrinsic to the library's rendering formula: adjusting the cloned
 * element's padding/line-height has NO effect on it (verified — html2canvas
 * reads the correct computed style but its internal formula ignores it), so
 * the only reliable fix is to bypass that renderer entirely.
 *
 * Fix: for every live <input>/<textarea>, clear the CLONE's value/placeholder
 * so html2canvas's special-cased renderer sees empty text and skips drawing
 * it, then overlay a plain absolutely-positioned <div> with the same text,
 * using ordinary flexbox centering (`display:flex; align-items:center`) —
 * html2canvas's regular text-layout path (used for all normal DOM text) is
 * reliable and renders this correctly.
 */
function fixInputRendering(cloneDoc: Document): void {
  const liveInputs = Array.from(
    document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input, textarea'),
  )
  const cloneInputs = Array.from(
    cloneDoc.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input, textarea'),
  )

  liveInputs.forEach((liveEl, i) => {
    const cloneEl = cloneInputs[i]
    if (!cloneEl) return

    if (liveEl.tagName === 'INPUT' && !TEXT_INPUT_TYPES.has((liveEl as HTMLInputElement).type)) {
      return // checkbox/radio/etc. render fine natively — leave them alone
    }

    const isPlaceholderText = !liveEl.value
    const text = liveEl.value || liveEl.placeholder
    if (!text) return

    const cs = window.getComputedStyle(liveEl)
    const rect = liveEl.getBoundingClientRect()

    // Suppress html2canvas-pro's own (buggy) input text rendering
    cloneEl.value = ''
    cloneEl.removeAttribute('placeholder')

    const textColor = isPlaceholderText
      ? window.getComputedStyle(liveEl, '::placeholder').color
      : cs.color
    const justify =
      cs.textAlign === 'center' ? 'center' : cs.textAlign === 'right' ? 'flex-end' : 'flex-start'

    const overlay = cloneDoc.createElement('div')
    overlay.textContent = text
    Object.assign(overlay.style, {
      position: 'fixed',
      left: `${rect.left}px`,
      top: `${rect.top}px`,
      width: `${rect.width}px`,
      height: `${rect.height}px`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: justify,
      paddingLeft: cs.paddingLeft,
      paddingRight: cs.paddingRight,
      fontFamily: cs.fontFamily,
      fontSize: cs.fontSize,
      fontWeight: cs.fontWeight,
      letterSpacing: cs.letterSpacing,
      color: textColor,
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      pointerEvents: 'none',
      boxSizing: 'border-box',
      zIndex: '2147483647',
    })
    cloneDoc.body.appendChild(overlay)
  })
}

// ── Mouse / crop handlers ─────────────────────────────────────────────────────
function getPreviewPos(e: MouseEvent): { x: number; y: number } {
  const rect = previewWrapperEl.value!.getBoundingClientRect()
  return {
    x: Math.max(0, Math.min(e.clientX - rect.left, previewW.value)),
    y: Math.max(0, Math.min(e.clientY - rect.top, previewH.value)),
  }
}

function onMouseDown(e: MouseEvent) {
  isDragging.value = true
  dragStart.value = getPreviewPos(e)
  dragEnd.value = null
  document.addEventListener('mousemove', onGlobalMouseMove)
  document.addEventListener('mouseup', onGlobalMouseUp)
}

function onGlobalMouseMove(e: MouseEvent) {
  if (!isDragging.value) return
  dragEnd.value = getPreviewPos(e)
}

function onGlobalMouseUp() {
  if (!isDragging.value) return
  isDragging.value = false
  document.removeEventListener('mousemove', onGlobalMouseMove)
  document.removeEventListener('mouseup', onGlobalMouseUp)
  // Treat a bare click (no meaningful drag) as a reset
  if (!cropRect.value) {
    dragStart.value = null
    dragEnd.value = null
  }
}

function clearCrop() {
  dragStart.value = null
  dragEnd.value = null
}

// ── Capture & open ─────────────────────────────────────────────────────────────
async function captureAndOpen() {
  if (isOpen.value || isCapturing.value) return
  isCapturing.value = true
  statusMessage.value = ''

  const restoreStyles = snapshotStyles()
  try {
    const vw = window.innerWidth
    const vh = window.innerHeight
    const scrollY = window.scrollY
    captureScrollY.value = scrollY

    const canvas = await html2canvasPro(document.body, {
      scale: 1,
      useCORS: true,
      backgroundColor: '#ffffff',
      scrollX: 0,
      scrollY: -scrollY,
      width: vw,
      height: vh,
      onclone: fixInputRendering,
      ignoreElements: (el: Element) =>
        (el as HTMLElement).hasAttribute('data-html2canvas-ignore'),
    })

    capturedCanvas.value = canvas
    captureViewportW.value = vw
    captureViewportH.value = vh

    // Compute preview size: fill available space (viewport minus right panel + margins)
    const maxW = Math.max(200, vw - 288 - 96)
    const maxH = Math.max(200, vh - 48)
    const ratio = Math.min(maxW / vw, maxH / vh, 1)
    previewW.value = Math.round(vw * ratio)
    previewH.value = Math.round(vh * ratio)
    previewScale.value = 1 / ratio // viewport px per preview px

    isOpen.value = true
    await nextTick()

    // Paint the screenshot into the preview canvas
    const ctx = previewCanvasEl.value?.getContext('2d')
    if (ctx && canvas) {
      ctx.drawImage(canvas, 0, 0, previewW.value, previewH.value)
    }

    await nextTick()
    modalEl.value?.focus()
  } catch (err) {
    console.error('[ScreenshotModal] Capture failed:', err)
    statusMessage.value = 'Capture failed. See browser console for details.'
  } finally {
    restoreStyles()
    isCapturing.value = false
  }
}

function close() {
  if (isDragging.value) {
    document.removeEventListener('mousemove', onGlobalMouseMove)
    document.removeEventListener('mouseup', onGlobalMouseUp)
    isDragging.value = false
  }
  isOpen.value = false
  clearCrop()
  capturedCanvas.value = null
  statusMessage.value = ''
}

// ── Export helpers ────────────────────────────────────────────────────────────
/** Returns the viewport-space crop bounding box, or the full viewport if no selection. */
function getViewportCrop(): { x: number; y: number; w: number; h: number } {
  if (cropRect.value) {
    const s = previewScale.value
    return {
      x: Math.round(cropRect.value.x * s),
      y: Math.round(cropRect.value.y * s),
      w: Math.round(cropRect.value.w * s),
      h: Math.round(cropRect.value.h * s),
    }
  }
  return { x: 0, y: 0, w: captureViewportW.value, h: captureViewportH.value }
}

async function doExport() {
  if (isExporting.value) return
  isExporting.value = true
  statusMessage.value = ''
  try {
    if (selectedFormat.value === 'svg') {
      await exportSvg()
    } else {
      await exportPng()
    }
  } catch (err) {
    console.error('[ScreenshotModal] Export failed:', err)
    statusMessage.value = 'Export failed. See browser console for details.'
  } finally {
    isExporting.value = false
  }
}

async function exportPng() {
  const { x, y, w, h } = getViewportCrop()
  const scale = selectedScale.value

  // Snapshot body/html styles BEFORE hiding the modal so we can restore them
  // after html2canvas — it leaves side-effects (style mutations, iframes, etc.)
  const restoreStyles = snapshotStyles()

  // Hide this modal so it cannot interfere with the export re-render
  const modalNode = modalEl.value
  if (modalNode) modalNode.style.visibility = 'hidden'
  await nextTick()

  try {
    // Use html2canvas's own x/y/width/height crop so coordinates stay
    // in the same coordinate space as the preview capture (no manual drawImage crop needed)
    const exportCanvas = await html2canvasPro(document.body, {
      scale,
      useCORS: true,
      backgroundColor: '#ffffff',
      scrollX: 0,
      scrollY: -captureScrollY.value,
      x,
      y,
      width: w,
      height: h,
      onclone: fixInputRendering,
      ignoreElements: (el: Element) =>
        (el as HTMLElement).hasAttribute('data-html2canvas-ignore'),
    })

    await new Promise<void>((resolve) => {
      exportCanvas.toBlob(
        (blob) => {
          if (blob) {
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `figure_${scale}x.png`
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
            setTimeout(() => URL.revokeObjectURL(url), 10_000)
          }
          resolve()
        },
        'image/png',
      )
    })
  } finally {
    // Restore styles (resets html2canvas side-effects + forces reflow),
    // then restore modal visibility — close() removes it entirely right after.
    restoreStyles()
    if (modalNode) modalNode.style.visibility = ''
  }

  close()
}

async function exportSvg() {
  const { x, y, w, h } = getViewportCrop()

  // Find all non-ignored SVG elements in the live DOM
  const allSvgs = Array.from(document.querySelectorAll('svg')).filter(
    (svg) => !svg.closest('[data-html2canvas-ignore]'),
  ) as SVGSVGElement[]

  // Pick the SVG with the greatest intersection area with the crop region (viewport coords)
  let bestSvg: SVGSVGElement | null = null
  let bestArea = 0

  for (const svg of allSvgs) {
    const r = svg.getBoundingClientRect()
    const iw = Math.min(r.right, x + w) - Math.max(r.left, x)
    const ih = Math.min(r.bottom, y + h) - Math.max(r.top, y)
    if (iw > 0 && ih > 0 && iw * ih > bestArea) {
      bestArea = iw * ih
      bestSvg = svg
    }
  }

  if (!bestSvg) {
    statusMessage.value = 'No SVG element found in the selected region. Try PNG export instead.'
    return
  }

  const clone = bestSvg.cloneNode(true) as SVGSVGElement
  inlineCriticalStyles(bestSvg, clone)

  // Map crop region from viewport coordinates to SVG internal coordinates via CTM
  const ctm = bestSvg.getScreenCTM()
  if (ctm) {
    const inv = ctm.inverse()
    const mapPt = (px: number, py: number) => {
      const pt = (bestSvg as SVGSVGElement).createSVGPoint()
      pt.x = px
      pt.y = py
      return pt.matrixTransform(inv)
    }
    const tl = mapPt(x, y)
    const br = mapPt(x + w, y + h)
    const vbX = Math.min(tl.x, br.x)
    const vbY = Math.min(tl.y, br.y)
    const vbW = Math.abs(br.x - tl.x)
    const vbH = Math.abs(br.y - tl.y)
    clone.setAttribute('viewBox', `${vbX} ${vbY} ${vbW} ${vbH}`)
    clone.setAttribute('width', String(Math.round(vbW)))
    clone.setAttribute('height', String(Math.round(vbH)))
  }

  const svgStr = new XMLSerializer().serializeToString(clone)
  const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'figure.svg'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 10_000)

  close()
}

/**
 * Copy critical computed font/fill/stroke styles from source SVG text nodes
 * into the cloned SVG so the file renders correctly without external CSS.
 */
function inlineCriticalStyles(source: SVGSVGElement, clone: SVGSVGElement) {
  const cssProps = ['font-family', 'font-size', 'font-weight', 'fill', 'stroke', 'stroke-width']
  const srcEls = source.querySelectorAll<Element>('text, tspan')
  const cloneEls = clone.querySelectorAll<SVGElement>('text, tspan')
  srcEls.forEach((srcEl, i) => {
    const cloneEl = cloneEls[i]
    if (!cloneEl) return
    const cs = window.getComputedStyle(srcEl)
    cssProps.forEach((prop) => {
      const val = cs.getPropertyValue(prop)
      if (val) cloneEl.style.setProperty(prop, val)
    })
  })
}

// ── Global keyboard shortcut ──────────────────────────────────────────────────
function onKeyDown(e: KeyboardEvent) {
  if (e.ctrlKey && e.shiftKey && e.key === 'P') {
    e.preventDefault()
    if (isOpen.value) close()
    else captureAndOpen()
    return
  }
  if (e.key === 'Escape' && isOpen.value) {
    e.preventDefault()
    close()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  document.removeEventListener('mousemove', onGlobalMouseMove)
  document.removeEventListener('mouseup', onGlobalMouseUp)
})

defineExpose({ captureAndOpen })
</script>

<style scoped>
.slide-fade-enter-active,
.slide-fade-leave-active {
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
