import { backendFetch } from "@/lib/backend-client";
import type {
  Benchmark,
  Insights,
  PipelineRun,
  PopularPath,
  Recommendation,
  Referrer,
  Repo,
  RepoCreate,
  Snapshot,
  StageRun,
} from "@/lib/api-types";

type ProviderStatus = { provider: string; calls_today: number };

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

  listRuns: () => backendFetch<PipelineRun[]>("/runs"),
  triggerRun: () => backendFetch<PipelineRun[]>("/runs", { method: "POST" }),
  listRunStages: (id: number) => backendFetch<StageRun[]>(`/runs/${id}/stages`),

  providerStatus: () => backendFetch<ProviderStatus[]>("/providers/status"),
};
