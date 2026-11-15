"""Demo search over a finished run. Reads output/poc_<run_id>.json from Databricks into memory; writes nothing.

Run from the personal_mlcp folder with the venv active:
    python demo_search.py                      interactive: type a word, press Enter (blank line to quit)
    python demo_search.py hydrogen             one search
    python demo_search.py compressor --event acquisition --source fs-elliott
Options: --run RUN_ID  --event TYPE  --technology TEXT  --source TEXT  --label fact|claim  --limit N
All words must match (any of: title, company, product, technology, event type, source, key facts).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from atlas import storage  # noqa: E402


def load(run_id: str | None) -> tuple[str, dict]:
    if run_id is None:
        names = sorted(n for n in storage.list_dir("output") if n.startswith("poc_") and n.endswith(".json"))
        if not names:
            sys.exit("No run found in output/. Run: python -m atlas.run")
        run_id = names[-1][len("poc_"):-len(".json")]
    return run_id, storage.read_json(f"output/poc_{run_id}.json")


def haystack(item: dict) -> str:
    parts = [item.get(k) or "" for k in ("title", "company", "product", "technology", "event_type",
                                          "source_name", "region")]
    parts += item.get("key_facts") or []
    return " ".join(str(p) for p in parts).lower()


def search(items: list[dict], words: list[str], args) -> list[dict]:
    out = []
    for it in items:
        if not all(w.lower() in haystack(it) for w in words):
            continue
        if args.event and (it.get("event_type") or "") != args.event:
            continue
        if args.technology and args.technology.lower() not in (it.get("technology") or "").lower():
            continue
        if args.source and args.source.lower() not in (it.get("source_name") or "").lower() + " " + it.get("source_id", "").lower():
            continue
        if args.label and it.get("label") != args.label:
            continue
        out.append(it)
    out.sort(key=lambda i: i.get("published_at") or "", reverse=True)
    return out


def show(results: list[dict], limit: int) -> None:
    if not results:
        print("  no results. Try one broader word (for example: compressor, hydrogen, vacuum, blower, acquisition).\n")
        return
    print(f"  {len(results)} result(s)" + (f", showing {limit}" if len(results) > limit else "") + "\n")
    for n, it in enumerate(results[:limit], 1):
        label = "FACT " if it.get("label") == "fact" else "claim"
        print(f"  {n}. [{label}] {it.get('title') or '(no title)'}")
        meta = [it.get("published_at") or "date unknown", it.get("source_name") or it.get("source_id")]
        for key in ("company", "product", "technology", "event_type"):
            if it.get(key):
                meta.append(f"{key.replace('_', ' ')}: {it[key]}")
        if it.get("via_fallback"):
            meta.append(f"via fallback for {it.get('fallback_for')}")
        print("     " + " | ".join(str(m) for m in meta))
        for fact in (it.get("key_facts") or [])[:2]:
            print(f"     - {fact}")
        print(f"     {it.get('source_url')}\n")


def main() -> None:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("words", nargs="*")
    p.add_argument("--run")
    p.add_argument("--event")
    p.add_argument("--technology")
    p.add_argument("--source")
    p.add_argument("--label", choices=["fact", "claim"])
    p.add_argument("--limit", type=int, default=8)
    args = p.parse_args()

    run_id, env = load(args.run)
    items = env["items"]
    sources = env.get("sources", [])
    print(f"\nRun {run_id}: {len(items)} item(s) that passed the filter, from "
          f"{sum(1 for s in sources if s.get('items_passed'))} source(s); "
          f"{sum(1 for s in sources if s.get('status') != 'working')} source(s) refused or unreachable.\n")
    if args.words or args.event or args.technology or args.source or args.label:
        show(search(items, args.words, args), args.limit)
        return
    while True:
        try:
            q = input("search> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        show(search(items, q.split(), args), args.limit)


if __name__ == "__main__":
    main()
