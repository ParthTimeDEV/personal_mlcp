"""Atlas Copco Market & Technology Scout — Main Application Entry Point.

This Streamlit application provides competitive intelligence for Atlas Copco's
Compressor Technique business area. It interfaces strictly with Databricks Volumes
via atlas.storage and settings_store helpers, and starts pipeline runs via subprocess.
"""

from __future__ import annotations

import streamlit as st

from app.lib.data import get_active_prefix, is_demo_prefix, latest_run_id, list_run_ids


def main() -> None:
    st.set_page_config(
        page_title="Atlas Copco Market Scout",
        page_icon="⚙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    prefix = get_active_prefix()

    # Sidebar: System Environment & Scope
    st.sidebar.title("⚙️ Market Scout")
    st.sidebar.caption("Atlas Copco — Compressor Technique PoC")
    st.sidebar.divider()

    # Storage Prefix Notice
    st.sidebar.markdown(f"**Storage Prefix:** `{prefix or '(root / demo)'}`")
    if is_demo_prefix():
        st.sidebar.warning(
            "⚠️ **Live Demo Mode:** `ATLAS_PATH_PREFIX` is empty. You are connected to the primary demo storage."
        )
    else:
        st.sidebar.info(f"Connected to sandbox: `{prefix}`")

    # Run selection info
    run_ids = list_run_ids()
    latest_id = latest_run_id()
    if latest_id:
        st.sidebar.success(f"**Latest Run:** `{latest_id}`")
        st.sidebar.caption(f"{len(run_ids)} run(s) available in Volume.")
    else:
        st.sidebar.info("No runs found in storage yet.")

    st.sidebar.divider()
    st.sidebar.caption("Local Enterprise Dashboard • Zero Local Storage")

    # Main page content
    st.title("Atlas Copco Market & Technology Scout")
    st.markdown(
        """
        Welcome to the **Atlas Copco Market & Technology Intelligence Scout**.
        This platform monitors North American compressor news, product announcements,
        facility investments, and competitor activities in full compliance with web
        automation standards and zero-local-data policies.

        ---
        ### Navigation Guide
        Use the sidebar to navigate between operational modules:

        * **📊 Dashboard (`1_Dashboard`):** Browse extracted intelligence, filter facts/claims, explore stories, and export data in-memory.
        * **⚙️ Settings (`2_Settings`):** Configure the Auto Scout Engine, fine-tune relevance thresholds, and manage followed competitor watchlists.
        * **🌐 Sources (`3_Sources`):** Inspect the vetted source register and review newly discovered candidates and trust scores.
        * **🚀 Run Launcher (`4_Run`):** Safely initiate pipeline collection runs with live progress feedback.
        * **📑 Executive Report (`5_Report`):** Generate and download formal executive PPTX presentations and PDF digests.
        """
    )

    if not latest_id:
        st.info(
            "💡 **Initial State:** No pipeline runs detected in the current cloud storage prefix. "
            "Navigate to **Run Launcher** to start a run, or configure your scope in **Settings**."
        )


if __name__ == "__main__":
    main()
