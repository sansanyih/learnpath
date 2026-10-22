import { createRouter, createWebHistory } from "vue-router";

import { useSessionStore } from "@/stores/session";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "landing", component: () => import("@/views/LandingView.vue") },
    { path: "/demo", name: "demo", component: () => import("@/views/DemoView.vue") },
    { path: "/login", name: "login", component: () => import("@/views/LoginView.vue") },
    { path: "/plans", name: "plans", component: () => import("@/views/PlansView.vue") },
    {
      path: "/plans/:id",
      name: "plan-detail",
      component: () => import("@/views/PlanDetailView.vue"),
      meta: { auth: true },
    },
    {
      path: "/plans/:planId/chapters/:chapterId",
      name: "chapter",
      component: () => import("@/views/ChapterView.vue"),
      meta: { auth: true },
    },
    {
      path: "/plans/:planId/phases/:phaseId/quiz",
      name: "quiz",
      component: () => import("@/views/QuizView.vue"),
      meta: { auth: true },
    },
    {
      path: "/plans/:planId/tasks/:taskId",
      name: "task-guide",
      component: () => import("@/views/TaskGuideView.vue"),
      meta: { auth: true },
    },
    {
      path: "/review",
      name: "review",
      component: () => import("@/views/ReviewView.vue"),
      meta: { auth: true },
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("@/views/NotFoundView.vue"),
    },
  ],
  scrollBehavior: (to, _from, savedPosition) => {
    if (savedPosition) return savedPosition;
    if (to.hash) return { el: to.hash, behavior: "smooth" };
    return { top: 0 };
  },
});

router.beforeEach(async (to) => {
  const session = useSessionStore();
  if (session.token && !session.user) {
    try {
      await session.fetchMe();
    } catch {
      session.logout();
    }
  }
  if (to.meta.auth && !session.token) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && session.token) {
    return { name: "plans" };
  }
});

export default router;
