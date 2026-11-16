"""Atlas Copco Market & Technology Scout — Dashboard.

This screen provides an operational overview of pipeline runs, source compliance,
filterable facts & claims, multi-source stories, trend charts, and in-memory data exports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import streamlit as st

from atlas.models import Item, OutputEnvelope, RunLog
from app.lib.data import (
    StorageAccessError,
    clear_data_cache,
    get_active_prefix,
    is_demo_prefix,
    latest_run_id,
    list_run_ids,
    load_clean_items,
    load_envelope,
    load_log,
)
from app.lib.dashboard import (
    compute_run_metrics,
    get_other_story_items,
    prepare_chart_data,
    prepare_items_csv,
    prepare_sources_summary,
    prepare_stories_view,
)
from app.lib.filters import (
    REASON_LABELS,
    ItemFilters,
    explain_reasons,
    filter_items,
    parse_reason_label,
)

FIXTURE_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "sample_output.json"


def _load_synthetic_fixture() -> OutputEnvelope:
    """Load the verified synthetic sample fixture for development and offline demo."""
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return OutputEnvelope.model_validate(data)


def render_dashboard() -> None:
    st.set_page_config(
        page_title="Dashboard • Atlas Copco Scout",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("📊 Market & Technology Intelligence Dashboard")
    st.caption("Operational review of scout runs, source compliance, verified facts & claims, and corporate developments.")

    prefix = get_active_prefix()

    # --------------------------------------------------------------------------
    # 1. Sidebar: Run Selection & Environment
    # --------------------------------------------------------------------------
    st.sidebar.title("⚙️ Run & Filters")
    st.sidebar.markdown(f"**Storage Prefix:** `{prefix or '(root / demo)'}`")
    if is_demo_prefix():
        st.sidebar.warning("⚠️ **Live Demo Mode:** Connected to primary root storage.")
    else:
        st.sidebar.info(f"Sandbox prefix: `{prefix}`")

    if st.sidebar.button("🔄 Refresh Storage Data", use_container_width=True):
        clear_data_cache()
        st.rerun()

    # Discover available runs
    try:
        volume_run_ids = list_run_ids()
    except StorageAccessError as err:
        st.sidebar.error(f"Volume connection error: {err}")
        volume_run_ids = []

    # Build run choices
    run_options: list[str] = []
    if volume_run_ids:
        run_options.extend(volume_run_ids)
    run_options.append("Sample Fixture (Synthetic Offline Demo)")

    selected_run_option = st.sidebar.selectbox(
        "Select Pipeline Run",
        run_options,
        index=0,
        help="Select a cloud pipeline run from Databricks, or load the offline synthetic fixture.",
    )

    # --------------------------------------------------------------------------
    # 2. Data Ingestion for Selected Run
    # --------------------------------------------------------------------------
    is_synthetic = selected_run_option.startswith("Sample Fixture")
    envelope: OutputEnvelope | None = None
    run_log: RunLog | None = None
    all_raw_items: list[dict] = []

    if is_synthetic:
        st.info("ℹ️ **Synthetic Fixture Active:** Viewing offline sample fixture (`tests/fixtures/sample_output.json`).")
        try:
            envelope = _load_synthetic_fixture()
            all_raw_items = [it.model_dump(mode="json") for it in envelope.items]
        except Exception as exc:
            st.error(f"Failed to load synthetic fixture: {exc}")
            return
    else:
        run_id = selected_run_option
        try:
            with st.spinner(f"Loading run {run_id} from Databricks Volume..."):
                envelope = load_envelope(run_id)
                run_log = load_log(run_id)
                clean_items = load_clean_items(run_id)

            if clean_items:
                all_raw_items = [it.model_dump(mode="json") for it in clean_items]
            else:
                all_raw_items = [it.model_dump(mode="json") for it in envelope.items]
        except StorageAccessError as sa_err:
            st.error(f"**Storage Access Error:** Unable to retrieve run `{run_id}` from Databricks Volume.")
            st.caption(f"Technical details: {sa_err}")
            st.info("💡 You can switch to **'Sample Fixture (Synthetic Offline Demo)'** in the sidebar to browse sample intelligence.")
            return
        except Exception as exc:
            st.error(f"**Error Loading Run Data:** {exc}")
            return

    if not envelope:
        st.warning("No data found for the selected run.")
        return

    # Compute metrics
    metrics = compute_run_metrics(envelope, run_log, all_raw_items)

    # Map items by ID for story lookups
    items_by_id: dict[str, dict] = {it.get("id", ""): it for it in all_raw_items if it.get("id")}

    # --------------------------------------------------------------------------
    # 3. Sidebar Filter Controls (Task P2 - All Combinable)
    # --------------------------------------------------------------------------
    st.sidebar.divider()
    st.sidebar.subheader("Filter Intelligence")

    # Extract distinct values from available items
    available_sources = sorted(list({it.get("source_id") for it in all_raw_items if it.get("source_id")}))
    available_companies = sorted(list({it.get("company") for it in all_raw_items if it.get("company")}))
    available_techs = sorted(list({it.get("technology") for it in all_raw_items if it.get("technology")}))
    available_events = sorted(list({it.get("event_type") for it in all_raw_items if it.get("event_type")}))
    available_regions = sorted(list({it.get("region") for it in all_raw_items if it.get("region")}))
    available_stories = sorted(list({it.get("story_id") for it in all_raw_items if it.get("story_id")}))

    filter_source = st.sidebar.selectbox("Source ID", ["All Sources"] + available_sources)
    filter_source_type = st.sidebar.selectbox("Source Type", ["All Types", "competitor", "trade_news", "government"])
    filter_label = st.sidebar.selectbox("Fact vs Claim", ["All Labels", "fact", "claim"])
    filter_passed_option = st.sidebar.selectbox("Filter Status", ["All Items", "Passed Only", "Dropped Only"])
    filter_company = st.sidebar.selectbox("Company", ["All Companies"] + available_companies)
    filter_tech = st.sidebar.selectbox("Technology", ["All Technologies"] + available_techs)
    filter_event = st.sidebar.selectbox("Event Type", ["All Events"] + available_events)
    filter_region = st.sidebar.selectbox("Region", ["All Regions"] + available_regions)

    # Date range filters
    col_d1, col_d2 = st.sidebar.columns(2)
    with col_d1:
        date_from_input = st.date_input("From Date", value=None)
    with col_d2:
        date_to_input = st.date_input("To Date", value=None)

    filter_story = st.sidebar.selectbox("Story ID", ["All Stories"] + available_stories)
    filter_fallback = st.sidebar.checkbox("Via Fallback Only", value=False)
    filter_query = st.sidebar.text_input("Search Title & Facts", value="", placeholder="e.g. oil-free, acquisition...")

    st.sidebar.divider()
    sort_by_label = st.sidebar.selectbox("Sort By", ["Publication Date", "Company Name", "Source ID"])
    sort_order = st.sidebar.radio("Sort Order", ["Descending", "Ascending"], horizontal=True)

    sort_field_map = {
        "Publication Date": "date",
        "Company Name": "company",
        "Source ID": "source",
    }

    # Construct ItemFilters object
    filter_criteria = ItemFilters(
        source_id=filter_source if filter_source != "All Sources" else None,
        source_type=filter_source_type if filter_source_type != "All Types" else None,
        label=filter_label if filter_label != "All Labels" else None,
        passed=True if filter_passed_option == "Passed Only" else (False if filter_passed_option == "Dropped Only" else None),
        company=filter_company if filter_company != "All Companies" else None,
        technology=filter_tech if filter_tech != "All Technologies" else None,
        event_type=filter_event if filter_event != "All Events" else None,
        region=filter_region if filter_region != "All Regions" else None,
        date_from=date_from_input,
        date_to=date_to_input,
        story_id=filter_story if filter_story != "All Stories" else None,
        via_fallback_only=filter_fallback,
        query=filter_query if filter_query.strip() else None,
        sort_by=sort_field_map[sort_by_label],
        sort_desc=(sort_order == "Descending"),
    )

    # Apply pure filter
    filtered_items = filter_items(all_raw_items, filter_criteria)

    # --------------------------------------------------------------------------
    # 4. Main Tabs Navigation
    # --------------------------------------------------------------------------
    tab_overview, tab_browser, tab_stories, tab_charts, tab_exports = st.tabs([
        "📋 Overview & Sources",
        f"📰 Item Browser ({len(filtered_items)})",
        f"🔗 Stories ({len(envelope.stories or [])})",
        "📈 Trends & Analytics",
        "💾 In-Memory Export",
    ])

    # ==========================================================================
    # TAB 1: Overview & Sources Table
    # ==========================================================================
    with tab_overview:
        st.subheader("Run Overview Telemetry")
        
        # Top Metrics Grid
        m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)
        m_col1.metric("Items Collected", metrics["collected_count"])
        m_col2.metric("Passed Filter", metrics["passed_count"])
        m_col3.metric("Dropped Items", metrics["dropped_count"])
        m_col4.metric("Story Clusters", metrics["stories_count"])
        m_col5.metric("Refused Sources", metrics["refused_sources_count"])
        m_col6.metric("Fallback Items", metrics["fallback_items_count"])

        # Run Metadata Banner
        meta_col1, meta_col2, meta_col3 = st.columns(3)
        with meta_col1:
            st.markdown(f"**Run Identifier:** `{metrics['run_id']}`")
            st.markdown(f"**Timestamp:** `{metrics['generated_at']}`")
        with meta_col2:
            st.markdown(f"**Scope Technology:** `{metrics['scope_tech']}`")
            st.markdown(f"**Scope Region:** `{metrics['scope_region']}`")
        with meta_col3:
            st.markdown(f"**Candidates Considered:** `{metrics['candidates_considered']}`")
            if metrics["settings_used"]:
                recent_m = metrics["settings_used"].get("recent_months", 12)
                st.markdown(f"**Recency Window:** `{recent_m} months`")

        st.divider()

        # Section B: Source Summary Table
        st.subheader("Source Compliance & Collection Summary")
        sources_summary_data = prepare_sources_summary(envelope.sources or [])
        
        if not sources_summary_data:
            st.info("No source summary records found for this run.")
        else:
            # Display formatted rows
            summary_table_rows = []
            for row in sources_summary_data:
                status_icon = "🟢" if row["status"] in ("working", "approved") else ("🔴" if row["is_refused"] else "🟡")
                summary_table_rows.append({
                    "Source Name": row["name"],
                    "Source ID": row["source_id"],
                    "Kind": row["kind_label"],
                    "Status": f"{status_icon} {row['status']}",
                    "Collected": row["items_collected"],
                    "Passed": row["items_passed"],
                    "Notes": row["note"],
                })

            st.dataframe(
                summary_table_rows,
                use_container_width=True,
                column_config={
                    "Kind": st.column_config.TextColumn("Source Classification"),
                    "Notes": st.column_config.TextColumn("Compliance & Refusal Notes", width="large"),
                },
                hide_index=True,
            )

    # ==========================================================================
    # TAB 2: Item Browser & Expandable Details
    # ==========================================================================
    with tab_browser:
        st.subheader(f"Extracted Market Intelligence ({len(filtered_items)} items displayed)")
        
        if not filtered_items:
            st.info("No intelligence items match your current filter selections. Adjust the sidebar filters to broaden results.")
        else:
            for idx, item in enumerate(filtered_items):
                filter_meta = item.get("filter") or {}
                item_passed = filter_meta.get("passed", True) if isinstance(filter_meta, dict) else True
                reasons = filter_meta.get("reasons", []) if isinstance(filter_meta, dict) else []

                # Badges & Headline
                status_badge = "🟢 PASSED" if item_passed else "🔴 DROPPED"
                label_badge = "📋 FACT" if item.get("label") == "fact" else "💬 CLAIM"
                company_badge = item.get("company") or "Unknown Company"
                title_text = item.get("title") or "(Untitled Intelligence Record)"
                pub_date = item.get("published_at") or "Undated"

                with st.expander(f"{status_badge} • [{label_badge}] {company_badge} — {title_text} ({pub_date})"):
                    # Core Details Grid
                    d_col1, d_col2, d_col3 = st.columns(3)
                    with d_col1:
                        st.markdown(f"**Company:** `{item.get('company') or 'Not stated'}`")
                        st.markdown(f"**Product:** `{item.get('product') or 'Not stated'}`")
                        st.markdown(f"**Technology:** `{item.get('technology') or 'Not specified'}`")
                    with d_col2:
                        st.markdown(f"**Event Type:** `{item.get('event_type') or 'General'}`")
                        st.markdown(f"**Region:** `{item.get('region') or 'Unspecified'}`")
                        st.markdown(f"**Publication Date:** `{pub_date}`")
                    with d_col3:
                        st.markdown(f"**Source:** `{item.get('source_name')} ({item.get('source_id')})`")
                        st.markdown(f"**Classification:** `{item.get('label')}`")
                        if item.get("source_url"):
                            st.markdown(f"🔗 [Open Original Web Article]({item.get('source_url')})")

                    # Key Facts
                    st.markdown("**Key Extracted Facts:**")
                    facts = item.get("key_facts") or []
                    if facts:
                        for fact in facts:
                            fact_text = fact if isinstance(fact, str) else fact.get("text", "")
                            st.markdown(f"- {fact_text}")
                    else:
                        st.caption("No key facts extracted.")

                    # Fallback and Watchlist Information
                    if item.get("via_fallback"):
                        st.warning(
                            f"🔄 **Via Fallback Substitution:** Collected from allowed secondary source `{item.get('source_id')}` "
                            f"standing in for refused primary source `{item.get('fallback_for')}`."
                        )

                    if item.get("watch_matches"):
                        st.info(f"👀 **Followed Competitor Watchlist Matches:** {', '.join(item['watch_matches'])}")

                    # Filter Checks & Reason Explanations
                    st.markdown("---")
                    st.markdown("**Automated Filter Verdict & Reason Breakdown:**")
                    
                    if filter_meta:
                        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
                        f_col1.markdown(f"Compressor-related: {'✅ Yes' if filter_meta.get('compressor_related') else '❌ No'}")
                        f_col2.markdown(f"North America: {'✅ Yes' if filter_meta.get('north_america') else '❌ No'}")
                        f_col3.markdown(f"Credible Source: {'✅ Yes' if filter_meta.get('credible_source') else '❌ No'}")
                        f_col4.markdown(f"Recency: {'✅ Yes' if filter_meta.get('recent') else '❌ No'}")

                        if not item_passed:
                            st.error("**Why was this item dropped?**")
                            plain_reasons = explain_reasons(reasons)
                            for pr in plain_reasons:
                                st.markdown(f"• **{pr}**")
                    else:
                        st.caption("Filter metadata not attached.")

                    # Story Connection
                    story_id = item.get("story_id")
                    if story_id:
                        st.markdown("---")
                        st.markdown(f"**Story Cluster Association:** `{story_id}`")
                        other_items = get_other_story_items(item, all_raw_items)
                        if other_items:
                            st.markdown(f"Other items in this story cluster ({len(other_items)}):")
                            for other in other_items:
                                other_src = other.get("source_name") or other.get("source_id")
                                other_title = other.get("title") or "Untitled"
                                st.markdown(f"- *{other_src}*: **{other_title}** ({other.get('published_at') or 'Undated'})")
                        else:
                            st.caption("No other items linked in this story cluster.")

    # ==========================================================================
    # TAB 3: Story Clusters
    # ==========================================================================
    with tab_stories:
        st.subheader("Multi-Source Intelligence Stories")
        st.caption("Events covered across multiple independent sources represent verified market signals.")

        stories_data = prepare_stories_view(envelope.stories or [], items_by_id)

        if not stories_data:
            st.info("No story clusters identified in this run.")
        else:
            for story in stories_data:
                is_multi = story["is_multi_source"]
                multi_badge = "🌟 MULTI-SOURCE" if is_multi else "SINGLE SOURCE"
                source_count_label = f"{story['source_count']} source(s)"
                
                with st.expander(f"[{multi_badge} • {source_count_label}] {story['headline']}"):
                    s_c1, s_c2, s_c3 = st.columns(3)
                    with s_c1:
                        st.markdown(f"**Company:** `{story['company']}`")
                        st.markdown(f"**Product:** `{story['product']}`")
                    with s_c2:
                        st.markdown(f"**Event Type:** `{story['event_type']}`")
                        st.markdown(f"**Timeline:** `{story['first_published']}` to `{story['last_published']}`")
                    with s_c3:
                        st.markdown(f"**Participating Sources:** `{', '.join(story['source_ids'])}`")
                        if story["via_fallback_count"] > 0:
                            st.markdown(f"**Fallback Coverage:** `{story['via_fallback_count']} item(s)`")

                    st.markdown("**Articles Linked in this Story:**")
                    if story["items"]:
                        for s_item in story["items"]:
                            s_title = s_item.get("title") or "Untitled article"
                            s_src = s_item.get("source_name") or s_item.get("source_id")
                            s_date = s_item.get("published_at") or "Undated"
                            s_url = s_item.get("source_url")
                            link_str = f" • [Link]({s_url})" if s_url else ""
                            st.markdown(f"- **{s_title}** ({s_src}, {s_date}){link_str}")
                    else:
                        st.caption(f"{len(story['item_ids'])} linked item IDs: {', '.join(story['item_ids'])}")

    # ==========================================================================
    # TAB 4: Trends & Analytics (Streamlit Built-in Charts)
    # ==========================================================================
    with tab_charts:
        st.subheader("Market & Technology Scouting Analytics")

        if not filtered_items:
            st.info("No items match the current filter selection to render analytics.")
        else:
            chart_data = prepare_chart_data(filtered_items)

            ch_col1, ch_col2 = st.columns(2)
            with ch_col1:
                st.markdown("**Items per Source**")
                if chart_data["items_per_source"]:
                    st.bar_chart(chart_data["items_per_source"])
                else:
                    st.caption("No source data.")

            with ch_col2:
                st.markdown("**Top 10 Mentioned Companies**")
                if chart_data["top_companies"]:
                    st.bar_chart(chart_data["top_companies"])
                else:
                    st.caption("No company data available.")

            ch_col3, ch_col4 = st.columns(2)
            with ch_col3:
                st.markdown("**Items by Event Type**")
                if chart_data["items_per_event_type"]:
                    st.bar_chart(chart_data["items_per_event_type"])
                else:
                    st.caption("No event type data.")

            with ch_col4:
                st.markdown("**Publication Timeline (Items per Month)**")
                if chart_data["items_per_month"]:
                    st.bar_chart(chart_data["items_per_month"])
                else:
                    st.caption("No publication date data.")

    # ==========================================================================
    # TAB 5: In-Memory Export (Task P2 - Zero Local Disk Writes)
    # ==========================================================================
    with tab_exports:
        st.subheader("Export Filtered Intelligence (In-Memory Streaming)")
        st.markdown(
            "Download currently filtered intelligence records. In strict compliance with zero-local-data "
            "security standards, files are streamed directly in-memory and never cached on local disk."
        )

        st.markdown(f"**Records Prepared for Download:** `{len(filtered_items)}` items.")

        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            json_data = json.dumps(filtered_items, indent=2)
            st.download_button(
                label="📥 Download Visible Items as JSON",
                data=json_data,
                file_name=f"atlas_scout_items_{metrics['run_id']}.json",
                mime="application/json",
                use_container_width=True,
            )

        with exp_col2:
            csv_data = prepare_items_csv(filtered_items)
            st.download_button(
                label="📥 Download Visible Items as CSV",
                data=csv_data,
                file_name=f"atlas_scout_items_{metrics['run_id']}.csv",
                mime="text/csv",
                use_container_width=True,
            )


if __name__ == "__main__":
    render_dashboard()
