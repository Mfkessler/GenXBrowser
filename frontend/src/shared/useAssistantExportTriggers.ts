import { onMounted, onUnmounted } from "vue";

export type VisualizationExportFormat = "png" | "pdf" | "svg";
export type DataExportFormat = "tsv" | "csv" | "xlsx" | "json";

interface AssistantExportHandlers {
  openVisualizationExport: (format: VisualizationExportFormat) => void;
  openDataExport: (format?: DataExportFormat) => void;
}

type ExportAction = "open_export_modal" | `export_${VisualizationExportFormat | DataExportFormat}`;

const activeHandlers = new Set<AssistantExportHandlers>();
let pendingAction: ExportAction | null = null;

function applyAction(action: ExportAction, handlers: AssistantExportHandlers) {
  if (action === "open_export_modal") {
    handlers.openDataExport();
    return;
  }
  const format = action.slice("export_".length);
  if (format === "png" || format === "pdf" || format === "svg") {
    handlers.openVisualizationExport(format);
  } else if (format === "tsv" || format === "csv" || format === "xlsx" || format === "json") {
    handlers.openDataExport(format);
  }
}

function isExportAction(action: unknown): action is ExportAction {
  return action === "open_export_modal" || [
    "export_png", "export_pdf", "export_svg",
    "export_tsv", "export_csv", "export_xlsx", "export_json",
  ].includes(String(action));
}

function handleTrigger(event: Event) {
  const action = (event as CustomEvent<{ action?: string }>).detail?.action;
  if (!isExportAction(action)) return;
  if (activeHandlers.size === 0) {
    pendingAction = action;
    return;
  }
  for (const handlers of activeHandlers) applyAction(action, handlers);
}

if (typeof window !== "undefined") {
  window.addEventListener("genx:assistant-trigger", handleTrigger);
}

export function useAssistantExportTriggers(handlers: AssistantExportHandlers) {
  onMounted(() => {
    activeHandlers.add(handlers);
    if (pendingAction) {
      applyAction(pendingAction, handlers);
      pendingAction = null;
    }
  });
  onUnmounted(() => activeHandlers.delete(handlers));
}