import { backendFetch, backendFetchSystem } from "@/lib/backend-client";
import type {
  Benchmark,
  Draft,
  Insights,
  PipelineRun,
  PopularPath,
  ProviderStatus,
  Recommendation,
  Referrer,
  Repo,
  RepoCreate,
  Snapshot,
  StageRun,
  UserOut,
  UserUpsert,
} from "@/lib/api-types";

export const api = {
  listRepos: () => backendFetch<Repo[]>("/repos"),
  getRepo: (id: number) => backendFetch<Repo>(`/repos/${id}`),
  createRepo: (payload: RepoCreate) =>
    backendFetch<Repo>("/repos", { method: "POST", body: JSON.stringify(payload) }),
  deleteRepo: (id: number) => backendFetch<void>(`/repos/${id}`, { method: "DELETE" }),

  listSnapshots: (id: number) => backendFetch<Snapshot[]>(`/repos/${id}/snapshots`),
  getInsights: (id: number) => backendFetch<Insights>(`/repos/${id}/insights`),
  listBenchmarks: (id: number) => backendFetch<Benchmark[]>(`/repos/${id}/benchmarks`),
  listReferrers: (id: number) => backendFetch<Referrer[]>(`/repos/${id}/referrers`),
  listPopularPaths: (id: number) => backendFetch<PopularPath[]>(`/repos/${id}/popular-paths`),

  listRecommendations: () => backendFetch<Recommendation[]>("/recommendations"),
  dismissRecommendation: (id: number, dismissed: boolean) =>
    backendFetch<Recommendation>(`/recommendations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ dismissed }),
    }),

  listDrafts: () => backendFetch<Draft[]>("/drafts"),
  reviewDraft: (id: number, status: "approved" | "rejected") =>
    backendFetch<Draft>(`/drafts/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  listRuns: () => backendFetch<PipelineRun[]>("/runs"),
  triggerRun: () => backendFetch<{ status: string }>("/runs", { method: "POST" }),
  listRunStages: (id: number) => backendFetch<StageRun[]>(`/runs/${id}/stages`),
  triggerContentRun: () => backendFetch<{ status: string }>("/runs/content", { method: "POST" }),

  providerStatus: () => backendFetch<ProviderStatus[]>("/providers/status"),

  upsertUser: (payload: UserUpsert) =>
    backendFetchSystem<UserOut>("/users/upsert", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getMe: () => backendFetch<UserOut>("/users/me"),
  updateMe: (payload: { notification_email: string | null }) =>
    backendFetch<UserOut>("/users/me", { method: "PATCH", body: JSON.stringify(payload) }),
};
