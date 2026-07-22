export const queryKeys = {
  repos: {
    all: ["repos"] as const,
    detail: (id: number) => ["repos", id] as const,
    snapshots: (id: number) => ["repos", id, "snapshots"] as const,
    insights: (id: number) => ["repos", id, "insights"] as const,
    benchmarks: (id: number) => ["repos", id, "benchmarks"] as const,
    referrers: (id: number) => ["repos", id, "referrers"] as const,
    popularPaths: (id: number) => ["repos", id, "popular-paths"] as const,
  },
  recommendations: {
    all: ["recommendations"] as const,
  },
  drafts: {
    all: ["drafts"] as const,
  },
  runs: {
    all: ["runs"] as const,
    stages: (id: number) => ["runs", id, "stages"] as const,
  },
  providers: {
    status: ["providers", "status"] as const,
  },
};
