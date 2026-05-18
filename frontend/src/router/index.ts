import { createRouter, createWebHistory } from "vue-router";

const CatalogView = () => import("@/views/CatalogView.vue");
const AboutView = () => import("@/views/AboutView.vue");
const AdminView = () => import("@/views/AdminView.vue");
const HeatmapView = () => import("@/views/HeatmapView.vue");
const CompareExpressionView = () => import("@/views/CompareExpression.vue")
const PhylogeneticTreeView = () => import("@/views/PhylogeneticTreeView.vue")
const OraView = () => import("@/views/OraView.vue");

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: "/", redirect: "/catalog" },
    { path: "/catalog", name: "catalog", component: CatalogView },
    { path: "/about", name: "about", component: AboutView },
    { path: "/admin", name: "admin", component: AdminView },
    {
      path: "/h/:table_names",
      name: "heatmap",
      component: HeatmapView,
    },
    {
      path: "/o/:table_names",
      name: "ora analysis",
      component: OraView,
    },
    {
      path: "/c/:table_names",
      name: "compare expression",
      component: CompareExpressionView,
    },
    {
      path: "/p/:table_names",
      name: "phylogenetic analysis",
      component: PhylogeneticTreeView,
    },
  ],
});

export default router;
