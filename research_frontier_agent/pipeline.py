from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .config import resolve_path
from .profile import ProjectContext, ResearchProfile, load_profile, load_project
from .providers import CrossrefProvider, OpenAlexEnricher, PaperProvider, SemanticScholarProvider
from .render import render_app, render_excel, render_notes, render_preview, render_report
from .render.common import output_paths
from .screening.embedding_ranker import EmbeddingRanker
from .screening.keyword_ranker import KeywordRanker
from .screening.llm_judge import JUDGE_SCHEMA_VERSION, ResearchJudge, fallback_judgment
from .storage import FrontierDatabase
from .translation import Translator
from .utils import read_json, stable_paper_id, write_json


def _dates(config: dict[str, Any]) -> tuple[str, str]:
    to_date = config.get("to_date") or date.today().isoformat()
    end = date.fromisoformat(to_date)
    from_date = config.get("from_date") or (end - timedelta(days=int(config.get("days", 7)))).isoformat()
    if date.fromisoformat(from_date) > end:
        raise ValueError("from_date cannot be later than to_date")
    return from_date, to_date


def _context_hash(profile: ResearchProfile, projects: list[ProjectContext], model: str, judge_version: str) -> str:
    source = (
        profile.description + "\n" + "\n".join(project.to_prompt() for project in projects)
        + "\n" + model + "\n" + judge_version
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _select_capacity(papers: list[dict[str, Any]], config: dict[str, Any], profile: ResearchProfile) -> list[dict[str, Any]]:
    capacity = dict(config.get("reading_capacity") or {})
    caps = {
        "A": int(capacity.get("max_A", profile.max_a)),
        "B": int(capacity.get("max_B", profile.max_b)),
        "C": int(capacity.get("max_C", profile.max_c)),
    }
    selected: list[dict[str, Any]] = []
    for priority in ("A", "B", "C"):
        ranked = sorted(
            (p for p in papers if p.get("priority") == priority),
            key=lambda p: (p.get("relevance_score", 0), p.get("semantic_score") or 0),
            reverse=True,
        )
        selected.extend(ranked[:caps[priority]])
    selected.sort(key=lambda p: ("ABC".find(p.get("priority", "Z")), -int(p.get("relevance_score", 0))))
    return selected[:profile.weekly_reading_capacity]


def _priority_stats(papers: list[dict[str, Any]], scanned: int, candidates: int) -> dict[str, int]:
    result = {"scanned": scanned, "candidates": candidates, "A": 0, "B": 0, "C": 0, "D": 0, "Ignore": 0}
    for paper in papers:
        priority = paper.get("priority", "Ignore")
        result[priority] = result.get(priority, 0) + 1
    return result


def _semantic_scholar_queries(config: dict[str, Any], profile: ResearchProfile) -> list[str]:
    configured = config.get("semantic_scholar_queries") or {}
    if isinstance(configured, dict):
        configured = configured.get(profile.name, [])
    if configured:
        return [str(query) for query in configured]
    return profile.core_keywords[:4]


def _merge_discovery_records(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge duplicate provider records while preserving richer metadata."""
    result = dict(existing)
    for key, value in incoming.items():
        if key == "source":
            sources = [part for part in str(result.get("source") or "").split(";") if part]
            if value and value not in sources:
                sources.append(str(value))
            result["source"] = ";".join(sources)
        elif key == "abstract" and len(str(value or "")) > len(str(result.get(key) or "")):
            result[key] = value
            result["abstract_source"] = incoming.get("abstract_source", incoming.get("source", ""))
        elif not result.get(key) and value not in (None, "", [], {}):
            result[key] = value
    return result


def run_pipeline(
    config: dict[str, Any],
    *,
    providers: list[PaperProvider] | None = None,
    embedding_ranker: EmbeddingRanker | None = None,
    judge: ResearchJudge | None = None,
    translator: Translator | None = None,
) -> dict[str, Any]:
    """Run the complete pipeline; injectable components keep external APIs testable."""
    profile = load_profile(resolve_path(config["profile"]))
    projects = [load_project(resolve_path(path)) for path in config.get("projects", [])]
    from_date, to_date = _dates(config)
    paths = output_paths(profile.name, to_date, resolve_path(config.get("output_root", "outputs")))
    database = FrontierDatabase(resolve_path(config.get("database", "state/frontier.db")))
    run_id = database.start_run(profile.name, from_date, to_date)
    errors: list[dict[str, Any]] = []

    try:
        if config.get("skip_screen"):
            source_path = resolve_path(config.get("screened_file") or paths["screened"])
            scan_data = read_json(source_path)
            papers = list(scan_data.get("papers") or (scan_data.get("new", []) + scan_data.get("already_seen", [])))
        elif config.get("skip_scan"):
            source_path = resolve_path(config.get("scan_file") or paths["scan"])
            scan_data = read_json(source_path)
            papers = list(scan_data.get("new", [])) + list(scan_data.get("already_seen", []))
        else:
            if providers is None:
                venues = read_json(resolve_path(config["watchlist"]))
                conference_value = config.get("conference_watchlist")
                if conference_value:
                    conference_path = resolve_path(conference_value)
                    if conference_path.exists():
                        venues += read_json(conference_path)
                providers = []
                if "crossref" in config.get("data_sources", ["crossref"]):
                    providers.append(CrossrefProvider(
                        venues,
                        max_per_venue=int(config.get("max_per_venue", 50)),
                        timeout=float(config.get("request_timeout", 30)),
                        retries=int(config.get("request_retries", 3)),
                        sleep=float(config.get("request_sleep", 0.2)),
                    ))
                if "semantic_scholar" in config.get("data_sources", []):
                    providers.append(SemanticScholarProvider(
                        _semantic_scholar_queries(config, profile),
                        api_key=config.get("semantic_scholar_api_key", ""),
                        api_base=config.get("semantic_scholar_api_base", "https://api.semanticscholar.org/graph/v1"),
                        max_results_per_query=int(config.get("semantic_scholar_max_results", 100)),
                        timeout=float(config.get("request_timeout", 30)),
                        retries=int(config.get("semantic_scholar_request_retries", 5)),
                        sleep=float(config.get("semantic_scholar_request_sleep", 1.1)),
                    ))
            papers = []
            for provider in providers or []:
                found, provider_errors = provider.discover(from_date, to_date)
                papers.extend(found)
                errors.extend(provider_errors)
            unique: dict[str, dict[str, Any]] = {}
            for paper in papers:
                paper_id = stable_paper_id(paper)
                if paper_id in unique:
                    unique[paper_id] = _merge_discovery_records(unique[paper_id], paper)
                else:
                    unique[paper_id] = paper
            papers = list(unique.values())

        new_papers: list[dict[str, Any]] = []
        already_seen: list[dict[str, Any]] = []
        for paper in papers:
            paper_id, is_new = database.upsert_paper(paper, profile.name)
            paper["paper_id"] = paper_id
            paper.setdefault("reading_status", "new")
            (new_papers if is_new else already_seen).append(paper)

        if config.get("enrich"):
            try:
                OpenAlexEnricher(
                    timeout=float(config.get("request_timeout", 30)),
                    retries=int(config.get("request_retries", 3)),
                ).enrich(papers)
            except Exception as exc:
                errors.append({"stage": "openalex", "error": str(exc)})

        if not config.get("skip_screen"):
            papers = KeywordRanker(profile).rank(papers)
        else:
            for paper in papers:
                paper.setdefault("keyword_tier", paper.get("tier", "other"))
                paper.setdefault("matched_keywords", [])
                paper.setdefault("core_hits", [])
                paper.setdefault("proxy_hits", [])
                paper.setdefault("eco_hits", [])

        scan_data = {
            "coverage": {"from": from_date, "to": to_date},
            "profile": profile.name,
            "new": new_papers,
            "already_seen": already_seen,
            "source_errors": errors,
            "data_sources": config.get("data_sources", ["crossref"]),
        }
        write_json(paths["scan"], scan_data)

        if config.get("embedding_enabled"):
            try:
                ranker = embedding_ranker or EmbeddingRanker(
                    backend=config.get("embedding_backend", "sentence-transformers"),
                    model=config.get("embedding_model", "BAAI/bge-m3"),
                    api_base=config.get("embedding_api_base", ""),
                    api_key=config.get("embedding_api_key", ""),
                    timeout=float(config.get("request_timeout", 30)),
                    retries=int(config.get("request_retries", 3)),
                )
                ranker.rank(papers, profile.description)
            except Exception as exc:
                errors.append({"stage": "embedding", "error": str(exc), "fallback": "keyword-only"})
                for paper in papers:
                    paper.setdefault("semantic_score", None)
                    paper.setdefault("semantic_rank", None)
        else:
            for paper in papers:
                paper.setdefault("semantic_score", None)
                paper.setdefault("semantic_rank", None)

        threshold = float(config.get("embedding_threshold", 0.45))
        candidates = [
            paper for paper in papers
            if paper.get("keyword_tier") != "other"
            or (config.get("embedding_enabled") and (paper.get("semantic_score") or 0) >= threshold)
        ]
        write_json(paths["screened"], {**scan_data, "papers": papers, "candidates": candidates})

        judge_enabled = bool(config.get("llm_judge_enabled"))
        if judge_enabled and judge is None:
            try:
                judge = ResearchJudge(
                    model=config.get("llm_model", ""), api_base=config.get("api_base", ""),
                    api_key=config.get("api_key", ""), temperature=float(config.get("temperature", 0.1)),
                    timeout=float(config.get("request_timeout", 60)), retries=int(config.get("request_retries", 3)),
                )
            except ValueError as exc:
                errors.append({"stage": "llm_judge", "error": str(exc), "fallback": "keyword-priority"})
                judge_enabled = False

        judge_version = getattr(judge, "cache_version", JUDGE_SCHEMA_VERSION)
        context_hash = _context_hash(profile, projects, config.get("llm_model", ""), judge_version)
        for paper in papers:
            if paper not in candidates:
                paper.update(fallback_judgment(paper))
                database.update_analysis(paper["paper_id"], paper)
                continue
            parsed: dict[str, Any]
            raw = ""
            if judge_enabled and judge is not None:
                cached = database.get_completed_judgment(paper["paper_id"], context_hash, judge.model)
                if cached:
                    raw, parsed = cached
                    paper["judge_checkpoint"] = "reused"
                else:
                    try:
                        raw, parsed = judge.judge(profile, paper, projects)
                        database.save_judgment(
                            paper["paper_id"], context_hash, judge.model, status="complete", raw_response=raw, parsed=parsed
                        )
                        paper["judge_checkpoint"] = "completed"
                    except Exception as exc:
                        errors.append({"stage": "llm_judge", "paper": paper.get("stable_id"), "error": str(exc)})
                        database.save_judgment(
                            paper["paper_id"], context_hash, judge.model, status="failed", raw_response=raw, error=str(exc)
                        )
                        parsed = fallback_judgment(paper)
                        paper["judge_checkpoint"] = "failed-fallback"
            else:
                parsed = fallback_judgment(paper)
                paper["judge_checkpoint"] = "disabled"
            paper["judge_raw_response"] = raw
            paper.update(parsed)
            database.update_analysis(paper["paper_id"], paper)

        if config.get("translation_enabled"):
            translator = translator or Translator(
                backend=config.get("translation_backend", "auto"),
                model=config.get("translation_model") or config.get("llm_model", ""),
                api_base=config.get("translation_api_base") or config.get("api_base", ""),
                api_key=config.get("translation_api_key") or config.get("api_key", ""),
                temperature=float(config.get("temperature", 0.1)),
                timeout=float(config.get("request_timeout", 60)),
                retries=int(config.get("request_retries", 2)),
            )
            translator.translate_papers(candidates)
            for paper in candidates:
                database.update_analysis(paper["paper_id"], paper)

        report_papers = _select_capacity(candidates, config, profile)
        stats = _priority_stats(report_papers, len(papers), len(candidates))
        judged_stats = _priority_stats(candidates, len(papers), len(candidates))
        result = {
            "run_id": run_id,
            "profile": {"name": profile.name, "path": str(profile.path), "weekly_reading_capacity": profile.weekly_reading_capacity},
            "projects": [project.name for project in projects],
            "coverage": {"from": from_date, "to": to_date},
            "stats": stats,
            "judged_stats": judged_stats,
            "report_papers": report_papers,
            "all_candidates": sorted(candidates, key=lambda p: p.get("relevance_score", 0), reverse=True),
            "new_count": len(new_papers),
            "already_seen_count": len(already_seen),
            "errors": errors,
            "paths": {key: str(value) for key, value in paths.items()},
        }
        write_json(paths["judged"], result)

        modes = set(config.get("output_modes") or ["html"])
        if "html" in modes:
            render_report(result, paths["html"])
        if "excel" in modes:
            render_excel(result["all_candidates"], judged_stats, paths["excel"])
        if "app" in modes:
            render_app(result["all_candidates"], judged_stats, paths["app"], profile.name, result["coverage"])
        if "notes" in modes:
            render_notes(report_papers, paths["notes"])
        if "codex" in modes:
            render_preview(report_papers, stats, paths["codex"])

        database.finish_run(run_id, stats, errors)
        return result
    finally:
        database.close()
