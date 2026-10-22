export interface ChapterStatusResponse {
  status: "todo" | "learning" | "review" | "mastered";
}

export interface ReviewQueueItem {
  id: string;
  kp_id: string;
  kp_name: string;
  objective: string;
  phase_title: string;
  plan_id: string;
  due_at: string | null;
  overdue: boolean;
  interval_days: number;
  mastery_score: number;
  mastery_status: string;
}

export interface MasteryItem {
  kp_id: string;
  kp_name: string;
  phase_title: string;
  plan_id: string;
  score: number;
  status: string;
  attempts: number;
  last_score: number | null;
  due_at: string | null;
}

export interface MasterySummary {
  average: number;
  total: number;
  mastered: number;
  learning: number;
  review: number;
}

export interface MasteryDashboard {
  items: MasteryItem[];
  summary: MasterySummary;
}
