import { api } from "./request";
import type { LearningStats } from "./statsTypes";

export const statsApi = {
  get: () => api.get<LearningStats>("/api/stats"),
};

export const meApi = {
  exportData: () => api.get<Record<string, unknown>>("/api/me/export"),
  deleteAccount: () => api.delete<{ ok: boolean; message: string }>("/api/me"),
};
