"""Report: one click gives the brief: the facts, the sources, and why it matters for Atlas Copco."""
from __future__ import annotations

import streamlit as st

from app.lib.data import latest_run_id, list_run_ids
from atlas import storage
from atlas.report.brief import brief_path, write_brief

st.set_page_config(page_title="Report", layout="wide")
st.title("Report")
st.caption("One page with three things: the facts, the sources, and why it matters for Atlas Copco. "
           "Facts marked Not important are left out.")

try:
    runs = list_run_ids()
except Exception as exc:
    st.error(f"Could not list the runs: {exc}")
    st.stop()
if not runs:
    st.info("No results yet. Go to the Dashboard and press Done to run.")
    st.stop()

run_id = st.selectbox("Run", runs, index=runs.index(latest_run_id()) if latest_run_id() in runs else 0)
c1, c2 = st.columns(2)
for col, fmt, label in ((c1, "pptx", "Get the report (PowerPoint)"), (c2, "pdf", "Get the report (PDF)")):
    if col.button(label, type="primary", use_container_width=True):
        with st.spinner("Building the report..."):
            try:
                write_brief(run_id, fmt)
                st.session_state[f"brief_{run_id}_{fmt}"] = storage.read_bytes(brief_path(run_id, fmt))
            except Exception as exc:
                st.error(f"The report could not be built: {type(exc).__name__}: {exc}")
    data = st.session_state.get(f"brief_{run_id}_{fmt}")
    if data:
        mime = "application/pdf" if fmt == "pdf" else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        col.download_button(f"Download {fmt.upper()}", data, file_name=f"brief_{run_id}.{fmt}", mime=mime,
                            use_container_width=True, key=f"dl_{fmt}")
