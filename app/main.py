"""Dashboard: change the filters, press Done, the system saves them and reruns by itself, then shows the result."""
from __future__ import annotations

import typing

import streamlit as st

from app.lib.data import get_active_prefix, is_demo_prefix, latest_run_id, load_envelope, clear_data_cache
from app.lib.settings_ui import load_technology_labels
from app.lib.simple_ui import run_panel, trigger_rerun
from atlas.models import EventType, ScoutSettings
from atlas.scout import settings_store

st.set_page_config(page_title="Compressor market scout", page_icon="📊", layout="wide")
EVENTS = list(typing.get_args(EventType))
REGIONS = ["US", "CA", "MX"]


st.title("📊 Compressor market scout")
st.caption("Change the filters, press **Done**. The system saves them and reruns automatically.")
if is_demo_prefix():
    st.warning("You are looking at the real demo folders.")

try:
    current = settings_store.load_settings()
except Exception as exc:
    st.error(f"The saved settings could not be read: {exc}")
    st.stop()

with st.form("filters"):
    c1, c2 = st.columns(2)
    regions = c1.multiselect("Regions", REGIONS, default=list(current.regions),
                             help="Only items about these regions are kept.")
    months = c2.slider("How recent (months)", 1, 60, current.recent_months,
                       help="Items older than this are dropped.")
    technologies = c1.multiselect("Technologies (empty = all)", load_technology_labels(),
                                  default=[t for t in current.technologies if t in load_technology_labels()])
    events = c2.multiselect("Types of news (empty = all)", EVENTS, default=list(current.event_types),
                            format_func=lambda e: e.replace("_", " "))
    include = c1.text_area("Also count these words as compressor-related (one per line)",
                           "\n".join(current.extra_compressor_keywords), height=90)
    exclude = c2.text_area("Leave out anything containing these words (one per line)",
                           "\n".join(current.excluded_keywords), height=90)
    done = st.form_submit_button("✅ Done", type="primary")

if done:
    try:
        new = current.model_copy(update=dict(
            regions=regions, recent_months=months, technologies=technologies, event_types=events,
            extra_compressor_keywords=[w.strip() for w in include.splitlines() if w.strip()],
            excluded_keywords=[w.strip() for w in exclude.splitlines() if w.strip()]))
        settings_store.save_settings(ScoutSettings.model_validate(new.model_dump()))
    except Exception as exc:
        st.error(f"Not saved: {exc}")
    else:
        st.success("Saved.")
        trigger_rerun("new filters")

run_panel()

st.divider()
run_id = latest_run_id()
if run_id is None:
    st.info("No results yet. Press Done to run for the first time.")
    st.stop()
try:
    envelope = load_envelope(run_id)
except Exception as exc:
    st.error(f"The latest run could not be read: {exc}")
    st.stop()

others = [i for i in envelope.items if not (i.company or "").lower().startswith("atlas copco")]
m1, m2, m3 = st.columns(3)
m1.metric("Facts kept", len(envelope.items))
m2.metric("Sources read", sum(1 for s in envelope.sources if s.kind != "fallback" and s.items_collected > 0))
m3.metric("Run", run_id)
st.subheader("What we found")
rows = [{"Date": i.published_at or "", "Company": i.company or "", "News": (i.event_type or "other").replace("_", " "),
         "Fact": (i.key_facts[0] if i.key_facts else i.title or ""), "Source": i.source_url}
        for i in sorted(envelope.items, key=lambda i: i.published_at or "", reverse=True)]
st.dataframe(rows, use_container_width=True, hide_index=True,
             column_config={"Source": st.column_config.LinkColumn("Source", display_text="open")})
st.caption("Use **Facts** to mark facts important or not, **Sources** to confirm sources, **Report** for the brief.")
