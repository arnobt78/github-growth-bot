// Draft.content is stored as an untyped JSON column on the backend (app/models.py),
// so its per-kind shape can't be expressed in the generated OpenAPI schema — these
// mirror app/pipeline/content/assembler.py's ContentAssembler._content_for exactly.

export interface ReadmeSuggestionContent {
  current: string | null;
  suggested: string;
  reason: string | null;
}

export interface MissingDocSuggestionContent {
  suggested: string;
  reason: string | null;
}

export interface TopicSuggestionContent {
  current: string[];
  suggested: string[];
  reason: string | null;
}

export interface SeoSuggestionContent {
  current: string | null;
  suggested_description: string;
  keywords: string[];
  reason: string | null;
}

export type ReleaseNotesContent = MissingDocSuggestionContent;

export type DraftKind =
  | "readme_suggestion"
  | "missing_doc_suggestion"
  | "topic_suggestion"
  | "seo_suggestion"
  | "release_notes";
