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