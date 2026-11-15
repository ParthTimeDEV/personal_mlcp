"""Subprocess execution and live progress parsing for atlas.run.

Strict security:
- Never passes Databricks tokens via command-line flags.
- Spawns subprocess using sys.executable with unbuffered text I/O (-u).
- Redacts credentials/tokens in output before display.
- Browser-independent, pure progress parsing unit-tested offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
import subprocess
import sys
from typing import Any


def build_run_args(
    *,
    only_source: str | None = None,
    max_items: int | None = None,
    use_default_settings: bool = False,
    no_discovery: bool = False,
    no_fallback: bool = False,
) -> list[str]:
    """Construct and validate CLI arguments for `python -m atlas.run`.

    Raises ValueError if options are invalid or contain suspicious tokens.
    """
    args: list[str] = []

    if only_source is not None:
        source_clean = only_source.strip()
        if source_clean and source_clean.lower() not in ("all sources", "all"):
            # Security & format validation for source_id
            if any(c in source_clean for c in " \t\n\r;|<>&"):
                raise ValueError(f"Invalid characters in source_id: '{source_clean}'")
            if any(term in source_clean.lower() for term in ["token", "dapi", "secret", "password"]):
                raise ValueError(f"Suspicious source identifier: '{source_clean}'")
            args.extend(["--only", source_clean])

    if max_items is not None:
        if not isinstance(max_items, int) or max_items <= 0:
            raise ValueError(f"max_items must be a positive integer, got: {max_items}")
        args.extend(["--max-items", str(max_items)])

    if use_default_settings:
        args.append("--use-default-settings")

    if no_discovery:
        args.append("--no-discovery")

    if no_fallback:
        args.append("--no-fallback")

    return args


def start_run(args: list[str]) -> subprocess.Popen:
    """Launch `python -m atlas.run <args>` as an asynchronous subprocess.

    Safety:
    - Never injects or passes Databricks tokens in argv.
    - Child process inherits environment (including .env read internally).
    - Unbuffered output (-u) allows real-time stdout streaming.
    """
    # Verify no tokens or secrets in command arguments
    for arg in args:
        if any(secret_term in arg.lower() for secret_term in ["token", "dapi", "secret", "password"]):
            raise ValueError(f"Security violation: suspicious argument blocked: {arg}")

    cmd = [sys.executable, "-u", "-m", "atlas.run", *args]

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=os.environ.copy(),
    )


def terminate_process(proc: subprocess.Popen, timeout: float = 2.0) -> bool:
    """Safely terminate a running pipeline subprocess.

    Returns True if the process has terminated, False if it could not be stopped.
    """
    if proc.poll() is not None:
        return True

    try:
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=timeout)
            return True
    except (ProcessLookupError, PermissionError):
        # Process already gone
        return True
    except Exception:
        return proc.poll() is not None


_SECRET_ASSIGN_RE = re.compile(r"((?:token|secret|password|key)\s*[:=]\s*)([^\s,;]+)", re.IGNORECASE)


def sanitize_output_line(line: str) -> str:
    """Redact any potential Databricks tokens or credential values from console output."""
    if not line:
        return line
    redacted = _SECRET_ASSIGN_RE.sub(r"\1[REDACTED]", line)
    # Match long hex-like or dapi tokens
    return re.sub(r"\bdapi[a-zA-Z0-9_\-]{16,}\b", "[REDACTED_TOKEN]", redacted)


def parse_progress_line(line: str) -> dict[str, Any] | None:
    """Parse a single console output line from atlas.run into structured progress state.

    Pure function: returns a dict with progress metadata, or None if the line
    is unstructured text.
    """
    clean = line.strip()
    if not clean:
        return None

    # Source progress: [1/5] source_id
    src_match = re.match(r"^\[([0-9]+)/([0-9]+)\]\s+([a-zA-Z0-9_\-]+)$", clean)
    if src_match:
        cur, total, src_id = int(src_match.group(1)), int(src_match.group(2)), src_match.group(3)
        return {
            "type": "source_start",
            "current": cur,
            "total": total,
            "source_id": src_id,
            "progress_percent": cur / total if total > 0 else 0.0,
        }

    # Gate refusal: "refused by the compliance gate: reasons..."
    if "refused by the compliance gate:" in clean:
        reasons = clean.split("refused by the compliance gate:", 1)[1].strip()
        return {
            "type": "source_refused",
            "reasons": reasons,
        }

    # Source allowed: "allowed; fetching up to N pages"
    if "allowed; fetching up to" in clean:
        return {
            "type": "source_allowed",
            "message": clean,
        }

    # Collection: "collected X page(s) of Y listed"
    col_match = re.search(r"collected\s+([0-9]+)\s+page\(s\)", clean)
    if col_match:
        return {
            "type": "collection",
            "pages_collected": int(col_match.group(1)),
        }

    # Filter completion: "done: X of Y item(s) passed the filter"
    done_match = re.search(r"done:\s+([0-9]+)\s+of\s+([0-9]+)\s+item\(s\)\s+passed", clean)
    if done_match:
        passed, total = int(done_match.group(1)), int(done_match.group(2))
        return {
            "type": "source_done",
            "passed": passed,
            "total": total,
        }

    # Run ID announcement: "Run 20261115T045141Z starting" or "run_id: 20261115T045141Z"
    run_id_match = re.search(r"^run_id:\s*([0-9]{8}T[0-9]{6}Z)$", clean)
    if run_id_match:
        return {"type": "run_id", "run_id": run_id_match.group(1)}

    run_start_match = re.search(r"^Run\s+([0-9]{8}T[0-9]{6}Z)\s+starting", clean)
    if run_start_match:
        return {"type": "run_id", "run_id": run_start_match.group(1)}

    # Stage transitions
    if "Discovery: looking for new candidate sources" in clean:
        return {"type": "stage", "stage": "discovery"}
    if clean.startswith("Switching:"):
        return {"type": "stage", "stage": "switching"}

    # Discovery summary: "discovery: X candidate(s) found, Y vetted, Z usable"
    disc_summary = re.search(
        r"discovery:\s+([0-9]+)\s+candidate\(s\)\s+found,\s+([0-9]+)\s+vetted,\s+([0-9]+)\s+usable", clean
    )
    if disc_summary:
        return {
            "type": "discovery_summary",
            "found": int(disc_summary.group(1)),
            "vetted": int(disc_summary.group(2)),
            "usable": int(disc_summary.group(3)),
        }

    # Switched summary: "Switched: refused_id -> X item(s)"
    if clean.startswith("Switched:"):
        return {"type": "switched", "message": clean}

    # Validation: "output validated: PASS" or "output validated: FAIL"
    if clean.startswith("output validated:"):
        status = clean.split("output validated:", 1)[1].strip()
        return {"type": "validation", "status": status}

    # Local data check: "local data check: PASS"
    if clean.startswith("local data check:"):
        status = clean.split("local data check:", 1)[1].strip()
        return {"type": "local_data_check", "status": status}

    # Fatal error or error line
    if clean.startswith("Cannot start:") or " ERROR: " in clean or clean.startswith("ERROR:"):
        return {"type": "error", "error": clean}

    return None


def extract_run_id_from_output(output_text: str) -> str | None:
    """Scan accumulated process output for the run_id timestamp.

    Prioritizes explicit 'run_id: <timestamp>' lines at the end of summary,
    falling back to 'Run <timestamp> starting'.
    """
    explicit = re.findall(r"run_id:\s*([0-9]{8}T[0-9]{6}Z)", output_text)
    if explicit:
        return explicit[-1]
    matches = re.findall(r"\b([0-9]{8}T[0-9]{6}Z)\b", output_text)
    return matches[0] if matches else None


def extract_errors_from_output(output_text: str) -> list[str]:
    """Extract distinct error messages from accumulated console text."""
    errors: list[str] = []
    lines = output_text.splitlines()
    in_errors_block = False

    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        if clean.startswith("Cannot start:"):
            errors.append(clean)
        elif clean.startswith("Errors:"):
            in_errors_block = True
        elif in_errors_block:
            if clean.startswith("- "):
                errors.append(clean.removeprefix("- ").strip())
            elif clean.startswith("Written to Databricks:") or clean.startswith("output validated:"):
                in_errors_block = False
        elif " ERROR: " in clean or clean.startswith("ERROR:"):
            errors.append(clean)
        elif "output validation failed:" in clean:
            errors.append(clean)

    return errors


@dataclass
class RunProgressTracker:
    """Tracks live progress, stage transitions, per-source metrics, and console log."""

    run_id: str | None = None
    stage: str = "Initializing"
    current_source: str | None = None
    source_index: int = 0
    total_sources: int = 0
    progress_percent: float = 0.0
    lines: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    sources_status: dict[str, dict[str, Any]] = field(default_factory=dict)
    is_done: bool = False
    exit_code: int | None = None
    output_validated: bool | None = None
    local_data_check: bool | None = None
    stopped_by_user: bool = False

    def process_line(self, raw_line: str) -> None:
        """Process a raw line from process stdout."""
        clean_raw = raw_line.rstrip("\r\n")
        sanitized = sanitize_output_line(clean_raw)
        self.lines.append(sanitized)

        parsed = parse_progress_line(clean_raw)
        if not parsed:
            return

        ptype = parsed.get("type")

        if ptype == "run_id":
            if not self.run_id:
                self.run_id = parsed["run_id"]

        elif ptype == "stage":
            stg = parsed["stage"]
            if stg == "discovery":
                self.stage = "Source Discovery"
            elif stg == "switching":
                self.stage = "Fallback Switching"

        elif ptype == "source_start":
            self.stage = "Collection & Extraction"
            self.current_source = parsed["source_id"]
            self.source_index = parsed["current"]
            self.total_sources = parsed["total"]
            self.progress_percent = parsed["progress_percent"]
            self.sources_status[self.current_source] = {
                "source_id": self.current_source,
                "status": "processing",
                "collected": 0,
                "passed": 0,
                "total": 0,
                "note": "",
            }

        elif ptype == "source_refused":
            if self.current_source and self.current_source in self.sources_status:
                self.sources_status[self.current_source]["status"] = "refused"
                self.sources_status[self.current_source]["note"] = parsed["reasons"]

        elif ptype == "collection":
            if self.current_source and self.current_source in self.sources_status:
                self.sources_status[self.current_source]["collected"] = parsed["pages_collected"]

        elif ptype == "source_done":
            if self.current_source and self.current_source in self.sources_status:
                self.sources_status[self.current_source]["status"] = "passed"
                self.sources_status[self.current_source]["passed"] = parsed["passed"]
                self.sources_status[self.current_source]["total"] = parsed["total"]

        elif ptype == "validation":
            self.output_validated = (parsed["status"] == "PASS")
            self.stage = "Finalizing"

        elif ptype == "local_data_check":
            self.local_data_check = (parsed["status"] == "PASS")

        elif ptype == "error":
            self.errors.append(parsed["error"])
