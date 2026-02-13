import "./assets/main.css";

import { createApp } from "vue";
import { createPinia } from "pinia";
import { parse } from "yaml";

import App from "./App.vue";
import router from "./router";

import type { Config } from "@/shared/Config";
import { useVisualizationStore } from "./stores/visualization";
import { useFiltersStore } from "./stores/filters";
import { vTooltip } from "@/shared/tooltipDirective";

async function initApp() {
  const baseUrl = import.meta.env.BASE_URL || "/";
  const response = await fetch(`${baseUrl}genxbrowser_config.yaml`);
  const configYaml = await response.text();
  const config = parse(configYaml) as Config;

  const app = createApp(App);
  app.directive("tooltip", vTooltip);
  const pinia = createPinia();

  app.use(router);
  app.use(pinia);
  app.provide("config", config);

  //Initialize pinia stores with config data
  const visualizationStore = useVisualizationStore();
  visualizationStore.initialize(config.visualization.id_column);

  const filtersStore = useFiltersStore();
  filtersStore.setIdColumnName(config.visualization.id_column);

  app.mount("#app");
}

initApp();
