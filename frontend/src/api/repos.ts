import { api } from "./request";
import type { ChapterDetail, ChapterFiles, RepoSource } from "./repoTypes";

export const reposApi = {
  list: (planId: string) => api.get<RepoSource[]>(`/api/plans/${planId}/repos`),
  chapter: (chapterId: string) => api.get<ChapterDetail>(`/api/chapters/${chapterId}`),
  chapterFiles: (chapterId: string) => api.get<ChapterFiles>(`/api/chapters/${chapterId}/files`),
  generateContent: (chapterId: string) =>
    api.post<{ content_md: string; cached: boolean }>(`/api/chapters/${chapterId}/content`),
};
