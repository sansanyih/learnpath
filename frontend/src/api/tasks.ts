import { api } from "./request";
import type { TaskDetail, TaskGuide } from "./types";

export const tasksApi = {
  updateStatus: (taskId: string, status: "todo" | "done") =>
    api.patch<{ id: string; status: string; phase_id: string; phase_status: string }>(
      `/api/tasks/${taskId}`,
      { status },
    ),
  detail: (taskId: string) => api.get<TaskDetail>(`/api/tasks/${taskId}`),
  guide: (taskId: string) => api.post<TaskGuide>(`/api/tasks/${taskId}/guide`),
};
