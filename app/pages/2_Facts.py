"""Facts: mark each gathered fact important or not important. Saving reruns the system."""
from __future__ import annotations

import streamlit as st

from app.lib.data import latest_run_id, load_envelope
from app.lib.simple_ui import run_panel, trigger_rerun
from atlas import review

st.set_page_config(page_title="Facts", page_icon="✅", layout="wide")
st.title("✅ Facts")
st.caption("Mark each fact **Important** or **Not important**. Not important facts are left out of the next run and "
           "of the report. Press Save when you are done.")

run_id = latest_run_id()
if run_id is None:
    st.info("No facts yet. Go to the Dashboard and press Done to run.")
    st.stop()
try:
    envelope = load_envelope(run_id)
    decisions = review.load_fact_decisions()
except Exception as exc:
    st.error(f"Could not read the facts: {exc}")
    st.stop()

run_panel()
items = [i for i in sorted(envelope.items, key=lambda i: i.published_at or "", reverse=True)
         if not (i.company or "").lower().startswith("atlas copco") and i.key_facts]
# Facts already marked not important are not in a new run's output, so show them from the run being viewed.
LABELS = {"approved": "Important", "denied": "Not important", "": "Not decided"}
st.write(f"{len(items)} facts from run `{run_id}`.")

with st.form("facts"):
    choice: dict[str, str] = {}
    for item in items[:60]:
        current = decisions.get(item.id, "")
        c1, c2 = st.columns([4, 2])
        c1.markdown(f"**{item.company or 'Unknown company'}** · {(item.event_type or 'other').replace('_', ' ')} · "
                    f"{item.published_at or 'date not stated'}  \n{item.key_facts[0]}  \n"
                    f"[{item.source_name}]({item.source_url})")
        picked = c2.radio("Decision", list(LABELS), index=list(LABELS).index(current), key=f"d_{item.id}",
                          format_func=LABELS.get, horizontal=True, label_visibility="collapsed")
        choice[item.id] = picked
        st.divider()
    saved = st.form_submit_button("💾 Save", type="primary")

if saved:
    updated = dict(decisions)
    for item_id, value in choice.items():
        if value:
            updated[item_id] = value
        else:
            updated.pop(item_id, None)
    review.save_fact_decisions(updated)
    st.success("Saved.")
    trigger_rerun("your fact decisions")
    st.rerun()
if len(items) > 60:
    st.caption("Showing the 60 newest facts.")
