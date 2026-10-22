import { api } from "./request";
import type { ChapterQuiz, ChapterQuizLatest, ChapterQuizResult } from "./chapterQuizTypes";

export const chapterQuizApi = {
  create: (chapterId: string) => api.post<ChapterQuiz>(`/api/chapters/${chapterId}/quiz`),
  submit: (chapterId: string, answers: Array<{ quiz_id: string; answer: string }>) =>
    api.post<ChapterQuizResult>("/api/chapters/chapter-quiz/submit", {
      chapter_id: chapterId,
      answers,
    }),
  latest: (chapterId: string) => api.get<ChapterQuizLatest>(`/api/chapters/${chapterId}/quiz/latest`),
};
