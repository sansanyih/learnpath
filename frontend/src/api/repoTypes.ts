export interface ChapterSummary {
  id: string;
  seq: number;
  title: string;
  purpose: string;
  files: string[];
  concepts: string[];
  status: string;
  has_content: boolean;
}

export interface RepoSource {
  id: string;
  repo_full_name: string;
  ref: string;
  status: string;
  file_count: number;
  chapters: ChapterSummary[];
}

export interface ChapterDetail {
  id: string;
  plan_id: string;
  repo_id: string;
  seq: number;
  title: string;
  purpose: string;
  files: string[];
  concepts: string[];
  status: string;
  content_md: string | null;
}

export interface ChapterFile {
  path: string;
  content: string;
}

export interface ChapterFiles {
  files: ChapterFile[];
}
