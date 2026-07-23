import type {
  DraftKind,
  MissingDocSuggestionContent,
  ReadmeSuggestionContent,
  SeoSuggestionContent,
  TopicSuggestionContent,
} from "@/types/drafts";
import { Chip } from "@/components/ui/chip";

function Reason({ reason }: { reason: string | null }) {
  if (!reason) return null;
  return <p className="mt-2 text-xs text-muted-foreground">{reason}</p>;
}

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

export function DraftContent({ kind, content }: { kind: DraftKind | string; content: unknown }) {
  if (kind === "readme_suggestion" && isReadmeSuggestion(content)) {
    return (
      <div>
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
        <Reason reason={content.reason} />
      </div>
    );
  }

  if (kind === "missing_doc_suggestion" && isMissingDocSuggestion(content)) {
    return (
      <div>
        <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-muted/50 p-2 text-xs">{content.suggested}</pre>
        <Reason reason={content.reason} />
      </div>
    );
  }

  if (kind === "topic_suggestion" && isTopicSuggestion(content)) {
    return (
      <div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Current</p>
            <div className="flex flex-wrap gap-1.5">
              {content.current.length > 0
                ? content.current.map((topic, i) => <Chip key={`${topic}-${i}`}>{topic}</Chip>)
                : <p className="text-xs text-muted-foreground">(no topics yet)</p>}
            </div>
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Suggested</p>
            <div className="flex flex-wrap gap-1.5">
              {content.suggested.map((topic, i) => (
                <Chip key={`${topic}-${i}`}>{topic}</Chip>
              ))}
            </div>
          </div>
        </div>
        <Reason reason={content.reason} />
      </div>
    );
  }

  if (kind === "seo_suggestion" && isSeoSuggestion(content)) {
    return (
      <div className="space-y-1.5 text-sm">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Current</p>
            <p className="text-sm">{content.current ?? "(no description yet)"}</p>
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Suggested</p>
            <p className="text-sm">{content.suggested_description}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {content.keywords.map((keyword, i) => (
            <Chip key={`${keyword}-${i}`}>{keyword}</Chip>
          ))}
        </div>
        <Reason reason={content.reason} />
      </div>
    );
  }

  return <p className="text-sm text-muted-foreground">{JSON.stringify(content)}</p>;
}
