"""Streamlit pieces shared by the simple pages: the rerun trigger and the self-refreshing progress panel."""
from __future__ import annotations

import streamlit as st

from app.lib.data import clear_data_cache
from app.lib.simple import start_rerun


def trigger_rerun(reason: str) -> None:
    """Start a rerun after a save. If one is already running, queue one more to start right after it."""
    watcher = st.session_state.get("watcher")
    if watcher is not None and watcher.running:
        st.session_state["pending_rerun"] = True
        st.info("A run is already going. Your change is saved and a new run starts right after it.")
    else:
        st.session_state["watcher"] = start_rerun(reason)


def run_panel() -> None:
    """Shows the run in progress (refreshes every 3 seconds) and starts a queued rerun when one is waiting."""
    @st.fragment(run_every=3)
    def panel() -> None:
        watcher = st.session_state.get("watcher")
        if watcher is None:
            return
        if watcher.running:
            n, total = watcher.progress()
            st.progress(n / total if total else 0.0,
                        text=f"Rerunning ({watcher.reason}). Source {n} of {total}. {watcher.last_line()[:90]}")
            return
        if st.session_state.pop("pending_rerun", False):
            st.session_state["watcher"] = start_rerun("your latest changes")
            st.rerun()
        if watcher.exit_code == 0:
            clear_data_cache()
            st.success("The rerun is finished. The results are up to date.")
        else:
            st.error(f"The run stopped with an error (exit code {watcher.exit_code}). Last lines:")
            st.code("\n".join(watcher.lines[-8:]) or "no output")
    panel()
