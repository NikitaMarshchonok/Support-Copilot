import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Support Copilot", layout="wide")

st.title("🧠 Support Copilot (MVP)")
st.caption("Ticket → Draft reply + citations (RAG) + next actions")

DEMO_SCENARIOS = {
    "Refund within policy": {
        "ticket_text": (
            "Hi, I booked a stay for March 12–15 but had to cancel today. "
            "Can I get a full refund?\nReservation: 884512"
        ),
        "language": "en",
        "category": "refunds",
    },
    "Price mismatch claim": {
        "ticket_text": (
            "I booked this apartment yesterday, but now I see a lower price for the same dates. "
            "Can you match it?\nBooking ID: 992341"
        ),
        "language": "en",
        "category": "payments",
    },
    "Date change request": {
        "ticket_text": (
            "My flight was moved. I need to change my stay from Apr 6–9 to Apr 8–11. "
            "Is that possible?\nReservation 553210."
        ),
        "language": "en",
        "category": "policies",
    },
}

col1, col2 = st.columns([1, 1])

with col1:
    demo_name = st.selectbox("Demo scenarios", ["(none)"] + list(DEMO_SCENARIOS.keys()))
    if st.button("Load scenario", disabled=(demo_name == "(none)")):
        demo = DEMO_SCENARIOS[demo_name]
        st.session_state["ticket_text"] = demo["ticket_text"]
        st.session_state["language"] = demo["language"]
        st.session_state["category"] = demo["category"]

    ticket_text = st.text_area(
        "Ticket text",
        key="ticket_text",
        height=260,
        placeholder="Paste a customer message here...",
    )
    language = st.selectbox("Language", ["en", "ru", "he"], index=0, key="language")
    category = st.text_input("Category (optional)", value="", key="category")
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
