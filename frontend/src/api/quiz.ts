import { api } from "./request";
import type { PhaseQuiz, SubmitResult } from "./quizTypes";

export const quizApi = {
  create: (planId: string, phaseId: string) =>
    api.post<PhaseQuiz>(`/api/plans/${planId}/phases/${phaseId}/quiz`),
  submit: (phaseId: string, answers: Array<{ quiz_id: string; answer: string }>) =>
    api.post<SubmitResult>("/api/quizzes/submit", { phase_id: phaseId, answers }),
  adopt: (adjustmentId: string) =>
    api.post<{ ok: boolean; status: string; inserted: number }>(
      `/api/adjustments/${adjustmentId}/adopt`,
    ),
  ignore: (adjustmentId: string) =>
    api.post<{ ok: boolean; status: string }>(`/api/adjustments/${adjustmentId}/ignore`),
};
