export interface QuizQuestionItem {
  id: string;
  type: "choice" | "open";
  question: string;
  options: string[];
  difficulty: number;
}

export interface ChapterQuiz {
  chapter_id: string;
  chapter_title: string;
  questions: QuizQuestionItem[];
}

export interface ChapterQuizResultItem {
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

export interface ChapterQuizResult {
  chapter_id: string;
  score: number;
  dims: Record<string, number>;
  results: ChapterQuizResultItem[];
  status: string;
}

export interface ChapterQuizLatest {
  chapter_id: string;
  score: number | null;
  results: Array<{
    quiz_id: string;
    question: string;
    type: string;
    score: number;
    feedback: string;
    reference: string;
  }>;
}
