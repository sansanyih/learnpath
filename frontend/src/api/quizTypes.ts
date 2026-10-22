export interface QuizQuestion {
  id: string;
  type: "choice" | "open";
  question: string;
  options: string[];
  difficulty: number;
}

export interface PhaseQuiz {
  phase_id: string;
  phase_title: string;
  questions: QuizQuestion[];
}

export interface QuestionResult {
  quiz_id: string;
  question: string;
  type: string;
  answer: string;
  score: number;
  dims: Record<string, number>;
  feedback: string;
  reference: string;
  explanation: string;
}

export interface Adjustment {
  id: string;
  action: string;
  message: string;
  tasks: string[];
}

export interface SubmitResult {
  phase_id: string;
  score: number;
  dims: Record<string, number>;
  results: QuestionResult[];
  adjustment: Adjustment | null;
  cost_est: number;
}
