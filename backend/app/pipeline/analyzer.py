from app.pipeline.base import PipelineContext, Stage


class Analyzer(Stage):
    name = "analyzer"

    def run(self, ctx: PipelineContext) -> PipelineContext:
        n = ctx.normalized
        findings: list[dict] = []

        if not n.get("has_license"):
            findings.append({"category": "missing_license", "message": "This repo has no LICENSE file, which discourages adoption and contributions.", "impact": 7, "effort": 1})

        if not n.get("has_contributing"):
            findings.append({"category": "missing_contributing", "message": "No CONTRIBUTING.md — first-time contributors have no guidance.", "impact": 4, "effort": 2})

        if not n.get("topics"):
            findings.append({"category": "missing_topics", "message": "No repository topics set, which hurts GitHub search discoverability.", "impact": 6, "effort": 1})

        benchmarks = n.get("benchmarks", [])
        if benchmarks:
            avg_benchmark_stars = sum(b["stargazers_count"] for b in benchmarks) / len(benchmarks)
            if avg_benchmark_stars > n.get("stars", 0):
                findings.append({
                    "category": "benchmark_gap",
                    "message": f"Similar repos average {int(avg_benchmark_stars)} stars vs. this repo's {n.get('stars', 0)}.",
                    "impact": 5,
                    "effort": 5,
                })

        referrers = n.get("referrers", [])
        if referrers:
            top_referrer = max(referrers, key=lambda r: r["count"])
            if top_referrer["count"] >= 100:
                findings.append({
                    "category": "referrer_spike",
                    "message": f"Traffic spike from {top_referrer['referrer']} ({top_referrer['count']} views) — worth capitalizing on.",
                    "impact": 6,
                    "effort": 3,
                })

        ctx.findings = findings
        return ctx
