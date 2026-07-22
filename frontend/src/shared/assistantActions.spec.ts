import { describe, expect, it, vi } from "vitest";

import { createAssistantActionDispatcher } from "./assistantActions";

function deps() {
  const filters = { filters: {} };
  const visualization = { rowSideColors: [] as string[], colSideColors: [] as string[] };
  return {
    filtersStore: {
      toObject: () => filters,
      replaceState: vi.fn(), setFilter: vi.fn(), removeFilter: vi.fn(), clearFilters: vi.fn(),
    },
    visualizationStore: {
      $state: visualization,
      $patch: (mutator: (state: unknown) => void) => mutator(visualization),
      toObject: () => visualization, replaceState: vi.fn(), setExpressionDisplay: vi.fn(),
    },
    columnsStore: {
      rowColumns: [{ column_name: "tf_family", display_name: "TF Family" }],
      colColumns: [{ column_name: "group", display_name: "Group" }],
      filterableColColumns: [{ column_name: "group", display_name: "Group" }],
      orderableColColumns: [{ column_name: "group", display_name: "Group" }],
    },
    catalogStore: { selectedTableNames: new Set<string>(["CS"]), selectAll: vi.fn() },
    router: { push: vi.fn().mockResolvedValue(undefined), replace: vi.fn().mockResolvedValue(undefined) },
    route: { fullPath: "/h/CS", query: { filters: JSON.stringify({ stale: { value: "old" } }) } },
    idColumn: "gene_id", hiddenColumns: [],
  };
}

describe("GAIA state token dispatcher", () => {
  it("applies complete filters and axis-valid patches", async () => {
    const target = deps();
    const action = { kind: "state_token" as const, status: "pending" as const, spec: {
      view: "heatmap", tables: ["CS"], filters: { filters: { tf_family: { value: "MIKC" } } },
      viz_patches: { rowSideColors: ["TF Family"], colSideColors: ["Group"] },
      trigger_actions: [], url_path: "",
    } };
    expect(await createAssistantActionDispatcher(target as never).dispatch(action)).toBe(true);
    expect(target.filtersStore.replaceState).toHaveBeenCalled();
    expect(target.visualizationStore.$state.rowSideColors).toEqual(["tf_family"]);
    expect(target.visualizationStore.$state.colSideColors).toEqual(["group"]);
    expect(target.router.replace).toHaveBeenCalledWith({
      query: { filters: JSON.stringify({ tf_family: { value: "MIKC" } }) },
    });
  });

  it("expands the wildcard only to eligible axis columns", async () => {
    const target = deps();
    const action = { kind: "state_token" as const, status: "pending" as const, spec: {
      view: "heatmap", tables: ["CS"], filters: { filters: {} },
      viz_patches: { rowSideColors: ["*"], colSideColors: ["*"] }, trigger_actions: [], url_path: "",
    } };
    await createAssistantActionDispatcher(target as never).dispatch(action);
    expect(target.visualizationStore.$state.rowSideColors).toEqual(["tf_family"]);
    expect(target.visualizationStore.$state.colSideColors).toEqual(["group"]);
  });

  it("rejects cross-axis metadata", async () => {
    const target = deps();
    const action = { kind: "state_token" as const, status: "pending" as const, spec: {
      view: "heatmap", tables: ["CS"], filters: { filters: {} },
      viz_patches: { rowSideColors: ["Group"] }, trigger_actions: [], url_path: "",
    } };
    expect(await createAssistantActionDispatcher(target as never).dispatch(action)).toBe(false);
    expect(action.status).toBe("error");
  });

  it("applies compare grouping and expression through canonical leaf controls", async () => {
    const target = deps();
    const action = { kind: "state_token" as const, status: "pending" as const, spec: {
      view: "compare", tables: ["CS"], filters: { filters: {} },
      viz_patches: { "compare.groupingColumn": "Group", "compare.expression": "zscore" },
      trigger_actions: [], url_path: "",
    } };
    expect(await createAssistantActionDispatcher(target as never).dispatch(action)).toBe(true);
    expect((target.visualizationStore.$state as Record<string, unknown>).compare).toEqual({
      groupingColumn: "group", expression: "zscore",
    });
    expect(target.filtersStore.replaceState).not.toHaveBeenCalled();
    expect(target.catalogStore.selectAll).not.toHaveBeenCalled();
    expect(target.router.replace).not.toHaveBeenCalled();
  });

  it("applies a visualization-only token without reloading core view state", async () => {
    const target = deps();
    const action = { kind: "state_token" as const, status: "pending" as const, spec: {
      view: "heatmap", tables: ["CS"], filters: { filters: {} },
      viz_patches: { colorScale: "viridis" }, trigger_actions: [], url_path: "",
    } };

    expect(await createAssistantActionDispatcher(target as never).dispatch(action)).toBe(true);
    expect((target.visualizationStore.$state as Record<string, unknown>).colorScale).toBe("viridis");
    expect(target.filtersStore.replaceState).not.toHaveBeenCalled();
    expect(target.catalogStore.selectAll).not.toHaveBeenCalled();
    expect(target.router.replace).not.toHaveBeenCalled();
  });

  it("dispatches an export-only token against the loaded view without reloading", async () => {
    const target = deps();
    const listener = vi.fn();
    window.addEventListener("genx:assistant-trigger", listener);
    const action = { kind: "state_token" as const, status: "pending" as const, spec: {
      view: "heatmap", tables: ["CS"], filters: { filters: {} },
      viz_patches: {}, trigger_actions: ["export_png"], url_path: "",
    } };

    expect(await createAssistantActionDispatcher(target as never).dispatch(action)).toBe(true);
    expect(listener).toHaveBeenCalledOnce();
    expect(target.filtersStore.replaceState).not.toHaveBeenCalled();
    expect(target.catalogStore.selectAll).not.toHaveBeenCalled();
    expect(target.router.replace).not.toHaveBeenCalled();
    window.removeEventListener("genx:assistant-trigger", listener);
  });
});