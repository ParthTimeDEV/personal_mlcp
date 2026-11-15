"""Atlas Copco Market & Technology Scout — Sources & Candidate Review.

This screen provides visibility into the vetted source register (config/sources.yaml)
and allows operators to inspect discovered candidate sources, audit automated trust
scoring, and record Accept/Reject decisions in accordance with strict safety rules.
"""

from __future__ import annotations

from typing import Any
import streamlit as st

from atlas.compliance import load_register
from atlas.models import Candidate, CandidateDecision, Source
from atlas.scout import settings_store
from app.lib.data import clear_data_cache, get_active_prefix, is_demo_prefix
from app.lib.sources import (
    DISCLAIMER_TEXT,
    build_candidate_decision,
    can_accept_candidate,
    filter_candidates,
    prepare_candidate_rows,
    prepare_register_rows,
)


def render_sources() -> None:
    st.set_page_config(
        page_title="Sources • Atlas Copco Scout",
        page_icon="🌐",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("🌐 Source Register & Candidate Review")
    st.caption("Inspect the vetted source register and review newly discovered candidates and trust scores.")

    # Prominent Non-Approval Disclaimer Banner (parent2.md / parth2.md)
    st.warning(f"⚠️ **Legal & Compliance Notice:** {DISCLAIMER_TEXT}")

    prefix = get_active_prefix()

    # --------------------------------------------------------------------------
    # 1. Sidebar: Operator Identity & Environment
    # --------------------------------------------------------------------------
    st.sidebar.title("👤 Operator Identity")
    operator_name = st.sidebar.text_input(
        "Operator Name",
        value="Parth",
        help="Your name or team identifier recorded in CandidateDecision records.",
    )
    if not operator_name.strip():
        st.sidebar.error("⚠️ Operator name is required to submit candidate decisions.")

    st.sidebar.divider()
    st.sidebar.markdown(f"**Storage Prefix:** `{prefix or '(root / demo)'}`")
    if is_demo_prefix():
        st.sidebar.warning("⚠️ Connected to primary root storage.")
    else:
        st.sidebar.info(f"Sandbox prefix: `{prefix}`")

    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        clear_data_cache()
        st.rerun()

    # --------------------------------------------------------------------------
    # 2. Data Loading
    # --------------------------------------------------------------------------
    # Load Register
    try:
        register_sources = load_register()
    except Exception as exc:
        st.error(f"Error loading source register from config/sources.yaml: {exc}")
        register_sources = []

    # Load Candidates & Decisions
    try:
        candidates = settings_store.load_candidates()
    except Exception as exc:
        st.sidebar.warning(f"Note on candidate storage: {exc}")
        candidates = []

    try:
        decisions_list = settings_store.load_decisions()
        decisions_by_id = {d.candidate_id: d for d in decisions_list}
    except Exception:
        decisions_by_id = {}

    # --------------------------------------------------------------------------
    # 3. Main Navigation Tabs
    # --------------------------------------------------------------------------
    tab_candidates, tab_register = st.tabs([
        f"🔍 Discovered Candidates ({len(candidates)})",
        f"📋 Vetted Register ({len(register_sources)})",
    ])

    # ==========================================================================
    # TAB 1: Discovered Candidates & Decision Review
    # ==========================================================================
    with tab_candidates:
        st.subheader("Automated Source Candidates")
        st.markdown(
            "The Auto Scout Engine continuously identifies publisher domains through seed lists and "
            "outbound web links. Each candidate is vetted automatically against `robots.txt`, Terms of Use, "
            "and content relevance. Acceptance makes the source usable in subsequent runs."
        )

        # Filters for candidates
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            usable_filter = st.checkbox("Usable Candidates Only", value=False)
        with col_f2:
            status_filter = st.selectbox(
                "Vetting Status",
                ["all", "new", "auto_vetted", "needs_review", "rejected_by_rules"],
                index=0,
            )
        with col_f3:
            min_score = st.slider("Minimum Trust Score", min_value=0, max_value=100, value=0)
        with col_f4:
            search_query = st.text_input("Search Candidate", placeholder="Domain, company, region...")

        filtered_candidates = filter_candidates(
            candidates,
            usable_only=usable_filter,
            status_filter=status_filter,
            min_trust_score=min_score,
            query=search_query,
        )

        # Telemetry metrics
        usable_count = sum(1 for c in candidates if c.usable)
        accepted_count = sum(1 for d in decisions_by_id.values() if d.decision == "accepted")
        rejected_count = sum(1 for d in decisions_by_id.values() if d.decision == "rejected")

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Total Discovered", len(candidates))
        m_col2.metric("Meets Safety Rules (Usable)", usable_count)
        m_col3.metric("Accepted for Runs", accepted_count)
        m_col4.metric("Rejected", rejected_count)

        st.divider()

        if not candidates:
            st.info("💡 **No candidate sources found:** The Auto Scout Engine has not yet recorded candidate sources in `scout/candidates.json`. Run the pipeline with discovery enabled to populate candidates.")
        elif not filtered_candidates:
            st.info("No candidates match the specified filter criteria.")
        else:
            # Candidate Overview Table
            candidate_table_rows = prepare_candidate_rows(filtered_candidates, decisions_by_id)
            st.dataframe(
                candidate_table_rows,
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("---")
            st.subheader(f"Candidate Evaluation & Decisions ({len(filtered_candidates)} candidates)")

            for c in filtered_candidates:
                decision_obj = decisions_by_id.get(c.candidate_id)
                current_dec = decision_obj.decision.upper() if decision_obj else "PENDING REVIEW"
                dec_badge = "🟢 ACCEPTED" if current_dec == "ACCEPTED" else ("🔴 REJECTED" if current_dec == "REJECTED" else "🟡 PENDING")
                usable_badge = "✅ USABLE" if c.usable else "❌ UNUSABLE"

                with st.expander(f"[{dec_badge} • {usable_badge}] {c.name} ({c.domain}) — Trust Score: {c.trust_score}/100"):
                    # Metadata Grid
                    d_c1, d_c2, d_c3 = st.columns(3)
                    with d_c1:
                        st.markdown(f"**Candidate ID:** `{c.candidate_id}`")
                        st.markdown(f"**Domain:** `{c.domain}`")
                        st.markdown(f"**Publisher Type Guess:** `{c.type_guess}`")
                        st.markdown(f"**Target Region:** `{c.region}`")
                    with d_c2:
                        st.markdown(f"**Discovery Method:** `{c.discovered_via}`")
                        st.markdown(f"**Discovered From:** `{c.discovered_from or 'Seed list'}`")
                        st.markdown(f"**Discovered At:** `{c.discovered_at}`")
                        st.markdown(f"**Access Method:** `{c.access_method}`")
                    with d_c3:
                        st.markdown(f"**Robots.txt Status:** `{c.robots_status}`")
                        st.markdown(f"**Terms Status:** `{c.terms_status}`")
                        st.markdown(f"**Public & Logged-Out:** `{'Yes' if c.public_ok else 'Unknown/No'}`")
                        st.markdown(f"**Newest Item Date:** `{c.newest_item_date or 'Not stated'}`")

                    st.markdown("---")

                    # Vetting Evidence & Trust Score Breakdown
                    ev_c1, ev_c2 = st.columns(2)
                    with ev_c1:
                        st.markdown(f"**Trust Score Breakdown ({c.trust_score}/100):**")
                        if c.trust_reasons:
                            for reason in c.trust_reasons:
                                st.markdown(f"- {reason}")
                        else:
                            st.caption("No trust reasoning lines attached.")

                        if c.relevance_sample is not None:
                            st.markdown(f"**Relevance Sampling:** `{c.relevance_sample * 100:.1f}%` of sampled articles matched compressor keywords.")

                    with ev_c2:
                        st.markdown("**Terms of Use Audit Evidence:**")
                        if c.terms_evidence:
                            st.info(f"💬 *\"{c.terms_evidence}\"*")
                        else:
                            st.caption("No Terms of Use quotation stored.")

                        if c.terms_url:
                            st.markdown(f"🔗 [Inspect Source Terms Page]({c.terms_url})")
                        if c.notes:
                            st.caption(f"**Vetting Notes:** {c.notes}")

                    # Decision Status Display
                    st.markdown("---")
                    if decision_obj:
                        dec_color = "success" if decision_obj.decision == "accepted" else "error"
                        getattr(st, dec_color)(
                            f"**Current Status:** {decision_obj.decision.upper()} by `{decision_obj.decided_by}` "
                            f"on `{decision_obj.decided_at}`. Note: *{decision_obj.note or '(None)'}*"
                        )
                    else:
                        st.info("Current Status: **Awaiting Operator Decision**.")

                    # Decision Form
                    can_accept, accept_reason = can_accept_candidate(c)

                    dec_form_col1, dec_form_col2 = st.columns([2, 1])
                    with dec_form_col1:
                        dec_note = st.text_input(
                            "Decision Justification / Note",
                            value=decision_obj.note if decision_obj else "",
                            key=f"note_input_{c.candidate_id}",
                            placeholder="e.g. Verified trade publication focused on blowers and dryers.",
                        )

                    with dec_form_col2:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        b_col1, b_col2 = st.columns(2)

                        with b_col1:
                            # Accept button (STRICTLY DISABLED when usable is False)
                            if not can_accept:
                                st.button(
                                    "✅ Accept",
                                    key=f"accept_btn_{c.candidate_id}",
                                    disabled=True,
                                    help=accept_reason,
                                    use_container_width=True,
                                )
                            else:
                                if st.button(
                                    "✅ Accept",
                                    key=f"accept_btn_{c.candidate_id}",
                                    type="primary",
                                    use_container_width=True,
                                ):
                                    if not operator_name.strip():
                                        st.error("Please provide your Operator Name in the sidebar before accepting.")
                                    else:
                                        decision, err = build_candidate_decision(
                                            c, "accepted", operator_name, dec_note
                                        )
                                        if err:
                                            st.error(err)
                                        elif decision:
                                            settings_store.save_decision(decision)
                                            st.success(f"Candidate '{c.name}' accepted for future runs!")
                                            st.rerun()

                        with b_col2:
                            # Reject button (always available)
                            if st.button(
                                "❌ Reject",
                                key=f"reject_btn_{c.candidate_id}",
                                use_container_width=True,
                            ):
                                if not operator_name.strip():
                                    st.error("Please provide your Operator Name in the sidebar before rejecting.")
                                else:
                                    decision, err = build_candidate_decision(
                                        c, "rejected", operator_name, dec_note
                                    )
                                    if err:
                                        st.error(err)
                                    elif decision:
                                        settings_store.save_decision(decision)
                                        st.warning(f"Candidate '{c.name}' rejected.")
                                        st.rerun()

                    if not can_accept:
                        st.caption(f"🚫 {accept_reason}")

    # ==========================================================================
    # TAB 2: Vetted Source Register (Read-Only)
    # ==========================================================================
    with tab_register:
        st.subheader("Configured Source Register (config/sources.yaml)")
        st.markdown(
            "This table contains vetted industry publishers, competitor newsrooms, and government bodies "
            "established in the baseline configuration. The Compliance Gate executes sources marked `proposed` "
            "with `working` vetting status, and refuses all others."
        )

        if not register_sources:
            st.info("No sources loaded from register.")
        else:
            reg_rows = prepare_register_rows(register_sources)
            st.dataframe(
                reg_rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Notes": st.column_config.TextColumn("Vetting Evidence & Notes", width="large"),
                    "URL": st.column_config.LinkColumn("Source URL"),
                },
            )


if __name__ == "__main__":
    render_sources()
