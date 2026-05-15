<template>
  <div
    v-if="show"
    class="fixed inset-0 flex justify-center items-center z-50"
    style="background-color: rgba(0, 0, 0, 0.5)"
  >
    <div
      class="bg-white p-4 sm:p-6 rounded-lg shadow-lg w-[94vw] sm:w-[32rem] max-w-[96vw] max-h-[90vh] flex flex-col"
    >
      <!-- Title & Close Button -->
      <div class="flex justify-between items-center mb-4">
        <h1 class="text-xl font-bold cursor-default">Share Visualization</h1>
        <button
          @click="closeOverlay"
          class="text-gray-700 rounded-full p-2 hover:bg-gray-100"
          aria-label="Close overlay"
        >
          <svg
            class="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            ></path>
          </svg>
        </button>
      </div>

      <!-- Shareable Link Section -->
      <div v-if="showLink" class="mb-6">
        <label
          for="shareLink"
          class="block mb-2 text-sm font-semibold text-gray-700"
        >Shareable Link</label
        >
        <div class="flex items-center space-x-2">
          <input
            id="shareLink"
            type="text"
            readonly
            :value="isGeneratingLink ? 'Generating link...' : shareUrl"
            :disabled="isGeneratingLink"
            class="flex-grow p-2 border rounded-md text-sm cursor-pointer select-all"
            :class="{ 'bg-gray-100 text-gray-500': isGeneratingLink }"
            @click="copyToClipboard"
          />
          <button
            @click="copyToClipboard"
            :disabled="isGeneratingLink"
            class="p-2 border-1 border-accent2-900 bg-accent2-100 hover:bg-accent2-900 text-accent2-900 hover:text-accent2-100 rounded-md disabled:opacity-50"
            :aria-label="copied ? 'Copied' : 'Copy link'"
          >
            <span v-if="copied">Copied ✓</span>
            <span v-else>Copy</span>
          </button>
        </div>
        <p class="text-xs text-gray-500 mt-1">
          Click input or button to copy the link
        </p>
      </div>

      <!-- Download Buttons -->
      <div>
        <label class="block mb-2 text-sm font-semibold text-gray-700"
        >Download Visualization</label
        >
        <div class="flex flex-col space-y-2">
          <button
            @click="downloadPNG"
            class="w-full p-2 border rounded-md hover:bg-primary-100"
          >
            Download PNG
          </button>
          <button
            @click="downloadPDF"
            class="w-full p-2 border rounded-md hover:bg-primary-100"
          >
            Download PDF
          </button>
          <button
            @click="downloadSVG"
            class="w-full p-2 border rounded-md hover:bg-primary-100"
          >
            Download SVG
          </button>
        </div>
      </div>

      <!-- Close Button (Bottom) -->
      <button
        @click="closeOverlay"
        class="mt-2 border border-accent1-900 bg-accent1-100 text-accent1-900 hover:text-accent1-100 hover:bg-accent1-900 py-2 rounded-md w-full"
      >
        Close
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import axios from "axios";
import {
  onMounted,
  ref,
  type Ref,
} from "vue";

import {API_BASE_URL} from "@/shared/Config";
import {useFiltersStore} from "@/stores/filters";
import {useVisualizationStore} from "@/stores/visualization";
import html2canvasPro from "html2canvas-pro";

// Props
const props = defineProps<{
  show: boolean;
  baseUrl?: string;
  htmlContainer?: Ref<HTMLElement | null>;
  showLink: boolean;
}>();

// Emits
const emit = defineEmits(["close"]);

const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();

// Generate a descriptive filename based on current route/view and store data
function generateFilename(extension: string): string {
  const path = window.location.pathname;
  const pathParts = path.split('/').filter(Boolean);
  
  let baseName = 'visualization';
  
  // Extract view type from path (routes use short prefixes: /c/, /h/, /p/, /o/)
  if (path.includes('/c/')) {
    // Compare view - use store data for accurate filename
    baseName = 'compare';
    const compareState = visualizationStore.compare;
    
    if (compareState.selectedOrthogroup) {
      baseName += `_${compareState.selectedOrthogroup.toUpperCase()}`;
    }
    if (compareState.expression) {
      baseName += `_${compareState.expression}`;
    }
    if (compareState.plotType) {
      baseName += `_${compareState.plotType}`;
    }
    // Add species info
    if (compareState.selectedSpecies && compareState.selectedSpecies.length > 0) {
      if (compareState.selectedSpecies.length <= 3) {
        baseName += `_${compareState.selectedSpecies.join('-')}`;
      } else {
        baseName += `_${compareState.selectedSpecies.length}species`;
      }
    }
  } else if (path.includes('/h/')) {
    // Heatmap view
    baseName = 'heatmap';
    // Extract table name from path (second part after /h/)
    const hIndex = pathParts.indexOf('h') + 1;
    if (hIndex > 0 && hIndex < pathParts.length) {
      baseName += `_${pathParts[hIndex]}`;
    }
    // Add expression type from visualization store
    const expressionId = visualizationStore.expressionDisplay?.optionId;
    if (expressionId) {
      baseName += `_${expressionId}`;
    }
    // Add color scale
    if (visualizationStore.colorScale) {
      baseName += `_${visualizationStore.colorScale.toLowerCase()}`;
    }
  } else if (path.includes('/p/')) {
    // Phylogenetic tree view
    baseName = 'phylotree';
    // Extract table name from path
    const pIndex = pathParts.indexOf('p') + 1;
    if (pIndex > 0 && pIndex < pathParts.length) {
      baseName += `_${pathParts[pIndex]}`;
    }
    // Get orthogroup from visualization store (PhyloTree uses store, not filters)
    const ogValue = visualizationStore.phyloTree.selectedOrthogroup;
    if (ogValue) {
      baseName += `_${ogValue.toUpperCase()}`;
    }
  } else if (path.includes('/o/')) {
    // ORA view
    baseName = 'ora';
    // Extract table name from path
    const oIndex = pathParts.indexOf('o') + 1;
    if (oIndex > 0 && oIndex < pathParts.length) {
      baseName += `_${pathParts[oIndex]}`;
    }
    // Add significance threshold
    baseName += `_q${visualizationStore.significance}`;
  }
  
  // Add timestamp for uniqueness
  const timestamp = new Date().toISOString().slice(0, 10);
  return `${baseName}_${timestamp}.${extension}`;
}


const copied = ref(false);
const shareUrl = ref("");
const isGeneratingLink = ref(false);

function copyToClipboard() {
  if (!shareUrl.value) return;
  navigator.clipboard.writeText(shareUrl.value).then(() => {
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  });
}

function closeOverlay() {
  emit("close");
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    URL.revokeObjectURL(url);
    a.remove();
  }, 500);
}

async function generateHashLink(): Promise<string> {
  // Get the current state from stores
  const filtersData = filtersStore.toObject();
  const visualizationsData = visualizationStore.toObject();

  try {
    // Store the state and get a hash ID
    const response = await axios.post(`${API_BASE_URL}/api/id`, {
      filters: filtersData,
      visualizations: visualizationsData,
    });

    const hashId = response.data.id;
    
    // Build the short URL with just the hash ID
    const baseUrl = window.location.origin + window.location.pathname;
    return `${baseUrl}?id=${hashId}`;
  } catch (error) {
    console.error("Failed to generate share link:", error);
    // Fallback to current URL if hash generation fails
    return window.location.href;
  }
}

onMounted(async () => {
  if (typeof window !== 'undefined') {
    isGeneratingLink.value = true;
    try {
      shareUrl.value = await generateHashLink();
    } finally {
      isGeneratingLink.value = false;
    }
  }
});

// ---- Visualization Download Functions ----

/**
 * Check if the container is a PhyloTree (has zoom-container or is the phylotreeContainer)
 */
function isPhyloTreeContainer(container: HTMLElement | null): boolean {
  if (!container) return false;
  const svg = container.querySelector('svg');
  return svg?.querySelector('g.zoom-container') !== null ||
         container.id === 'phylotreeContainer' ||
         container.closest('#phylotreeContainer') !== null;
}

/**
 * Render SVG to canvas at specified scale (for PNG/PDF export).
 * This properly handles the full SVG content including transformed elements.
 */
async function renderSvgToCanvas(svgString: string, scale: number = 2): Promise<HTMLCanvasElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const svgBlob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);
    
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;
      
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.fillStyle = 'white';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.scale(scale, scale);
        ctx.drawImage(img, 0, 0);
      }
      
      URL.revokeObjectURL(url);
      resolve(canvas);
    };
    
    img.onerror = (e) => {
      URL.revokeObjectURL(url);
      reject(e);
    };
    
    img.src = url;
  });
}

async function downloadPNG() {
  try {
    // Generate a filename based on current page
    const filename = generateFilename('png');

    const container = props.htmlContainer?.value;
    if (!container) {
      alert("Visualization container not found.");
      return;
    }

    // Check if this is a PhyloTree - use SVG-based rendering for full content
    if (isPhyloTreeContainer(container)) {
      const svg = container.querySelector('svg');
      if (!svg) {
        alert("Visualization SVG not found.");
        return;
      }
      
      // Use specialized PhyloTree export
      const exportedSvg = exportPhyloTreeSvg(svg);
      const serializer = new XMLSerializer();
      const svgString = serializer.serializeToString(exportedSvg);
      
      const canvas = await renderSvgToCanvas(svgString, 2);
      
      canvas.toBlob((blob) => {
        if (!blob) return;
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 500);
      }, "image/png");
      return;
    }

    // Check if this is a Plotly container - use Plotly's native export
    const plotlyElement = container.classList.contains('js-plotly-plot') ? container :
                          container.querySelector('.js-plotly-plot') as HTMLElement | null;
    if (plotlyElement) {
      const Plotly = await import('plotly.js-dist-min');
      try {
        const pngData = await Plotly.toImage(plotlyElement, {
          format: 'png',
          width: plotlyElement.offsetWidth * 2 || 2400,
          height: plotlyElement.offsetHeight * 2 || 1600,
          scale: 2,
        });
        
        // Download the PNG
        const a = document.createElement("a");
        a.href = pngData;
        a.download = filename;
        a.click();
        return;
      } catch (plotlyError) {
        console.warn("Plotly PNG export failed, falling back:", plotlyError);
      }
    }

    // --- Standard PNG download using html2canvas ---
    const snapshot = await html2canvasPro(container, {
      scale: 2,
      useCORS: true,
      scrollX: 0,
      scrollY: -window.scrollY,
    });
    
    snapshot.toBlob((blob) => {
      if (!blob) return;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 500);
    }, "image/png");
    
  } catch (e) {
    alert("Failed to download PNG.");
    console.error(e);
  }
}

async function downloadPDF() {
  try {
    // Generate a filename based on current page
    const filename = generateFilename('pdf');

    const jsPDF = (await import("jspdf")).jsPDF;
    const container = props.htmlContainer?.value;
    if (!container) {
      alert("Visualization container not found.");
      return;
    }

    // Check if this is a PhyloTree - use SVG-based rendering for full content
    if (isPhyloTreeContainer(container)) {
      const svg = container.querySelector('svg');
      if (!svg) {
        alert("Visualization SVG not found.");
        return;
      }
      
      // Use specialized PhyloTree export
      const exportedSvg = exportPhyloTreeSvg(svg);
      const serializer = new XMLSerializer();
      const svgString = serializer.serializeToString(exportedSvg);
      if (!svgString) {
        alert("Visualization SVG not found.");
        return;
      }
      
      const canvas = await renderSvgToCanvas(svgString, 2);
      
      // Create PDF with appropriate size
      const imgWidth = canvas.width / 2; // Account for scale
      const imgHeight = canvas.height / 2;
      
      // Determine page orientation and size
      const isLandscape = imgWidth > imgHeight;
      const pdf = new jsPDF({
        unit: "pt",
        format: [imgWidth + 40, imgHeight + 40], // Custom size with margins
        orientation: isLandscape ? 'landscape' : 'portrait'
      });
      
      const imgData = canvas.toDataURL("image/png");
      pdf.addImage(imgData, "PNG", 20, 20, imgWidth, imgHeight);
      downloadBlob(pdf.output("blob"), filename);
      return;
    }

    // Check if this is a Plotly container - use Plotly's native export
    const plotlyElement = container.classList.contains('js-plotly-plot') ? container :
                          container.querySelector('.js-plotly-plot') as HTMLElement | null;
    if (plotlyElement) {
      const Plotly = await import('plotly.js-dist-min');
      try {
        const pngData = await Plotly.toImage(plotlyElement, {
          format: 'png',
          width: plotlyElement.offsetWidth * 2 || 2400,
          height: plotlyElement.offsetHeight * 2 || 1600,
          scale: 2,
        });
        
        // Load the image and convert to PDF
        const img = new Image();
        await new Promise<void>((resolve, reject) => {
          img.onload = () => resolve();
          img.onerror = reject;
          img.src = pngData;
        });
        
        const imgWidth = img.width / 2;
        const imgHeight = img.height / 2;
        const isLandscape = imgWidth > imgHeight;
        const pdf = new jsPDF({
          unit: "pt",
          format: [imgWidth + 40, imgHeight + 40],
          orientation: isLandscape ? 'landscape' : 'portrait'
        });
        
        pdf.addImage(pngData, "PNG", 20, 20, imgWidth, imgHeight);
        downloadBlob(pdf.output("blob"), filename);
        return;
      } catch (plotlyError) {
        console.warn("Plotly PDF export failed, falling back:", plotlyError);
      }
    }

    // --- Standard PDF download using html2canvas ---
    const snapshot = await html2canvasPro(container, {
      scale: 2,
      useCORS: true,
      scrollX: 0,
      scrollY: -window.scrollY,
    });

    // Create jsPDF with appropriate dimensions
    const imgWidth = snapshot.width / 2;
    const imgHeight = snapshot.height / 2;
    const isLandscape = imgWidth > imgHeight;
    const pdf = new jsPDF({
      unit: "pt",
      format: isLandscape ? [imgHeight + 40, imgWidth + 40] : [imgWidth + 40, imgHeight + 40],
      orientation: isLandscape ? 'landscape' : 'portrait'
    });

    const imgData = snapshot.toDataURL("image/png");
    pdf.addImage(imgData, "PNG", 20, 20, imgWidth, imgHeight);
    downloadBlob(pdf.output("blob"), filename);
    
  } catch (e) {
    alert("Failed to download PDF. Make sure jsPDF is installed.");
    console.error(e);
  }
}

/**
 * Clone an SVG element while preserving visual styles.
 * This is critical for export - we need to inline styles but NOT override
 * explicit SVG attributes with computed values that may be wrong.
 */
function inlineComputedStylesToClone(svg: SVGSVGElement): SVGSVGElement {
  const clone = svg.cloneNode(true) as SVGSVGElement;

  const originalNodes = svg.querySelectorAll<SVGElement>("*");
  const clonedNodes   = clone.querySelectorAll<SVGElement>("*");

  originalNodes.forEach((orig, i) => {
    const cloned = clonedNodes[i];
    if (!cloned) return;
    
    const tagName = orig.tagName.toLowerCase();
    
    // Skip defs, clipPath, and other non-visual elements
    if (['defs', 'clippath', 'lineargradient', 'radialgradient', 'pattern', 'mask', 'symbol', 'use'].includes(tagName)) {
      return;
    }
    
    // For each style-relevant attribute, prefer explicit attributes over computed styles
    const styleProps: Record<string, string> = {};
    
    // Text elements
    if (tagName === 'text' || tagName === 'tspan') {
      // Copy text styling from explicit attributes or computed
      ['fill', 'font-family', 'font-size', 'font-weight', 'font-style', 'text-anchor', 'dominant-baseline'].forEach(prop => {
        const attrVal = orig.getAttribute(prop);
        if (attrVal && attrVal !== 'inherit') {
          styleProps[prop] = attrVal;
        } else {
          const computed = window.getComputedStyle(orig).getPropertyValue(prop);
          // Only use computed if it's a valid color/value (not black default)
          if (computed && computed !== 'rgb(0, 0, 0)' && computed !== 'none' && computed !== 'normal') {
            styleProps[prop] = computed;
          } else if (attrVal) {
            styleProps[prop] = attrVal;
          }
        }
      });
      // Default text fill to black if not set (text should be visible)
      if (!styleProps['fill'] && !orig.getAttribute('fill')) {
        const computed = window.getComputedStyle(orig).getPropertyValue('fill');
        if (computed && computed !== 'none') {
          styleProps['fill'] = computed;
        }
      }
    }
    // Shape elements (path, line, rect, circle, etc.)
    else if (['path', 'line', 'polyline', 'polygon', 'rect', 'circle', 'ellipse'].includes(tagName)) {
      // CRITICAL: Preserve explicit fill and stroke attributes
      ['fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray', 'opacity', 'fill-opacity', 'stroke-opacity'].forEach(prop => {
        const attrVal = orig.getAttribute(prop);
        if (attrVal !== null) {
          // Explicit attribute - always use it
          styleProps[prop] = attrVal;
        } else {
          // No explicit attribute - check inline style
          const inlineStyle = orig.style.getPropertyValue(prop);
          if (inlineStyle) {
            styleProps[prop] = inlineStyle;
          }
          // For stroke/fill, check computed but be careful with defaults
          else if (prop === 'stroke' || prop === 'fill') {
            const computed = window.getComputedStyle(orig).getPropertyValue(prop);
            // Only use computed color if it looks like an actual color (not browser default black)
            if (computed && computed !== 'rgb(0, 0, 0)' && computed !== 'none') {
              styleProps[prop] = computed;
            }
          }
        }
      });
    }
    // Groups - minimal styling
    else if (tagName === 'g') {
      const opacity = orig.getAttribute('opacity');
      if (opacity) styleProps['opacity'] = opacity;
      // Preserve transform
      const transform = orig.getAttribute('transform');
      if (transform) cloned.setAttribute('transform', transform);
    }

    // Apply collected styles
    if (Object.keys(styleProps).length > 0) {
      const styleString = Object.entries(styleProps)
        .map(([k, v]) => `${k}:${v}`)
        .join(';');
      cloned.setAttribute('style', styleString);
    }
  });

  return clone;
}


/**
 * Apply PhyloTree CSS styles directly to SVG elements BEFORE cloning.
 * This is necessary because CSS classes are not preserved when exporting SVG.
 * Must be called on the ORIGINAL SVG (still in DOM) to access computed styles.
 * Applies styles directly as attributes so they survive cloning.
 */
function applyPhyloTreeStylesInPlace(svg: SVGSVGElement): void {
  // Branch paths - CRITICAL: must have fill:none to prevent black triangles
  // From phylotree.css: .branch { fill: none; stroke: #999; stroke-width: 2px; }
  svg.querySelectorAll('.branch').forEach((el) => {
    const path = el as SVGElement;
    // ALWAYS set fill to none for branches - this is the key fix for black artifacts
    path.setAttribute('fill', 'none');
    
    // Get current stroke color (may be set by species coloring)
    const currentStroke = path.getAttribute('stroke') || 
                          path.style.stroke || 
                          (svg.ownerDocument?.defaultView ? 
                            svg.ownerDocument.defaultView.getComputedStyle(path).stroke : null);
    const strokeColor = (currentStroke && currentStroke !== 'none' && currentStroke !== '' && currentStroke !== 'rgb(0, 0, 0)') 
                        ? currentStroke : '#999';
    
    if (!path.getAttribute('stroke') || path.getAttribute('stroke') === 'none') {
      path.setAttribute('stroke', strokeColor);
    }
    if (!path.getAttribute('stroke-width')) {
      path.setAttribute('stroke-width', '2');
    }
  });
  
  // ALSO apply to ALL path elements that don't have explicit fill set
  // This catches any paths that might not have the .branch class
  svg.querySelectorAll('path').forEach((el) => {
    const path = el as SVGElement;
    // If no fill attribute is set, default to 'none' for tree branches
    if (!path.hasAttribute('fill')) {
      // Check if this looks like a tree branch (has stroke but no fill)
      const hasStroke = path.hasAttribute('stroke') || path.style.stroke;
      if (hasStroke) {
        path.setAttribute('fill', 'none');
      }
    }
  });
  
  // Node circles - From phylotree.css: .node circle { fill: steelblue; stroke: black; }
  svg.querySelectorAll('.node circle, .node ellipse, .node rect').forEach((el) => {
    const shape = el as SVGElement;
    // Preserve existing fill color (species coloring may have set it)
    if (!shape.hasAttribute('fill')) {
      shape.setAttribute('fill', 'steelblue');
    }
    if (!shape.hasAttribute('stroke')) {
      shape.setAttribute('stroke', 'black');
      shape.setAttribute('stroke-width', '0.5');
    }
  });
  
  // Internal node circles - .internal-node { fill: #CCC; }
  svg.querySelectorAll('.internal-node circle, .internal-node ellipse, .internal-node rect').forEach((el) => {
    const shape = el as SVGElement;
    if (!shape.hasAttribute('fill')) {
      shape.setAttribute('fill', '#CCC');
    }
    if (!shape.hasAttribute('stroke')) {
      shape.setAttribute('stroke', 'black');
      shape.setAttribute('stroke-width', '0.5');
    }
  });
  
  // Collapsed node markers (triangles/shapes) - these SHOULD be black per CSS
  // .node-collapsed circle/ellipse/rect { fill: black !important; }
  svg.querySelectorAll('.node-collapsed circle, .node-collapsed ellipse, .node-collapsed rect, .node-collapsed path').forEach((el) => {
    const shape = el as SVGElement;
    // Only collapsed nodes should be filled black
    shape.setAttribute('fill', 'black');
  });
  
  // Collapsed indicator styling
  svg.querySelectorAll('.node-collapsed-indicator').forEach((el) => {
    const shape = el as SVGElement;
    shape.setAttribute('fill', '#dc2626');
    shape.setAttribute('stroke', '#991b1b');
    shape.setAttribute('stroke-width', '2');
  });
  
  // Node text labels
  svg.querySelectorAll('.node text, g.node text').forEach((el) => {
    const text = el as SVGElement;
    // Preserve existing fill (species coloring)
    const currentFill = text.getAttribute('fill') || text.style.fill;
    if (!currentFill || currentFill === 'none') {
      // Get computed style from DOM
      const computed = svg.ownerDocument?.defaultView?.getComputedStyle(text).fill;
      if (computed && computed !== 'none') {
        text.setAttribute('fill', computed);
      }
    }
    // Ensure font is set
    if (!text.hasAttribute('font-family')) {
      text.setAttribute('font-family', 'sans-serif');
    }
    if (!text.hasAttribute('font-size')) {
      text.setAttribute('font-size', '10px');
    }
  });
  
  // Heatmap cells - preserve their fill colors (they're set by the colorscale)
  svg.querySelectorAll('.heatmap-cell').forEach((el) => {
    const rect = el as SVGElement;
    // These should already have fill set - just ensure it's preserved
    const fill = rect.getAttribute('fill');
    if (!fill) {
      rect.setAttribute('fill', '#ccc');
    }
  });
  
  // Clade highlighting - .clade { fill: lightgrey; stroke: #222; opacity: 0.5; }
  svg.querySelectorAll('.clade').forEach((el) => {
    const shape = el as SVGElement;
    if (!shape.hasAttribute('fill')) {
      shape.setAttribute('fill', 'lightgrey');
    }
    if (!shape.hasAttribute('stroke')) {
      shape.setAttribute('stroke', '#222');
      shape.setAttribute('stroke-width', '2');
    }
    shape.setAttribute('opacity', '0.5');
  });
  
  // Scale bar - .tree-scale-bar line/path { fill: none; stroke: #000; }
  svg.querySelectorAll('.tree-scale-bar line, .tree-scale-bar path').forEach((el) => {
    const shape = el as SVGElement;
    shape.setAttribute('fill', 'none');
    shape.setAttribute('stroke', '#000');
  });
  
  // Ensure all text elements have a fill color for readability
  svg.querySelectorAll('text').forEach((el) => {
    const text = el as SVGElement;
    if (!text.hasAttribute('fill') && !text.style.fill) {
      // Get computed style if available
      const computed = svg.ownerDocument?.defaultView?.getComputedStyle(text).fill;
      if (computed && computed !== 'none' && computed !== 'rgb(255, 255, 255)') {
        text.setAttribute('fill', computed);
      } else {
        // Default to black for readability
        text.setAttribute('fill', '#000');
      }
    }
  });
}


/**
 * Export PhyloTree SVG with full content visible (no clipping).
 * Creates a clean export by:
 * 1. FIRST applying styles to original (while still in DOM for getComputedStyle)
 * 2. Cloning the SVG (with styles now as attributes)
 * 3. Removing zoom transforms from clone
 * 4. Calculating true content bounds
 * 5. Setting viewBox to show everything
 */
function exportPhyloTreeSvg(svg: SVGSVGElement): SVGSVGElement {
  // CRITICAL: Apply styles to the ORIGINAL SVG FIRST while it's still in the DOM
  // This allows getComputedStyle to work and captures all species colors, etc.
  applyPhyloTreeStylesInPlace(svg);
  
  // NOW clone - the inline attributes will be copied
  const clone = svg.cloneNode(true) as SVGSVGElement;
  
  // Remove the zoom container transform to show content at 1:1 scale
  const zoomContainer = clone.querySelector('g.zoom-container');
  if (zoomContainer) {
    zoomContainer.removeAttribute('transform');
  }
  
  // We need to measure bounds from the original SVG with transform temporarily removed
  const originalZoomContainer = svg.querySelector('g.zoom-container');
  const originalTransform = originalZoomContainer?.getAttribute('transform') || null;
  
  // Temporarily remove transform to measure true bounds
  if (originalZoomContainer) {
    originalZoomContainer.removeAttribute('transform');
  }
  
  // Calculate bounds - MUST include the heatmap which is in a translated group
  let bounds = { x: 0, y: 0, width: 1000, height: 800 };
  
  try {
    // Get the ENTIRE content group including heatmap
    // Structure: svg > g.zoom-container > g (main content with tree + heatmap)
    const mainGroup = originalZoomContainer?.querySelector(':scope > g') as SVGGraphicsElement | null;
    if (mainGroup) {
      const bbox = mainGroup.getBBox();
      bounds = {
        x: bbox.x,
        y: bbox.y,
        width: bbox.width,
        height: bbox.height
      };
      
      // Also check for legend/colorbar which might be outside main group
      const allGroups = svg.querySelectorAll('g.zoom-container g');
      allGroups.forEach((g) => {
        try {
          if (g instanceof SVGGraphicsElement) {
            const gBBox = g.getBBox();
            // Get cumulative transform offset
            let offsetX = 0, offsetY = 0;
            const transform = g.getAttribute('transform');
            if (transform) {
              const match = /translate\(([^,)]+),?\s*([^)]*)\)/.exec(transform);
              if (match) {
                offsetX = parseFloat(match[1]) || 0;
                offsetY = parseFloat(match[2]) || 0;
              }
            }
            const right = gBBox.x + gBBox.width + offsetX;
            const bottom = gBBox.y + gBBox.height + offsetY;
            if (right > bounds.x + bounds.width) {
              bounds.width = right - bounds.x;
            }
            if (bottom > bounds.y + bounds.height) {
              bounds.height = bottom - bounds.y;
            }
          }
        } catch {
          // getBBox can fail on empty groups
        }
      });
    }
  } catch {
    console.warn('getBBox failed, using fallback bounds');
  }
  
  // Restore original transform
  if (originalZoomContainer && originalTransform) {
    originalZoomContainer.setAttribute('transform', originalTransform);
  }
  
  // Add generous padding
  const padding = 50;
  bounds.x -= padding;
  bounds.y -= padding;
  bounds.width += padding * 2;
  bounds.height += padding * 2;
  
  // Ensure minimum dimensions
  bounds.width = Math.max(bounds.width, 400);
  bounds.height = Math.max(bounds.height, 300);
  
  // Set viewBox and dimensions on clone
  clone.setAttribute('viewBox', `${bounds.x} ${bounds.y} ${bounds.width} ${bounds.height}`);
  clone.setAttribute('width', String(bounds.width));
  clone.setAttribute('height', String(bounds.height));
  
  // Add white background as first child
  const SVG_NS = "http://www.w3.org/2000/svg";
  const bg = document.createElementNS(SVG_NS, "rect");
  bg.setAttribute("x", String(bounds.x));
  bg.setAttribute("y", String(bounds.y));
  bg.setAttribute("width", String(bounds.width));
  bg.setAttribute("height", String(bounds.height));
  bg.setAttribute("fill", "white");
  clone.insertBefore(bg, clone.firstChild);
  
  return clone;
}

function mergeAllSvgsInContainer(container: HTMLElement): string {
  // Check if this is a Plotly container (has .js-plotly-plot class or .plot-container)
  const plotlyElement = container.classList.contains('js-plotly-plot') ? container :
                        container.querySelector('.js-plotly-plot') as HTMLElement | null;
  
  // For Plotly, use Plotly's native toImage/Svg export to get complete SVG with axis labels
  if (plotlyElement) {
    // Plotly structures: .plot-container > .svg-container > multiple SVGs
    // We need to capture ALL SVGs in the svg-container and merge them properly
    const svgContainer = plotlyElement.querySelector('.svg-container');
    if (svgContainer) {
      const allSvgs = Array.from(svgContainer.querySelectorAll<SVGSVGElement>(':scope > svg'));
      if (allSvgs.length > 0) {
        // Merge all Plotly SVGs (main-svg contains plot, others contain axis titles etc.)
        const SVG_NS = "http://www.w3.org/2000/svg";
        const merged = document.createElementNS(SVG_NS, "svg");
        
        // Use dimensions from the first (main) SVG
        const mainSvg = allSvgs[0];
        const width = parseFloat(mainSvg.getAttribute("width") || "0") || mainSvg.viewBox.baseVal.width || 800;
        const height = parseFloat(mainSvg.getAttribute("height") || "0") || mainSvg.viewBox.baseVal.height || 600;
        
        merged.setAttribute("xmlns", SVG_NS);
        merged.setAttribute("width", String(width));
        merged.setAttribute("height", String(height));
        merged.setAttribute("viewBox", `0 0 ${width} ${height}`);
        
        // Add white background
        const bg = document.createElementNS(SVG_NS, "rect");
        bg.setAttribute("width", String(width));
        bg.setAttribute("height", String(height));
        bg.setAttribute("fill", "white");
        merged.appendChild(bg);
        
        // Merge all SVGs' contents
        allSvgs.forEach((svg) => {
          const inlinedClone = inlineComputedStylesToClone(svg);
          const g = document.createElementNS(SVG_NS, "g");
          
          while (inlinedClone.childNodes.length > 0) {
            g.appendChild(inlinedClone.firstChild as ChildNode);
          }
          
          merged.appendChild(g);
        });
        
        const serializer = new XMLSerializer();
        return serializer.serializeToString(merged);
      }
    }
    
    // Fallback: get the first SVG
    const mainSvg = plotlyElement.querySelector<SVGSVGElement>('svg');
    if (mainSvg) {
      const inlinedClone = inlineComputedStylesToClone(mainSvg);
      inlinedClone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      const serializer = new XMLSerializer();
      return serializer.serializeToString(inlinedClone);
    }
    return "";
  }
  
  // Non-Plotly containers
  let svgs = Array.from(container.querySelectorAll<SVGSVGElement>(":scope > svg, svg"));
  // Deduplicate in case of nested selectors
  svgs = [...new Set(svgs)];
  
  if (svgs.length === 0) {
    return "";
  }

  // If there's only one SVG (common case for PhyloTree, Heatmap), 
  // export it with full content
  if (svgs.length === 1) {
    const svg = svgs[0];
    
    // Check if it's a phylotree (has zoom-container or phylotree-related elements)
    const isPhyloTree = svg.querySelector('g.zoom-container') !== null ||
                        container.id === 'phylotreeContainer' ||
                        container.closest('#phylotreeContainer') !== null;
    
    if (isPhyloTree) {
      // Use specialized PhyloTree export that handles zoom transforms correctly
      const exportedSvg = exportPhyloTreeSvg(svg);
      // Don't inline styles for PhyloTree - the SVG already has correct inline styles
      exportedSvg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      const serializer = new XMLSerializer();
      return serializer.serializeToString(exportedSvg);
    }
    
    // For other single SVGs, use standard export
    const inlinedClone = inlineComputedStylesToClone(svg);
    
    // Get proper dimensions
    let width = 800, height = 600;
    try {
      const bbox = svg.getBBox();
      width = bbox.width || svg.viewBox.baseVal.width || parseFloat(svg.getAttribute("width") || "0") || 800;
      height = bbox.height || svg.viewBox.baseVal.height || parseFloat(svg.getAttribute("height") || "0") || 600;
    } catch {
      width = parseFloat(svg.getAttribute("width") || "0") || 800;
      height = parseFloat(svg.getAttribute("height") || "0") || 600;
    }
    
    inlinedClone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    inlinedClone.setAttribute("width", String(width));
    inlinedClone.setAttribute("height", String(height));
    
    const serializer = new XMLSerializer();
    return serializer.serializeToString(inlinedClone);
  }

  // Multiple SVGs: merge them (legacy behavior for views with multiple plots)
  const SVG_NS = "http://www.w3.org/2000/svg";
  const merged = document.createElementNS(SVG_NS, "svg");

  let currentY = 0;
  let maxWidth = 0;

  svgs.forEach((svg) => {
    // gestylten Clone erzeugen
    const inlinedClone = inlineComputedStylesToClone(svg);

    // Größe des Originals (weil das sicher im DOM ist)
    const bbox = svg.getBBox();  // nutzt das tatsächliche Layout
    const width = bbox.width || svg.viewBox.baseVal.width || parseFloat(svg.getAttribute("width") || "0");
    const height = bbox.height || svg.viewBox.baseVal.height || parseFloat(svg.getAttribute("height") || "0");

    maxWidth = Math.max(maxWidth, width);

    // Gruppe mit translate, damit das SVG nach unten geschoben wird
    const g = document.createElementNS(SVG_NS, "g");
    g.setAttribute("transform", `translate(0, ${currentY})`);

    // Kinder des geklonten SVG in die Gruppe schieben
    while (inlinedClone.childNodes.length > 0) {
      g.appendChild(inlinedClone.firstChild as ChildNode);
    }

    merged.appendChild(g);

    currentY += height; // nächstes SVG darunter
  });

  merged.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  merged.setAttribute("width", String(maxWidth));
  merged.setAttribute("height", String(currentY));

  const serializer = new XMLSerializer();
  return serializer.serializeToString(merged);
}




async function downloadSVG() {
  try {
    // Generate filename
    const filename = generateFilename('svg');
    
    const container = props.htmlContainer?.value;
    if (!container) {
      alert("Visualization SVG not found.");
      return;
    }

    // Check if this is a PhyloTree - use specialized export for full content
    if (isPhyloTreeContainer(container)) {
      const svg = container.querySelector('svg');
      if (!svg) {
        alert("Visualization SVG not found.");
        return;
      }
      
      // Use specialized PhyloTree export which applies CSS as inline styles
      const exportedSvg = exportPhyloTreeSvg(svg);
      const serializer = new XMLSerializer();
      const svgString = serializer.serializeToString(exportedSvg);
      
      const svgBlob = new Blob([svgString], {
        type: "image/svg+xml;charset=utf-8"
      });
      const svgUrl = URL.createObjectURL(svgBlob);

      const svgLink = document.createElement("a");
      svgLink.href = svgUrl;
      svgLink.download = filename;
      document.body.appendChild(svgLink);
      svgLink.click();
      svgLink.remove();

      setTimeout(() => URL.revokeObjectURL(svgUrl), 500);
      return;
    }

    // Check if this is a Plotly container - use Plotly's native SVG export
    const plotlyElement = container.classList.contains('js-plotly-plot') ? container :
                          container.querySelector('.js-plotly-plot') as HTMLElement | null;
    
    if (plotlyElement) {
      // Use Plotly's native toImage function for SVG export
      const Plotly = await import('plotly.js-dist-min');
      try {
        const svgData = await Plotly.toImage(plotlyElement, {
          format: 'svg',
          width: plotlyElement.offsetWidth || 1200,
          height: plotlyElement.offsetHeight || 800,
        });
        
        // svgData is a data URL, convert to blob
        const response = await fetch(svgData);
        const blob = await response.blob();
        
        const svgUrl = URL.createObjectURL(blob);
        const svgLink = document.createElement("a");
        svgLink.href = svgUrl;
        svgLink.download = filename;
        document.body.appendChild(svgLink);
        svgLink.click();
        svgLink.remove();
        
        setTimeout(() => URL.revokeObjectURL(svgUrl), 500);
        return;
      } catch (plotlyError) {
        console.warn("Plotly SVG export failed, falling back to manual export:", plotlyError);
        // Fall through to manual export
      }
    }

    // Non-Plotly/PhyloTree or fallback: use manual SVG export
    const svgString = mergeAllSvgsInContainer(container);

    if (!svgString) {
      alert("No SVG content found to export.");
      return;
    }

    const svgBlob = new Blob([svgString], {
      type: "image/svg+xml;charset=utf-8"
    });
    const svgUrl = URL.createObjectURL(svgBlob);

    const svgLink = document.createElement("a");
    svgLink.href = svgUrl;
    svgLink.download = filename;
    document.body.appendChild(svgLink);
    svgLink.click();
    svgLink.remove();

    setTimeout(() => URL.revokeObjectURL(svgUrl), 500);

  } catch (e) {
    alert("Failed to download SVG.");
    console.error(e);
  }
}
</script>
