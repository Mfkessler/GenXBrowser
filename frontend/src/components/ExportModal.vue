<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[60] flex items-center justify-center p-6">
      <!-- Background overlay -->
      <div class="absolute inset-0 bg-black opacity-50" @click="$emit('close')"></div>

      <!-- Modal content -->
      <div class="relative bg-white rounded-lg border border-gray-300 w-full max-w-md p-6 z-10 overflow-hidden">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <h3 class="text-lg font-bold text-gray-700">Export Data</h3>
        <button
          @click="$emit('close')"
          class="cursor-pointer text-gray-500 hover:text-red-600 text-xl font-bold"
          aria-label="Close"
        >
          &times;
        </button>
      </div>

      <!-- Export Info -->
      <div class="mb-6 p-3 bg-gray-50 rounded-md text-sm text-gray-600">
        <p><strong>{{ rowCount.toLocaleString() }}</strong> {{ rowLabel }}</p>
        <p><strong>{{ columnCount.toLocaleString() }}</strong> columns ({{ metaColumnCount }} metadata + {{ sampleColumnCount }} {{ dataColumnLabel }})</p>
        <p v-if="hasFilters" class="text-primary-600 mt-1">
          <svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          Filters applied
        </p>
      </div>

      <!-- Format Selection -->
      <div class="mb-6">
        <label class="block text-sm font-semibold text-gray-700 mb-3">Export Format</label>
        <div class="grid grid-cols-2 gap-3">
          <button
            v-for="format in exportFormats"
            :key="format.id"
            @click="selectedFormat = format.id"
            :class="[
              'cursor-pointer p-3 rounded-md border-2 text-left transition-all',
              selectedFormat === format.id
                ? 'border-primary-500 bg-primary-50'
                : 'border-gray-200 hover:border-gray-300'
            ]"
          >
            <div class="flex items-center gap-2">
              <span class="text-lg">{{ format.icon }}</span>
              <div>
                <p class="font-semibold text-gray-800">{{ format.label }}</p>
                <p class="text-xs text-gray-500">{{ format.description }}</p>
              </div>
            </div>
          </button>
        </div>
      </div>

      <!-- Options -->
      <div class="mb-6 space-y-3">
        <label class="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            v-model="includeHeaders"
            class="rounded text-primary-600"
          />
          <span class="text-sm text-gray-700">Include column headers</span>
        </label>
      </div>

      <!-- Action Buttons -->
      <div class="flex gap-3">
        <button
          @click="$emit('close')"
          class="cursor-pointer flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-100"
        >
          Cancel
        </button>
        <button
          @click="doExport"
          :disabled="exporting"
          class="cursor-pointer flex-1 px-4 py-2 bg-accent1-500 text-white rounded-md hover:bg-accent1-700 disabled:opacity-50 flex items-center justify-center gap-2"
        >
          Export
        </button>
      </div>

      <div
        v-if="exporting"
        class="absolute inset-0 z-20 flex items-center justify-center bg-white/90 backdrop-blur-[1px]"
        role="status"
        aria-live="polite"
      >
        <div class="w-[min(22rem,calc(100%-2rem))] rounded-md border border-gray-200 bg-white px-5 py-4 text-center shadow-lg">
          <div class="flex flex-col items-center gap-3">
            <svg class="h-9 w-9 animate-spin text-primary-500" viewBox="0 0 48 48" aria-hidden="true">
              <circle class="text-gray-200" cx="24" cy="24" r="18" fill="none" stroke="currentColor" stroke-width="4" />
              <circle cx="24" cy="24" r="18" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-dasharray="76 38" />
            </svg>
            <div class="w-full space-y-2">
              <div class="text-sm font-semibold text-gray-800">Preparing export...</div>
              <div class="h-2 w-full overflow-hidden rounded-full bg-gray-100">
                <div
                  class="h-full rounded-full bg-primary-500 transition-[width] duration-150"
                  :style="{ width: `${exportProgress}%` }"
                ></div>
              </div>
              <div class="text-xs font-medium text-gray-500">{{ exportProgress }}%</div>
            </div>
            <button
              type="button"
              class="cursor-pointer rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50"
              @click="cancelExport"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { nextTick, ref } from "vue";
import { getEntityLabelPlural } from "@/shared/dataTypeLabels";
import type { RowType } from "@/shared/RowType";

const props = defineProps<{
  data: RowType[];
  columns: string[];
  columnDisplayNames?: Record<string, string>;
  metaColumns: string[];
  sampleColumns: string[];
  filename: string;
  hasFilters: boolean;
  totalCount?: number;
  dataColumnLabel?: string;
  rowLabel?: string;
}>();

const emit = defineEmits(["close", "export"]);

const entityLabelPlural = getEntityLabelPlural();

// Computed info - use totalCount if provided, otherwise data length
const rowCount = props.totalCount ?? props.data.length;
const columnCount = props.columns.length;
const metaColumnCount = props.metaColumns.length;
const sampleColumnCount = props.sampleColumns.length;
const dataColumnLabel = props.dataColumnLabel ?? 'samples';
const rowLabel = props.rowLabel ?? entityLabelPlural.toLowerCase();

// Format options
const exportFormats = [
  { id: 'tsv', label: 'TSV', icon: '📄', description: 'Tab-separated values' },
  { id: 'csv', label: 'CSV', icon: '📊', description: 'Comma-separated values' },
  { id: 'xlsx', label: 'Excel', icon: '📗', description: 'Excel workbook (.xlsx)' },
  { id: 'json', label: 'JSON', icon: '{ }', description: 'JavaScript Object Notation' },
];

const selectedFormat = ref('tsv');
const includeHeaders = ref(true);
const exporting = ref(false);
const exportProgress = ref(0);
let cancelRequested = false;

function escapeValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  
  if (Array.isArray(value)) {
    return value.join(', ');
  }
  
  return String(value);
}

function getExportColumnName(column: string): string {
  return props.columnDisplayNames?.[column] || column;
}

function assertNotCanceled() {
  if (cancelRequested) {
    throw new DOMException('Export canceled', 'AbortError');
  }
}

function updateProgress(percent: number) {
  exportProgress.value = Math.max(0, Math.min(100, Math.round(percent)));
}

async function yieldToUi() {
  await new Promise<void>((resolve) => window.setTimeout(resolve, 0));
}

async function toDelimited(data: RowType[], columns: string[], delimiter: string, headers: boolean): Promise<string> {
  const lines: string[] = [];
  
  if (headers) {
    // Use display names if available, otherwise use column names
    const headerNames = columns.map(getExportColumnName);
    lines.push(headerNames.join(delimiter));
  }
  
  const totalRows = Math.max(data.length, 1);
  for (let rowIndex = 0; rowIndex < data.length; rowIndex++) {
    const row = data[rowIndex];
    const values = columns.map(col => {
      const val = escapeValue(row[col]);
      // For CSV/TSV, escape the delimiter if present
      if (val.includes(delimiter) && !val.startsWith('"')) {
        return `"${val.replace(/"/g, '""')}"`;
      }
      return val;
    });
    lines.push(values.join(delimiter));
    if (rowIndex % 250 === 0) {
      assertNotCanceled();
      updateProgress((rowIndex + 1) / totalRows * 95);
      await yieldToUi();
    }
  }
  
  return lines.join('\n');
}

async function toJson(data: RowType[], columns: string[]): Promise<string> {
  const filtered: Record<string, unknown>[] = [];
  const totalRows = Math.max(data.length, 1);
  for (let rowIndex = 0; rowIndex < data.length; rowIndex++) {
    const row = data[rowIndex];
    const obj: Record<string, unknown> = {};
    for (const col of columns) {
      obj[getExportColumnName(col)] = row[col];
    }
    filtered.push(obj);
    if (rowIndex % 250 === 0) {
      assertNotCanceled();
      updateProgress((rowIndex + 1) / totalRows * 80);
      await yieldToUi();
    }
  }
  assertNotCanceled();
  updateProgress(90);
  await yieldToUi();
  return JSON.stringify(filtered, null, 2);
}

// Convert column index (0-based) to Excel column name (A, B, ..., Z, AA, AB, ...)
function getExcelColumnName(index: number): string {
  let name = '';
  let i = index;
  while (i >= 0) {
    name = String.fromCharCode((i % 26) + 65) + name;
    i = Math.floor(i / 26) - 1;
  }
  return name;
}

async function toXlsx(data: RowType[], columns: string[], headers: boolean): Promise<Blob> {
  // Simple XLSX generation using XML (no external library needed)
  // This creates a basic Excel file that can be opened by Excel, LibreOffice, etc.
  
  const escapeXml = (str: string) => str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
  
  let sheetData = '';
  let rowNum = 1;
  
  if (headers) {
    sheetData += `<row r="${rowNum}">`;
    columns.forEach((col, i) => {
      const cellRef = getExcelColumnName(i) + rowNum;
      sheetData += `<c r="${cellRef}" t="inlineStr"><is><t>${escapeXml(getExportColumnName(col))}</t></is></c>`;
    });
    sheetData += '</row>';
    rowNum++;
  }
  
  const totalRows = Math.max(data.length, 1);
  for (let dataIndex = 0; dataIndex < data.length; dataIndex++) {
    const row = data[dataIndex];
    sheetData += `<row r="${rowNum}">`;
    columns.forEach((col, i) => {
      const cellRef = getExcelColumnName(i) + rowNum;
      const val = row[col];
      
      if (val === null || val === undefined) {
        sheetData += `<c r="${cellRef}"/>`;
      } else if (typeof val === 'number' && !isNaN(val)) {
        sheetData += `<c r="${cellRef}"><v>${val}</v></c>`;
      } else {
        const strVal = Array.isArray(val) ? val.join(', ') : String(val);
        sheetData += `<c r="${cellRef}" t="inlineStr"><is><t>${escapeXml(strVal)}</t></is></c>`;
      }
    });
    sheetData += '</row>';
    rowNum++;
    if (dataIndex % 250 === 0) {
      assertNotCanceled();
      updateProgress((dataIndex + 1) / totalRows * 75);
      await yieldToUi();
    }
  }

  // Calculate the dimension reference (e.g., "A1:ZZ1000")
  const lastCol = getExcelColumnName(columns.length - 1);
  const dimension = `A1:${lastCol}${rowNum - 1}`;
  
  const worksheet = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<dimension ref="${dimension}"/>
<sheetData>${sheetData}</sheetData>
</worksheet>`;
  
  const contentTypes = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>`;
  
  const workbook = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets>
</workbook>`;
  
  const workbookRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>`;
  
  const rels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`;
  
  // Use JSZip if available, otherwise create a simple zip manually
  // For simplicity, we'll use a basic approach
  const { default: JSZip } = await import('jszip');
  const zip = new JSZip();
  
  zip.file('[Content_Types].xml', contentTypes);
  zip.file('_rels/.rels', rels);
  zip.file('xl/workbook.xml', workbook);
  zip.file('xl/_rels/workbook.xml.rels', workbookRels);
  zip.file('xl/worksheets/sheet1.xml', worksheet);
  
  assertNotCanceled();
  return await zip.generateAsync(
    { type: 'blob', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
    (metadata) => updateProgress(75 + metadata.percent * 0.2),
  );
}

function cancelExport() {
  cancelRequested = true;
}

async function doExport() {
  exporting.value = true;
  cancelRequested = false;
  updateProgress(0);
  await nextTick();
  
  try {
    let blob: Blob;
    let extension: string;
    
    switch (selectedFormat.value) {
      case 'csv':
        const csvContent = await toDelimited(props.data, props.columns, ',', includeHeaders.value);
        blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' });
        extension = 'csv';
        break;
        
      case 'tsv':
        const tsvContent = await toDelimited(props.data, props.columns, '\t', includeHeaders.value);
        blob = new Blob([tsvContent], { type: 'text/tab-separated-values;charset=utf-8' });
        extension = 'tsv';
        break;
        
      case 'json':
        const jsonContent = await toJson(props.data, props.columns);
        blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8' });
        extension = 'json';
        break;
        
      case 'xlsx':
        blob = await toXlsx(props.data, props.columns, includeHeaders.value);
        extension = 'xlsx';
        break;
        
      default:
        throw new Error(`Unknown format: ${selectedFormat.value}`);
    }
    assertNotCanceled();
    updateProgress(100);
    
    // Download
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${props.filename}.${extension}`;
    document.body.appendChild(a);
    a.click();
    
    setTimeout(() => {
      URL.revokeObjectURL(url);
      a.remove();
    }, 0);
    
    emit('close');
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      return;
    }
    console.error('Export failed:', e);
    alert('Export failed. Please try again.');
  } finally {
    exporting.value = false;
  }
}
</script>
