export interface StatsDay {
  date: string;
  minutes: number;
  count: number;
}

export interface StatsWeekDay {
  date: string;
  minutes: number;
  is_future: boolean;
}

export interface LearningStats {
  streak: number;
  days: StatsDay[];
  week: {
    minutes: number;
    target: number;
    days: StatsWeekDay[];
  };
  review_strategy: {
    intervals: number[];
    mastered_streak: number;
  };
}
