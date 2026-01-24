import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Support Copilot", layout="wide")

st.title("🧠 Support Copilot (MVP)")
st.caption("Ticket → Draft reply + citations (RAG) + next actions")

col1, col2 = st.columns([1, 1])

with col1:
    ticket_text = st.text_area("Ticket text", height=260, placeholder="Paste a customer message here...")
    language = st.selectbox("Language", ["en", "ru", "he"], index=0)
    category = st.text_input("Category (optional)", value="")
    if st.button("Generate", type="primary", disabled=(len(ticket_text.strip()) < 3)):
        with st.spinner("Thinking..."):
            r = requests.post(
                f"{API_URL}/suggest-reply",
                json={"ticket_text": ticket_text, "language": language, "category": category or None},
                timeout=60,
            )
        st.session_state["last_ticket"] = ticket_text
        st.session_state["resp"] = r.json()

with col2:
    resp = st.session_state.get("resp")
    if resp:
        st.subheader("Draft reply")
        st.write(resp.get("draft_reply", ""))

        st.subheader("Citations")
        for c in resp.get("citations", []):
            st.markdown(f"- **{c.get('title','Policy')}**")
            if c.get("url"):
                st.markdown(f"  - {c['url']}")
            st.markdown(f"  - _{c.get('snippet','')}_")

        st.subheader("Next actions")
        for a in resp.get("next_actions", []):
            st.markdown(f"- {a}")

        st.subheader("Confidence")
        st.progress(float(resp.get("confidence", 0.0)))

        st.subheader("Feedback")
        fb_col1, fb_col2 = st.columns([1, 3])
        with fb_col1:
            up = st.button("👍 Helpful")
            down = st.button("👎 Not helpful")
        with fb_col2:
            comment = st.text_input("Comment (optional)", value="")

        if up or down:
            requests.post(
                f"{API_URL}/feedback",
                json={
                    "ticket_text": st.session_state.get("last_ticket", "")[:4000],
                    "helpful": bool(up),
                    "comment": comment or None,
                    "model": resp.get("debug", {}).get("model"),
                },
                timeout=30,
            )
            st.success("Saved feedback ✅")
