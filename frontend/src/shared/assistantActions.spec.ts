import { describe, expect, it } from "vitest";

import { createAssistantActionDispatcher, type DispatcherDeps } from "./assistantActions";
import type { AssistantAction } from "@/stores/assistant";

function makeDeps(): DispatcherDeps {
  const state: Record<string, unknown> = {
    rowSideColors: [],
    colSideColors: [],
    rowOrder: { name: "", order: "asc" },
    colOrder: { name: "", order: "asc" },
    customColOrder: {
      enabled: false,
      mode: "metadata",
      metadataColumn: "tissue_types",
      metadataValues: [],
      sampleNames: [],
    },
  };

  return {
    filtersStore: {
      setFilter: () => undefined,
      removeFilter: () => undefined,
      clearFilters: () => undefined,
    },
    visualizationStore: {
      $state: state,
      $patch: (mutator) => mutator(state),
      toObject: () => ({ ...state }),
    },
    columnsStore: {
      rowColumns: [{ column_name: "ortho_id" }, { column_name: "tf_family" }],
      colColumns: [{ column_name: "tissue_types" }, { column_name: "condition" }],
      filterableColColumns: [{ column_name: "tissue" }, { column_name: "condition" }],
      orderableColColumns: [{ column_name: "tissue_types" }, { column_name: "condition" }],
      sampleMetadata: [{ column_name: "sample_a" }, { column_name: "sample_b" }],
    },
    catalogStore: { selectedTableNames: new Set<string>() },
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
  };
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
    const action = vizAction({ rowSideColors: ["tissue_types"] });
    const mutated = await createAssistantActionDispatcher(makeDeps()).dispatch(action);

    expect(mutated).toBe(false);
    expect(action.status).toBe("error");
    expect(action.error).toContain("row/.var column");
  });

  it("applies valid row and sample settings", async () => {
    const deps = makeDeps();
    const action = vizAction({
      rowSideColors: ["ortho_id", "tf_family"],
      colSideColors: ["tissue_types"],
      compare: { groupingColumn: "tissue" },
    });

    const mutated = await createAssistantActionDispatcher(deps).dispatch(action);

    expect(mutated).toBe(true);
    expect(action.status).toBe("applied");
    expect(deps.visualizationStore.$state.rowSideColors).toEqual(["ortho_id", "tf_family"]);
    expect(deps.visualizationStore.$state.colSideColors).toEqual(["tissue_types"]);
  });
});