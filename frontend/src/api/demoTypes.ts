export interface DemoTask {
  title: string;
  type: string;
  duration_min: number;
}

export interface DemoPhase {
  seq: number;
  title: string;
  days: number;
  focus: string;
  knowledge_points: string[];
  tasks: DemoTask[];
}

export interface DemoPlan {
  goal: string;
  level: string;
  daily_minutes: number;
  total_days: number;
  phases: DemoPhase[];
}
