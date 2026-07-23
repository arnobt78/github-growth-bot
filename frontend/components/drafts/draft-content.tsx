import type {
  MissingDocSuggestionContent,
  ReadmeSuggestionContent,
  SeoSuggestionContent,
  TopicSuggestionContent,
} from "@/types/drafts";
import { Chip } from "@/components/ui/chip";

function isReadmeSuggestion(c: unknown): c is ReadmeSuggestionContent {
  return typeof c === "object" && c !== null && typeof (c as ReadmeSuggestionContent).suggested === "string" && "current" in c;
}

function isMissingDocSuggestion(c: unknown): c is MissingDocSuggestionContent {
  return typeof c === "object" && c !== null && typeof (c as MissingDocSuggestionContent).suggested === "string" && !("current" in c);
}

function isTopicSuggestion(c: unknown): c is TopicSuggestionContent {
  return typeof c === "object" && c !== null && Array.isArray((c as TopicSuggestionContent).suggested) && Array.isArray((c as TopicSuggestionContent).current);
}

function isSeoSuggestion(c: unknown): c is SeoSuggestionContent {
  return typeof c === "object" && c !== null && typeof (c as SeoSuggestionContent).suggested_description === "string";
}

export function DraftContent({ kind, content }: { kind: string; content: unknown }) {
  if (kind === "readme_suggestion" && isReadmeSuggestion(content)) {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Current</p>
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-2 text-xs">
            {content.current ?? "(no README yet)"}
          </pre>
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Suggested</p>
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-2 text-xs">{content.suggested}</pre>
        </div>
      </div>
    );
  }

  if (kind === "missing_doc_suggestion" && isMissingDocSuggestion(content)) {
    return (
      <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-2 text-xs">{content.suggested}</pre>
    );
  }

  if (kind === "topic_suggestion" && isTopicSuggestion(content)) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {content.suggested.map((topic) => (
          <Chip key={topic}>{topic}</Chip>
        ))}
      </div>
    );
  }

  if (kind === "seo_suggestion" && isSeoSuggestion(content)) {
    return (
      <div className="space-y-1.5 text-sm">
        <p>{content.suggested_description}</p>
        <div className="flex flex-wrap gap-1.5">
          {content.keywords.map((keyword) => (
            <Chip key={keyword}>{keyword}</Chip>
          ))}
        </div>
      </div>
    );
  }

  return <p className="text-sm text-muted-foreground">{JSON.stringify(content)}</p>;
}
