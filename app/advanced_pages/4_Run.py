"""Run Launcher Page — Atlas Copco Market Scout.

Allows operators to launch end-to-end pipeline scouting runs, monitor real-time
progress via unbuffered subprocess streaming, gracefully terminate active runs,
and inspect execution metrics with zero local data storage.
"""

from __future__ import annotations

import queue
import threading
import time
import streamlit as st

from app.lib.data import (
    clear_data_cache,
    get_active_prefix,
    is_demo_prefix,
    load_envelope,
    load_log,
)
from app.lib.runner import (
    RunProgressTracker,
    build_run_args,
    extract_errors_from_output,
    extract_run_id_from_output,
    start_run,
    terminate_process,
)
from atlas.compliance import load_register


def _enqueue_output(pipe, q: queue.Queue) -> None:
    """Read lines from pipe and put them onto queue."""
    try:
        for line in iter(pipe.readline, ""):
            q.put(line)
    except Exception:
        pass
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def main() -> None:
    st.set_page_config(
        page_title="Run Launcher — Atlas Copco Market Scout",
        page_icon="🚀",
        layout="wide",
    )

    st.title("🚀 Pipeline Run Launcher")
    st.caption("Initiate, monitor, and manage end-to-end competitive intelligence scouting runs.")

    # 1. Environment & Storage Notice
    prefix = get_active_prefix()
    st.sidebar.markdown(f"**Storage Prefix:** `{prefix or '(root / demo)'}`")
    if is_demo_prefix():
        st.sidebar.warning(
            "⚠️ **Live Demo Mode:** `ATLAS_PATH_PREFIX` is empty. You are running against primary demo storage."
        )
    else:
        st.sidebar.info(f"Connected to sandbox prefix: `{prefix}`")

    st.sidebar.caption("Prefix is configured in `.env` and cannot be modified via the UI.")

    # Load register sources for source picker
    try:
        register = load_register()
        available_sources = ["All Sources"] + [s.source_id for s in register]
    except Exception as exc:
        st.sidebar.error(f"Could not load source register: {exc}")
        available_sources = ["All Sources"]

    # 2. Check Session State for Active / Previous Run
    proc = st.session_state.get("run_proc")
    q: queue.Queue | None = st.session_state.get("run_queue")
    tracker: RunProgressTracker | None = st.session_state.get("run_tracker")

    is_running = False
    if proc is not None and tracker is not None and q is not None:
        # Drain all newly arrived lines
        while True:
            try:
                line = q.get_nowait()
                tracker.process_line(line)
            except queue.Empty:
                break

        # Check process status
        poll_code = proc.poll()
        if poll_code is None:
            is_running = True
        else:
            is_running = False
            if not tracker.is_done:
                tracker.is_done = True
                tracker.exit_code = poll_code
                if not tracker.run_id:
                    tracker.run_id = extract_run_id_from_output("\n".join(tracker.lines))
                if poll_code == 0:
                    clear_data_cache()

    # 3. Configuration Form (Disabled when run is active)
    with st.expander("⚙️ Run Configuration", expanded=(not is_running and tracker is None)):
        col1, col2 = st.columns([1, 1])

        with col1:
            selected_source = st.selectbox(
                "Source Selection",
                options=available_sources,
                index=0,
                disabled=is_running,
                help="Execute all registered sources, or select a single source_id.",
            )
            max_items_input = st.number_input(
                "Max Items per Source",
                min_value=0,
                max_value=500,
                value=0,
                step=1,
                disabled=is_running,
                help="Override maximum items to collect per source. Set to 0 to use saved settings value (default 20).",
            )

        with col2:
            st.markdown("**Execution Switches**")
            use_default_settings = st.checkbox(
                "Use Default Settings (`--use-default-settings`)",
                value=False,
                disabled=is_running,
                help="Ignore saved settings in Volume and strictly use config/scout_settings.yaml.",
            )
            no_discovery = st.checkbox(
                "Skip Source Discovery (`--no-discovery`)",
                value=False,
                disabled=is_running,
                help="Do not scout for new candidates; only run vetted registered sources and previously accepted sources.",
            )
            no_fallback = st.checkbox(
                "Skip Fallback Switching (`--no-fallback`)",
                value=False,
                disabled=is_running,
                help="Do not switch to alternative sources if a target competitor site is refused or rate limited.",
            )

    # 4. Action Buttons
    btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 4])

    with btn_col1:
        start_clicked = st.button(
            "🚀 Start Pipeline Run",
            type="primary",
            disabled=is_running,
            use_container_width=True,
        )

    with btn_col2:
        stop_clicked = st.button(
            "🛑 Stop Pipeline Run",
            type="secondary",
            disabled=(not is_running),
            use_container_width=True,
        )

    with btn_col3:
        if tracker is not None and not is_running:
            if st.button("🔄 Clear Output / New Run", use_container_width=False):
                st.session_state["run_proc"] = None
                st.session_state["run_queue"] = None
                st.session_state["run_tracker"] = None
                st.rerun()

    # Handle Stop
    if stop_clicked and proc is not None and tracker is not None:
        terminate_process(proc)
        tracker.is_done = True
        tracker.exit_code = -1
        tracker.stopped_by_user = True
        st.session_state["run_proc"] = None
        st.warning("⚠️ Pipeline run was terminated by operator.")
        st.rerun()

    # Handle Start
    if start_clicked and not is_running:
        try:
            target_src = None if selected_source == "All Sources" else selected_source
            max_items_val = int(max_items_input) if max_items_input > 0 else None
            args = build_run_args(
                only_source=target_src,
                max_items=max_items_val,
                use_default_settings=use_default_settings,
                no_discovery=no_discovery,
                no_fallback=no_fallback,
            )

            new_proc = start_run(args)
            new_queue: queue.Queue = queue.Queue()
            reader_thread = threading.Thread(
                target=_enqueue_output,
                args=(new_proc.stdout, new_queue),
                daemon=True,
            )
            reader_thread.start()

            new_tracker = RunProgressTracker()
            st.session_state["run_proc"] = new_proc
            st.session_state["run_queue"] = new_queue
            st.session_state["run_tracker"] = new_tracker
            st.rerun()
        except Exception as exc:
            st.error(f"❌ Failed to launch pipeline process: {exc}")

    # 5. Live Progress Display & Telemetry
    if tracker is not None:
        st.divider()

        if is_running:
            st.subheader(f"⚡ Pipeline Running: {tracker.stage}")
            p_val = min(max(tracker.progress_percent, 0.0), 1.0)
            st.progress(p_val, text=f"Progress: {int(p_val * 100)}% | Current Source: {tracker.current_source or 'Initializing...'}")

            # Status cards
            mcol1, mcol2, mcol3 = st.columns(3)
            with mcol1:
                st.metric("Current Stage", tracker.stage)
            with mcol2:
                st.metric("Source Progress", f"{tracker.source_index} / {tracker.total_sources}")
            with mcol3:
                st.metric("Current Target", tracker.current_source or "—")

        elif tracker.is_done:
            if tracker.stopped_by_user:
                st.warning("⚠️ **Run Cancelled:** Pipeline execution was stopped by operator request.")
            elif tracker.exit_code == 0:
                st.success(f"🎉 **Run Successful!** Pipeline run `{tracker.run_id or 'completed'}` exited with code 0.")
                
                # Try to load envelope and show summary telemetry
                if tracker.run_id:
                    try:
                        envelope = load_envelope(tracker.run_id)
                        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
                        with sc1:
                            st.metric("Sources Checked", len(envelope.sources))
                        with sc2:
                            st.metric("Items Collected", sum(s.items_collected for s in envelope.sources))
                        with sc3:
                            st.metric("Items Passed", len(envelope.items))
                        with sc4:
                            st.metric("Stories Built", len(envelope.stories))
                        with sc5:
                            st.metric("Candidates Vetted", envelope.candidates_considered)
                    except Exception:
                        pass

                # Navigation button to Dashboard
                st.page_link(
                    "pages/1_Dashboard.py",
                    label="📊 View Extracted Intelligence in Dashboard",
                    icon="📊",
                )

            else:
                st.error(f"❌ **Run Failed:** Pipeline process exited with code `{tracker.exit_code}`.")
                errs = tracker.errors or extract_errors_from_output("\n".join(tracker.lines))
                if errs:
                    st.markdown("**Error Details:**")
                    for err in errs:
                        st.error(f"• {err}")

        # 6. Source Progress Table (if any sources processed)
        if tracker.sources_status:
            with st.expander("📋 Per-Source Status Breakdown", expanded=False):
                source_rows = []
                for s_id, s_info in tracker.sources_status.items():
                    source_rows.append({
                        "Source ID": s_id,
                        "Status": s_info.get("status", "pending"),
                        "Collected": s_info.get("collected", 0),
                        "Passed": s_info.get("passed", 0),
                        "Total Clean": s_info.get("total", 0),
                        "Note": s_info.get("note", ""),
                    })
                st.dataframe(source_rows, use_container_width=True)

        # 7. Live Console Output
        with st.expander("📜 Console Output", expanded=True):
            st.code("\n".join(tracker.lines) if tracker.lines else "Waiting for subprocess output...", language="text")

            if tracker.lines:
                st.download_button(
                    label="📥 Download Console Log",
                    data="\n".join(tracker.lines),
                    file_name=f"pipeline_run_{tracker.run_id or 'log'}.txt",
                    mime="text/plain",
                )

    # 6. Trigger auto-refresh while process is actively running
    if is_running:
        time.sleep(0.5)
        st.rerun()


if __name__ == "__main__":
    main()
