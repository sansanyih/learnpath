import { api } from "./request";
import type { PlanDetail, PlanSummary } from "./types";

export const plansApi = {
  list: () => api.get<PlanSummary[]>("/api/plans"),
  detail: (id: string) => api.get<PlanDetail>(`/api/plans/${id}`),
  remove: (id: string) => api.delete<void>(`/api/plans/${id}`),
};
