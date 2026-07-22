import { beforeEach, describe, expect, it, vi } from "vitest";

import { createAssistantActionDispatcher, type DispatcherDeps } from "./assistantActions";
import { useAssistantStore, type ChatMessage, type ClientContext } from "@/stores/assistant";
import type { AssistantAction } from "@/stores/assistant";
import { createPinia, setActivePinia } from "pinia";

vi.mock("axios", () => ({
  default: {
    post: vi.fn(async (_url: string, payload: Record<string, unknown>) => ({
      data: { id: "abc123def4567890", url_path: "/h/CS?id=abc123def4567890", view: payload.view || "heatmap" },
    })),
    isAxiosError: () => false,
  },
}));

beforeEach(() => {
  setActivePinia(createPinia());
});

type TestDeps = DispatcherDeps & {
  __test: {
    filterChainColumns: string[][];
    filterChainOperators: Array<[string, string, "and" | "or"]>;
  };
};

function makeDeps(): TestDeps {
  const state: Record<string, unknown> = {
    expressionDisplay: { optionId: "getmm", layer: "getmm", transform: "raw" },
    rowSideColors: [],
    colSideColors: [],
    rowOrder: { name: "", order: "asc" },
    colOrder: { name: "", order: "asc" },
    customColOrder: {
      enabled: false,
      mode: "metadata",
      metadataColumn: "default_trait",
      metadataValues: [],
      sampleNames: [],
    },
  };

  const appliedFilters: Record<string, unknown> = {};
  const filterChainColumns: string[][] = [];
  const filterChainOperators: Array<[string, string, "and" | "or"]> = [];

  return {
    filtersStore: {
      setFilter: (key, filter) => { appliedFilters[key] = filter; },
      removeFilter: () => undefined,
      clearFilters: () => undefined,
      setFilterChainColumns: (columns) => { filterChainColumns.push([...columns]); },
      setPairOperator: (left, right, operator) => { filterChainOperators.push([left, right, operator]); },
      toObject: () => ({ filters: appliedFilters }),
    },
    visualizationStore: {
      $state: state,
      $patch: (mutator) => mutator(state),
      toObject: () => ({ ...state }),
      setExpressionDisplay: (optionId, layer, transform) => {
        state.expressionDisplay = { optionId, layer, transform };
      },
    },
    columnsStore: {
      rowColumns: [
        { column_name: "ortho_id", display_name: "Orthogroup", type: "array", array_separator: "," },
        { column_name: "tf_family", display_name: "TF Family", type: "text" },
        { column_name: "length", display_name: "Length", type: "bigint" },
        { column_name: "is_tf", display_name: "Is TF", type: "boolean" },
      ],
      colColumns: [
        { column_name: "default_trait", display_name: "Tissue" },
        { column_name: "condition", display_name: "Condition" },
      ],
      filterableColColumns: [
        { column_name: "tissue", display_name: "Tissue" },
        { column_name: "condition", display_name: "Condition" },
      ],
      orderableColColumns: [
        { column_name: "default_trait", display_name: "Tissue" },
        { column_name: "condition", display_name: "Condition" },
      ],
      sampleMetadata: [{ column_name: "sample_a" }, { column_name: "sample_b" }],
    },
    catalogStore: {
      selectedTableNames: new Set<string>(),
      selectAll(tableNames: string[]) {
        this.selectedTableNames = new Set(tableNames);
      },
    },
    router: {
      push: () => Promise.resolve(),
      replace: () => Promise.resolve(),
    } as unknown as DispatcherDeps["router"],
    route: {
      fullPath: "/h/CS",
      path: "/h/CS",
      params: { table_names: "CS" },
      query: {},
      name: "heatmap",
    } as unknown as DispatcherDeps["route"],
    __test: { filterChainColumns, filterChainOperators },
  } as TestDeps;
}

function vizAction(patch: Record<string, unknown>): AssistantAction {
  return { kind: "viz_update", spec: { patch }, status: "pending" };
}

describe("assistant visualization action guardrails", () => {
  it("rejects row metadata in sample-axis settings", async () => {
    const action = vizAction({ colOrder: { name: "ortho_id" } });
    const mutated = await createAssistantActionDispatcher(makeDeps()).dispatch(action);

    expect(mutated).toBe(false);
    expect(action.status).toBe("error");
    expect(action.error).toContain("sample/.obs column");
  });

  it("rejects sample metadata in row-axis settings", async () => {
    const action = vizAction({ rowSideColors: ["default_trait"] });
    const mutated = await createAssistantActionDispatcher(makeDeps()).dispatch(action);

    expect(mutated).toBe(false);
    expect(action.status).toBe("error");
    expect(action.error).toContain("row/.var column");
  });

  it("applies valid row and sample settings", async () => {
    const deps = makeDeps();
    const action = vizAction({
      rowSideColors: ["ortho_id", "tf_family"],
      colSideColors: ["default_trait"],
      compare: { groupingColumn: "tissue" },
    });

    const mutated = await createAssistantActionDispatcher(deps).dispatch(action);

    expect(mutated).toBe(true);
    expect(action.status).toBe("applied");
    expect(deps.visualizationStore.$state.rowSideColors).toEqual(["ortho_id", "tf_family"]);
    expect(deps.visualizationStore.$state.colSideColors).toEqual(["default_trait"]);
  });

  it("expands the '*' sentinel to all eligible RowSideColors", async () => {
    const deps = makeDeps();
    deps.idColumn = "length";
    deps.hiddenColumns = ["tf_family"];
    const action = vizAction({ rowSideColors: ["*"] });

    const mutated = await createAssistantActionDispatcher(deps).dispatch(action);

    expect(mutated).toBe(true);
    expect(action.status).toBe("applied");
    // length (id column) and tf_family (hidden) are excluded.
    expect(deps.visualizationStore.$state.rowSideColors).toEqual(["ortho_id", "is_tf"]);
  });

  it("expands the '*' sentinel to all eligible ColSideColors", async () => {
    const deps = makeDeps();
    const action = vizAction({ colSideColors: ["*"] });

    const mutated = await createAssistantActionDispatcher(deps).dispatch(action);

    expect(mutated).toBe(true);
    expect(action.status).toBe("applied");
    expect(deps.visualizationStore.$state.colSideColors).toEqual(["default_trait", "condition"]);
  });

  it("resolves display names before axis validation", async () => {
    const deps = makeDeps();
    const action = vizAction({
      rowSideColors: ["Orthogroup", "TF Family"],
      colSideColors: ["Tissue", "Condition"],
    });

    const mutated = await createAssistantActionDispatcher(deps).dispatch(action);

    expect(mutated).toBe(true);
    expect(action.status).toBe("applied");
    expect(deps.visualizationStore.$state.rowSideColors).toEqual(["ortho_id", "tf_family"]);
    expect(deps.visualizationStore.$state.colSideColors).toEqual(["default_trait", "condition"]);
    expect(action.summary).toContain("Orthogroup");
    expect(action.summary).toContain("Condition");
  });

  it("normalizes filters by sidebar datatype", async () => {
    const deps = makeDeps();
    const dispatcher = createAssistantActionDispatcher(deps);

    await dispatcher.dispatch({ kind: "add_filter", spec: { column: "Length", value: [100, 300] }, status: "pending" });
    await dispatcher.dispatch({ kind: "add_filter", spec: { column: "Is TF", value: true }, status: "pending" });
    await dispatcher.dispatch({ kind: "add_filter", spec: { column: "Orthogroup", value: ["OG1", "OG2"], match_mode: "and" }, status: "pending" });
    await dispatcher.dispatch({ kind: "add_filter", spec: { column: "Condition", has_value: true }, status: "pending" });

    const filters = (deps.filtersStore.toObject?.() as { filters: Record<string, unknown> }).filters;
    expect(filters.length).toMatchObject({ value: [100, 300] });
    expect(filters.is_tf).toMatchObject({ value: true });
    expect(filters.ortho_id).toMatchObject({ value: "OG1|OG2", match_mode: "and", exact: true });
    expect(filters.condition).toMatchObject({ value: "", has_value: true, exact: true });
  });

  it("treats a value-less assistant filter as the Sidebar has-value checkbox", async () => {
    const deps = makeDeps();
    const action: AssistantAction = { kind: "add_filter", spec: { column: "Condition" }, status: "pending" };

    const mutated = await createAssistantActionDispatcher(deps).dispatch(action);

    const filters = (deps.filtersStore.toObject?.() as { filters: Record<string, unknown> }).filters;
    expect(mutated).toBe(true);
    expect(action.summary).toContain("has value");
    expect(filters.condition).toMatchObject({ value: "", has_value: true, exact: true });
  });

  it("sets filter-chain operators using resolved display names", async () => {
    const deps = makeDeps();
    const dispatcher = createAssistantActionDispatcher(deps);

    const action: AssistantAction = { kind: "set_filter_chain", spec: { columns: ["Orthogroup", "TF Family"], operator: "and" }, status: "pending" };
    const mutated = await dispatcher.dispatch(action);

    expect(mutated).toBe(true);
    expect(action.status).toBe("applied");
    expect(deps.__test.filterChainColumns).toEqual([["ortho_id", "tf_family"]]);
    expect(deps.__test.filterChainOperators).toEqual([["ortho_id", "tf_family", "and"]]);
    expect(action.summary).toContain("Orthogroup AND TF Family");
  });

  it("re-homes a bare groupingColumn onto the active compare view", async () => {
    const deps = makeDeps();
    deps.visualizationStore.$state.compare = { groupingColumn: "" };
    deps.route = {
      ...deps.route,
      fullPath: "/c/CS",
      path: "/c/CS",
      name: "compare expression",
    } as unknown as DispatcherDeps["route"];

    const action = vizAction({ groupingColumn: "condition" });
    const mutated = await createAssistantActionDispatcher(deps).dispatch(action);

    expect(mutated).toBe(true);
    expect(action.status).toBe("applied");
    expect((deps.visualizationStore.$state.compare as Record<string, unknown>).groupingColumn).toBe("condition");
  });

  it("re-homes a compare.groupingColumn onto colSideColors when in the heatmap", async () => {
    const deps = makeDeps();
    deps.visualizationStore.$state.colSideColors = ["default_trait"];
    // Default route in makeDeps() is the heatmap (/h/CS).
    const action = vizAction({ compare: { groupingColumn: "condition" } });
    const mutated = await createAssistantActionDispatcher(deps).dispatch(action);

    expect(mutated).toBe(true);
    expect(action.status).toBe("applied");
    // Grouping has no home in the heatmap, so the metadata column is added
    // to the existing ColSideColors selection instead of being dropped.
    expect(deps.visualizationStore.$state.colSideColors).toEqual(["default_trait", "condition"]);
    // No bogus compare grouping column should leak in while at the heatmap.
    expect(deps.visualizationStore.$state.compare).toBeUndefined();
  });

  it("updates visible dataset cards through route table_names", async () => {
    const deps = makeDeps();
    const replace = vi.fn(() => Promise.resolve());
    deps.router = { ...deps.router, replace } as unknown as DispatcherDeps["router"];
    deps.route = {
      ...deps.route,
      fullPath: "/o/arabidopsis_thaliana,solanum_lycopersicum,oryza_sativa",
      path: "/o/arabidopsis_thaliana,solanum_lycopersicum,oryza_sativa",
      params: { table_names: "arabidopsis_thaliana,solanum_lycopersicum,oryza_sativa" },
      name: "ora",
    } as unknown as DispatcherDeps["route"];
    const action: AssistantAction = {
      kind: "dataset_visibility",
      spec: {
        action: "HIDE",
        dataset_ids: ["arabidopsis_thaliana"],
        visible_dataset_ids: ["solanum_lycopersicum", "oryza_sativa"],
      },
      status: "pending",
    };

    const mutated = await createAssistantActionDispatcher(deps).dispatch(action);

    expect(mutated).toBe(true);
    expect(action.status).toBe("applied");
    expect(Array.from(deps.catalogStore.selectedTableNames)).toEqual(["solanum_lycopersicum", "oryza_sativa"]);
    expect(replace).toHaveBeenCalledWith(expect.objectContaining({
      params: expect.objectContaining({ table_names: "solanum_lycopersicum,oryza_sativa" }),
    }));
  });

  it("accepts expressionDisplay viz_update aliases", async () => {
    const deps = makeDeps();
    const action = vizAction({ expressionDisplay: { optionId: "zscore" } });

    const mutated = await createAssistantActionDispatcher(deps).dispatch(action);

    expect(mutated).toBe(true);
    expect(action.status).toBe("applied");
    expect(deps.visualizationStore.$state.expressionDisplay).toEqual({
      optionId: "zscore",
      layer: "getmm",
      transform: "zscore",
    });
  });
});

describe("assistant deeplink state planning", () => {
  it("uses explicit deeplink filters as the target state and clears stale filters", async () => {
    const store = useAssistantStore();
    const msg: ChatMessage = {
      role: "assistant",
      content: 'Opening.\n\n```deeplink\n{"view":"heatmap","tables":["all"],"filters":{"filters":{"tf_family":{"value":"GRAS","exact":true}}}}\n```',
    };
    const context: ClientContext = {
      view: "compare expression",
      route: "/c/CS?id=oldstate",
      filters: {
        filters: {
          tf_family: { value: "C2H2", exact: true },
          ortho_id: { value: "OG0002324", exact: true },
        },
        datasetIdFilters: {},
      },
      visualizations: { compare: { selectedOrthogroup: "OG0002324" } },
    };

    await (store as unknown as { extractAndDispatchActions: (msg: ChatMessage, ctx: ClientContext) => Promise<void> })
      .extractAndDispatchActions(msg, context);

    expect(msg.actions?.[0]?.status).toBe("applied");
    expect(msg.actions?.[0]?.summary).toContain("tf_family");
    expect(msg.actions?.[0]?.summary).toContain("ortho_id");
    expect(msg.content).toContain("Clearing active filter state");
  });
});