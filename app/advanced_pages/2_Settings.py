"""Atlas Copco Market & Technology Scout — Settings Editor.

This screen allows operators to configure ScoutSettings, fine-tune relevance
thresholds, adjust discovery and switching policies, and maintain the competitor watchlist.
All settings are persisted to Databricks Volume (settings/scout_settings.json) and apply
strictly to the next pipeline run.
"""

from __future__ import annotations

from typing import Any
import streamlit as st

from atlas.models import EventType, Region, ScoutSettings, SourceType, WatchEntry
from atlas.scout import settings_store
from app.lib.data import get_active_prefix, is_demo_prefix
from app.lib.settings_ui import (
    SETTING_EXPLANATIONS,
    build_scout_settings,
    format_diff_summary,
    format_watchlist_for_editor,
    load_technology_labels,
    parse_watchlist_from_editor,
    settings_diff,
)

AVAILABLE_REGIONS: list[Region] = ["US", "CA", "MX"]
AVAILABLE_SOURCE_TYPES: list[SourceType] = ["competitor", "trade_news", "government"]
AVAILABLE_EVENT_TYPES: list[EventType] = [
    "product_launch",
    "acquisition",
    "investment_expansion",
    "partnership",
    "regulation_standard",
    "appointment",
    "award",
    "event",
    "other",
]


def _init_settings_state() -> None:
    """Initialize session state for settings form if not already present."""
    if "settings_loaded" not in st.session_state:
        try:
            defaults = settings_store.default_settings()
        except Exception:
            defaults = ScoutSettings()

        try:
            current = settings_store.load_settings()
        except Exception as exc:
            st.session_state["storage_warning"] = str(exc)
            current = defaults

        st.session_state["defaults"] = defaults
        st.session_state["current"] = current
        st.session_state["settings_loaded"] = True
        st.session_state["confirm_reset"] = False


def render_settings() -> None:
    st.set_page_config(
        page_title="Settings • Atlas Copco Scout",
        page_icon="⚙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("⚙️ Scout Engine & Filter Settings")
    st.caption("Configure the Auto Scout Engine, relevance filters, vetting thresholds, and followed competitor watchlists.")

    _init_settings_state()

    defaults: ScoutSettings = st.session_state["defaults"]
    current: ScoutSettings = st.session_state["current"]

    prefix = get_active_prefix()

    # --------------------------------------------------------------------------
    # 1. Sidebar Environment & Notice
    # --------------------------------------------------------------------------
    st.sidebar.title("⚙️ Storage Target")
    st.sidebar.markdown(f"**Storage Prefix:** `{prefix or '(root / demo)'}`")
    if is_demo_prefix():
        st.sidebar.warning("⚠️ **Live Demo Mode:** Connected to primary root storage.")
    else:
        st.sidebar.info(f"Sandbox prefix: `{prefix}`")

    st.sidebar.divider()
    st.sidebar.markdown("ℹ️ **Operational Policy:**")
    st.sidebar.caption("All settings are saved directly to Databricks cloud storage (`settings/scout_settings.json`).")
    st.sidebar.caption("Changes apply to the next pipeline run.")

    if st.session_state.get("storage_warning"):
        st.sidebar.warning(f"Storage note: {st.session_state['storage_warning']}")

    # --------------------------------------------------------------------------
    # 2. Main Form
    # --------------------------------------------------------------------------
    tech_labels = load_technology_labels()

    st.info("💡 **Changes apply to the next run.** Adjust parameters below and click **Save Settings** to update cloud configuration.")

    # Container for validation errors
    error_container = st.container()
    field_errors: dict[str, str] = {}

    # Reset confirmation banner
    if st.session_state.get("confirm_reset"):
        with st.container():
            st.warning("⚠️ **Confirm Reset:** Are you sure you want to discard current settings and reload factory defaults?")
            col_rc1, col_rc2 = st.columns(2)
            with col_rc1:
                if st.button("✅ Yes, Reset to Defaults", use_container_width=True):
                    try:
                        fresh_defaults = settings_store.default_settings()
                    except Exception:
                        fresh_defaults = ScoutSettings()
                    st.session_state["current"] = fresh_defaults
                    st.session_state["confirm_reset"] = False
                    st.success("Settings have been reset to factory defaults. Remember to click 'Save Settings' to apply to storage.")
                    st.rerun()
            with col_rc2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state["confirm_reset"] = False
                    st.rerun()

    # ==========================================================================
    # GROUP A: Scope
    # ==========================================================================
    st.subheader("1. Geographic & Industry Scope")
    st.caption("Define the market, regional boundaries, and corporate event types to scout.")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        scope_regions = st.multiselect(
            "Target Regions",
            options=AVAILABLE_REGIONS,
            default=current.regions,
            help="Select one or more geographic regions.",
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['regions']}")

        scope_events = st.multiselect(
            "Event Classifications",
            options=AVAILABLE_EVENT_TYPES,
            default=current.event_types,
            help="Filter for specific corporate announcements (product launches, investments, etc.).",
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['event_types']} *(Empty = all event types permitted)*")

    with col_s2:
        scope_techs = st.multiselect(
            "Compressor Technologies",
            options=tech_labels,
            default=[t for t in current.technologies if t in tech_labels],
            help="Select specific technology patterns from config/technologies.yaml.",
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['technologies']} *(Empty = all technologies permitted)*")

    st.divider()

    # ==========================================================================
    # GROUP B: Relevance Filter
    # ==========================================================================
    st.subheader("2. Relevance Filter Parameters")
    st.caption("Deterministic rules applied by the filter stage to verify relevance and timeliness.")

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        recent_months = st.slider(
            "Maximum Publication Age (Months)",
            min_value=1,
            max_value=60,
            value=current.recent_months,
            help="Articles with datelines older than this many months are dropped.",
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['recent_months']}")

        require_industrial = st.checkbox(
            "Require Explicit Industrial Context",
            value=current.require_industrial,
            help="When checked, drops consumer-grade articles lacking industrial compressor context.",
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['require_industrial']}")

    with col_r2:
        extra_keywords_text = st.text_area(
            "Additional Compressor Keywords (One per line)",
            value="\n".join(current.extra_compressor_keywords),
            placeholder="e.g.\nhydrogen compressor\noil-free blower\nvacuum pump",
            height=90,
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['extra_compressor_keywords']}")

        excluded_keywords_text = st.text_area(
            "Excluded Keywords (One per line)",
            value="\n".join(current.excluded_keywords),
            placeholder="e.g.\ntoy compressor\naquarium pump\nrefrigerator",
            height=90,
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['excluded_keywords']}")

    st.divider()

    # ==========================================================================
    # GROUP C: Sources
    # ==========================================================================
    st.subheader("3. Source Ingestion & Safety Thresholds")
    st.caption("Publisher categories, candidate vetting criteria, and per-source volume throttles.")

    col_src1, col_src2 = st.columns(2)
    with col_src1:
        source_types = st.multiselect(
            "Permitted Source Types",
            options=AVAILABLE_SOURCE_TYPES,
            default=current.source_types,
            help="Publisher categories permitted in collection runs.",
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['source_types']}")

        use_discovered = st.checkbox(
            "Include Auto-Vetted Discovered Sources",
            value=current.use_discovered_sources,
            help="Allow candidate sources discovered by the scout engine to be collected.",
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['use_discovered_sources']}")

    with col_src2:
        min_trust = st.slider(
            "Minimum Automated Trust Score",
            min_value=0,
            max_value=100,
            value=current.min_trust_score,
            help="Discovered candidate sources must meet or exceed this score.",
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['min_trust_score']}")

        max_items = st.number_input(
            "Max Items Collected per Source",
            min_value=1,
            max_value=100,
            value=current.max_items_per_source,
            step=1,
            help="Caps the number of items fetched from any individual source per run.",
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['max_items_per_source']}")

    st.divider()

    # ==========================================================================
    # GROUP D: Scout Engine
    # ==========================================================================
    st.subheader("4. Auto Scout & Switching Engine")
    st.caption("Autonomous source discovery and legal secondary-source coverage switching.")

    col_eng1, col_eng2 = st.columns(2)
    with col_eng1:
        discovery_on = st.checkbox(
            "Enable Automated Candidate Discovery",
            value=current.discovery_enabled,
            help="Scouts for new publisher domains via seed lists and compliant outbound links.",
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['discovery_enabled']}")

        switching_on = st.checkbox(
            "Enable Secondary Source Switching (Fallback)",
            value=current.fallback_enabled,
            help="When a primary source is refused, searches other allowed sources for competitor news.",
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['fallback_enabled']}")

    with col_eng2:
        fallback_max = st.number_input(
            "Max Fallback Items per Source",
            min_value=1,
            max_value=200,
            value=current.fallback_max_items_per_source,
            step=5,
            help="Maximum articles to collect from secondary sources during a switching event.",
        )
        st.caption(f"ℹ️ {SETTING_EXPLANATIONS['fallback_max_items_per_source']}")

    st.divider()

    # ==========================================================================
    # GROUP E: Watchlist
    # ==========================================================================
    st.subheader("5. Competitor & Technology Watchlist")
    st.caption(f"ℹ️ {SETTING_EXPLANATIONS['watchlist']}")
    st.markdown("Entries in this table are actively monitored. When a primary competitor site is blocked or unreachable, the scout gathers news about them through approved secondary trade journals.")

    # Format watchlist for table editor
    watchlist_editor_data = format_watchlist_for_editor(current.watchlist)
    
    edited_watchlist = st.data_editor(
        watchlist_editor_data,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "name": st.column_config.TextColumn("Entity / Product Name", required=True),
            "kind": st.column_config.SelectboxColumn("Classification", options=["company", "product", "technology"], required=True),
            "aliases": st.column_config.TextColumn("Known Aliases (Comma-separated)", help="e.g. Ingersoll-Rand, Ingersoll Rand Inc."),
            "follow_when_blocked": st.column_config.CheckboxColumn("Follow When Primary Refused", default=True),
        },
        key="watchlist_editor",
    )

    st.divider()

    # ==========================================================================
    # Build & Validate Provisional Settings
    # ==========================================================================
    form_payload = {
        "regions": scope_regions,
        "technologies": scope_techs,
        "event_types": scope_events,
        "recent_months": recent_months,
        "extra_compressor_keywords": extra_keywords_text,
        "excluded_keywords": excluded_keywords_text,
        "require_industrial": require_industrial,
        "source_types": source_types,
        "use_discovered_sources": use_discovered,
        "min_trust_score": min_trust,
        "max_items_per_source": max_items,
        "discovery_enabled": discovery_on,
        "fallback_enabled": switching_on,
        "fallback_max_items_per_source": fallback_max,
    }

    # Validate watchlist
    parsed_watchlist, watchlist_errors = parse_watchlist_from_editor(edited_watchlist)
    form_payload["watchlist"] = [w.model_dump() for w in parsed_watchlist]

    provisional_settings, build_errors = build_scout_settings(form_payload)

    # Combine errors
    all_validation_errors: list[str] = list(build_errors.values()) + watchlist_errors

    # --------------------------------------------------------------------------
    # 6. Diff Panel: Differences against Defaults
    # --------------------------------------------------------------------------
    st.subheader("🔍 Settings Differences from Defaults")
    if provisional_settings:
        diffs = settings_diff(provisional_settings, defaults)
        if diffs:
            formatted_diffs = format_diff_summary(diffs)
            with st.expander(f"⚠️ {len(formatted_diffs)} setting(s) modified from defaults", expanded=True):
                for item in formatted_diffs:
                    st.markdown(f"- {item['display']}")
        else:
            st.success("✅ All current settings exactly match the factory defaults.")
    else:
        st.warning("Cannot compute diff: please resolve the validation errors above.")

    st.divider()

    # --------------------------------------------------------------------------
    # 7. Action Buttons (Save & Reset)
    # --------------------------------------------------------------------------
    act_col1, act_col2 = st.columns([1, 1])

    with act_col1:
        if st.button("💾 Save Settings to Cloud Volume", type="primary", use_container_width=True):
            if all_validation_errors:
                with error_container:
                    st.error("❌ **Cannot save invalid settings:**")
                    for err in all_validation_errors:
                        st.markdown(f"- {err}")
            elif provisional_settings is not None:
                try:
                    settings_store.save_settings(provisional_settings)
                    st.session_state["current"] = provisional_settings
                    st.success("✅ **Settings saved successfully to Databricks Volume!** These parameters will govern the next run.")
                    st.rerun()
                except Exception as save_err:
                    st.error(f"Failed to persist settings to Volume: {save_err}")

    with act_col2:
        if st.button("🔄 Reset to Factory Defaults", use_container_width=True):
            st.session_state["confirm_reset"] = True
            st.rerun()


if __name__ == "__main__":
    render_settings()
