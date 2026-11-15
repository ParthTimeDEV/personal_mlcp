"""Report generation and inspection logic for the Atlas Copco Market Scout.

Interfaces strictly with atlas.report.build and atlas.storage.
Zero local disk writes: all report generation and downloads stream in-memory.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Literal

from atlas.models import OutputEnvelope

ReportFormat = Literal["pptx", "pdf"]
ReportKind = Literal["onepager", "report"]

KIND_LABELS: dict[str, str] = {
    "onepager": "One-page summary (recommended)",
    "report": "Full report (about 10 slides or pages)",
}

FORMAT_LABELS: dict[ReportFormat, str] = {
    "pptx": "Executive PowerPoint Presentation (.pptx)",
    "pdf": "Executive Digest Document (.pdf)",
}

FORMAT_MIME_TYPES: dict[str, str] = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
}


def get_report_relative_path(run_id: str, fmt: str, kind: str = "report") -> str:
    """Return the relative Volume path where the report is uploaded.

    kind "report": reports/report_<run_id>.<fmt> (atlas.report.build.report_path)
    kind "onepager": reports/onepager_<run_id>.<fmt> (atlas.report.onepager.onepager_path)
    """
    clean_fmt = fmt.lower().lstrip(".")
    return f"reports/{_prefix(kind)}_{run_id}.{clean_fmt}"


def _prefix(kind: str) -> str:
    return "onepager" if kind == "onepager" else "report"


def get_report_filename(run_id: str, fmt: str, kind: str = "report") -> str:
    """Return standard download filename."""
    clean_fmt = fmt.lower().lstrip(".")
    return f"{_prefix(kind)}_{run_id}.{clean_fmt}"


def get_report_mime_type(fmt: str) -> str:
    """Return MIME type for HTTP download headers."""
    clean_fmt = fmt.lower().lstrip(".")
    return FORMAT_MIME_TYPES.get(clean_fmt, "application/octet-stream")


def validate_report_format(fmt: str) -> ReportFormat:
    """Ensure format is either 'pptx' or 'pdf'."""
    clean = fmt.lower().strip()
    if clean not in ("pptx", "pdf"):
        raise ValueError(f"Unsupported report format: '{fmt}'. Must be 'pptx' or 'pdf'.")
    return clean  # type: ignore


def extract_report_preview_metrics(envelope: OutputEnvelope) -> dict[str, Any]:
    """Extract summary metrics from OutputEnvelope for report preview.

    Derives all counts from actual envelope models; zero hand-typed or fake numbers.
    """
    items = envelope.items
    sources = envelope.sources
    stories = envelope.stories

    dates = [i.published_at for i in items if i.published_at]
    if dates:
        date_range_str = f"{min(dates)[:10]} to {max(dates)[:10]}"
    else:
        date_range_str = "(not stated)"

    companies = [i.company for i in items if i.company]
    top_companies = [c for c, _ in Counter(companies).most_common(5)]

    technologies = [i.technology for i in items if i.technology]
    top_technologies = [t for t, _ in Counter(technologies).most_common(3)]

    multi_source_stories = sum(1 for s in stories if len(s.source_ids) >= 2)
    fallback_items = sum(1 for i in items if i.via_fallback)

    return {
        "run_id": envelope.run_id,
        "generated_at": envelope.generated_at,
        "scope_tech": envelope.scope.technology,
        "scope_region": envelope.scope.region,
        "sources_count": len(sources),
        "items_count": len(items),
        "stories_count": len(stories),
        "multi_source_stories_count": multi_source_stories,
        "candidates_considered": envelope.candidates_considered,
        "date_range": date_range_str,
        "top_companies": top_companies,
        "top_technologies": top_technologies,
        "fallback_items_count": fallback_items,
    }


def find_existing_reports(run_id: str, entries: list[str]) -> list[dict[str, str]]:
    """Scan entries from storage.list_dir('reports') for reports matching run_id.

    Supports both 'report_<run_id>.<fmt>' (Sachi's convention) and '<run_id>.<fmt>'.
    Returns sorted list of matching report metadata dicts.
    """
    reports: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for entry in entries:
        filename = entry.rstrip("/")
        # Check if file belongs to this run_id
        if run_id in filename:
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            kind = "onepager" if filename.startswith("onepager_") else "report"
            if ext in ("pptx", "pdf") and (kind, ext) not in seen:
                seen.add((kind, ext))
                if kind == "onepager":
                    label = "One-page summary (PowerPoint)" if ext == "pptx" else "One-page summary (PDF)"
                else:
                    label = "Executive Presentation (PowerPoint)" if ext == "pptx" else "Executive Digest (PDF)"
                reports.append({
                    "run_id": run_id,
                    "kind": kind,
                    "fmt": ext,
                    "filename": filename,
                    "relative_path": f"reports/{filename}",
                    "label": label,
                    "mime_type": get_report_mime_type(ext),
                })

    # One-page summaries first, then full reports; within each, pptx before pdf
    return sorted(reports, key=lambda r: (r["kind"] != "onepager", r["fmt"] != "pptx"))


def generate_report_bytes(run_id: str, fmt: str, kind: str = "report") -> tuple[bytes | None, str | None]:
    """Call atlas.report.build.write_report (kind "report") or atlas.report.onepager.write_onepager
    (kind "onepager") and read back the generated bytes from Volume.

    Returns:
        (report_bytes, None) on success
        (None, error_message) on failure
    """
    try:
        valid_fmt = validate_report_format(fmt)
    except ValueError as err:
        return None, str(err)

    try:
        from atlas.report.build import report_path, write_report
        from atlas.report.onepager import onepager_path, write_onepager
        from atlas import storage
    except ImportError as err:
        return None, f"Report builder module is not available: {err}"

    try:
        # write_report builds the report, writes to storage, and returns the Volume path
        if kind == "onepager":
            vol_path = write_onepager(run_id, valid_fmt)
            rel_path = onepager_path(run_id, valid_fmt)
        else:
            vol_path = write_report(run_id, valid_fmt)
            rel_path = report_path(run_id, valid_fmt)

        # Read the newly written bytes from Volume storage in-memory
        report_bytes = storage.read_bytes(rel_path)
        if not report_bytes:
            return None, f"Report generated at {vol_path} was empty."
        return report_bytes, None
    except Exception as exc:
        return None, f"Report generation failed: {type(exc).__name__}: {exc}"
