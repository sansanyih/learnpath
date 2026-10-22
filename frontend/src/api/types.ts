export interface User {
  id: string;
  email: string;
  display_name?: string | null;
  role: string;
}

export interface TokenResponse {
  token: string;
  user: User;
}

export interface KnowledgePoint {
  name: string;
  objective: string;
}

export interface PhaseSkeleton {
  id: string;
  seq: number;
  title: string;
  days: number;
  focus: string;
  knowledge_points: KnowledgePoint[];
}

export interface PlanSummary {
  id: string;
  goal_title: string;
  status: string;
  created_at: string;
  phase_count: number;
  task_count: number;
}

export interface TaskItem {
  id: string;
  day_offset: number;
  title: string;
  type: string;
  duration_min: number;
  resource: string;
  acceptance: string;
  status: string;
}

export interface PhaseDetailItem {
  id: string;
  seq: number;
  title: string;
  days: number;
  focus: string;
  deliverable: string;
  status: string;
  knowledge_points: Array<KnowledgePoint & { id: string; seq: number }>;
  tasks: TaskItem[];
}

export interface PlanDetail {
  id: string;
  goal_title: string;
  goal_raw: string;
  daily_minutes: number;
  level: string;
  deadline: string | null;
  status: string;
  created_at: string;
  phases: PhaseDetailItem[];
}

export interface GuideMaterial {
  title: string;
  url: string;
  kind: string;
}

export interface GuideConcept {
  name: string;
  explanation: string;
}

export interface GuideCodeExample {
  title: string;
  language: string;
  code: string;
  note: string;
}

export interface TaskGuide {
  steps: string[];
  concepts: GuideConcept[];
  code_examples: GuideCodeExample[];
  materials: GuideMaterial[];
  search_queries: string[];
  self_check: string[];
  pitfalls: string[];
}

export interface TaskSibling {
  id: string;
  title: string;
  status: string;
  day_offset: number;
}

export interface TaskDetail {
  id: string;
  title: string;
  type: string;
  duration_min: number;
  acceptance: string;
  status: string;
  day_offset: number;
  phase_id: string;
  phase_title: string;
  plan_id: string;
  goal_title: string;
  phase_tasks: TaskSibling[];
  guide: TaskGuide | null;
}
