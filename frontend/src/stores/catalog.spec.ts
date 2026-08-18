import { beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";

import { useCatalogStore } from "./catalog";

describe("catalog orthogroup capabilities", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("requires every selected dataset to support orthogroups", () => {
    const store = useCatalogStore();
    store.setOrthogroupCapabilities([
      { table_name: "with_ogs", has_orthogroups: true },
      { table_name: "without_ogs", has_orthogroups: false },
    ]);

    store.selectAll(["with_ogs"]);
    expect(store.allSelectedHaveOrthogroups).toBe(true);

    store.selectAll(["with_ogs", "without_ogs"]);
    expect(store.allSelectedHaveOrthogroups).toBe(false);
  });

  it("keeps legacy catalog entries backward compatible", () => {
    const store = useCatalogStore();
    store.setOrthogroupCapabilities([{ table_name: "legacy" }]);
    expect(store.hasOrthogroups("legacy")).toBe(true);
  });
});