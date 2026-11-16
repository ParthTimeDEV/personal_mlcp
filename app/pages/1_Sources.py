"""Sources: every source in three lists: confirmed, still to confirm, blocked. Confirming reruns the system."""
from __future__ import annotations

import streamlit as st

from app.lib.simple import classify_sources
from app.lib.simple_ui import run_panel, trigger_rerun
from atlas import review
from atlas.compliance import load_register
from atlas.scout import settings_store

st.set_page_config(page_title="Sources", layout="wide")
st.title("Sources")
st.caption("Where our facts come from. Confirm the ones you are happy with. Blocked ones are shown with the reason; "
           "we never read them.")
st.info("Confirming here records your team's decision. It is not an approval by Atlas Copco.")

try:
    confirmations = review.load_source_confirmations()
    candidates = settings_store.load_candidates()
    rejected = {d.candidate_id for d in settings_store.load_decisions() if d.decision == "rejected"}
    groups = classify_sources(load_register(), candidates, confirmations, rejected)
except Exception as exc:
    st.error(f"Could not read the sources: {exc}")
    st.stop()

run_panel()
tab_conf, tab_todo, tab_block = st.tabs([
    f"Confirmed ({len(groups['confirmed'])})", f"To confirm ({len(groups['to_confirm'])})",
    f"Blocked ({len(groups['blocked'])})"])


def show(rows: list[dict], button: str | None, new_value: str | None) -> None:
    if not rows:
        st.write("Nothing here.")
    for row in rows:
        c1, c2 = st.columns([5, 1])
        badge = "found by the scout" if row["kind"] == "discovered" else "on our list"
        score = f" · trust score {row['score']}" if row["score"] is not None else ""
        c1.markdown(f"**{row['name']}** · {row['type'].replace('_', ' ')} · {badge}{score}  \n{row['url']}")
        if row["detail"]:
            c1.caption(row["detail"][:260])
        if button and c2.button(button, key=f"{new_value}_{row['id']}"):
            updated = dict(confirmations)
            updated[row["id"]] = new_value
            review.save_source_confirmations(updated)
            st.success(f"Saved: {row['name']}")
            trigger_rerun("a source decision")
            st.rerun()


with tab_conf:
    show(groups["confirmed"], "Undo", "pending")
with tab_todo:
    show(groups["to_confirm"], "Confirm", "confirmed")
with tab_block:
    show(groups["blocked"], None, None)
