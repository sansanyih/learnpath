import { api } from "./request";
import type { ChapterStatusResponse } from "./reviewTypes";
import type { MasteryDashboard, ReviewQueueItem } from "./reviewTypes";

export const reviewApi = {
  queue: () => api.get<{ items: ReviewQueueItem[]; total: number }>("/api/review/queue"),
  complete: (reviewId: string, result: "again" | "hard" | "good") =>
    api.post<{ ok: boolean; interval_days: number; due_at: string }>(
      `/api/review/${reviewId}/complete`,
      { result },
    ),
  mastery: () => api.get<MasteryDashboard>("/api/mastery"),
};

export const chapterStatusApi = {
  get: (chapterId: string) => api.get<ChapterStatusResponse>(`/api/chapters/${chapterId}/progress`),
  set: (chapterId: string, status: string) =>
    api.put<ChapterStatusResponse>(`/api/chapters/${chapterId}/progress`, { status }),
};
