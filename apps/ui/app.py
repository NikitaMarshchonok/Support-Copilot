import json
import os
import textwrap
from io import BytesIO
from pathlib import Path

import requests
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

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


def _build_export_markdown(resp: dict) -> str:
    citations = resp.get("citations", [])
    lines = [
        "# Support Copilot Reply",
        "",
        "## Draft reply",
        resp.get("draft_reply", ""),
        "",
        "## Next actions",
    ]
    for a in resp.get("next_actions", []):
        lines.append(f"- {a}")
    lines += ["", "## Clarifying questions"]
    for q in resp.get("clarifying_questions", []):
        lines.append(f"- {q}")
    lines += ["", "## Citations"]
    for c in citations:
        title = c.get("title", "Policy")
        url = c.get("url")
        snippet = c.get("snippet", "")
        lines.append(f"- **{title}**")
        if url:
            lines.append(f"  - {url}")
        if snippet:
            lines.append(f"  - _{snippet}_")
    return "\n".join(lines).strip() + "\n"


def _build_export_pdf(markdown_text: str) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    x = 72
    y = height - 72
    for raw_line in markdown_text.splitlines():
        line = raw_line.replace("#", "").strip()
        wrapped = textwrap.wrap(line, width=95) or [""]
        for wline in wrapped:
            pdf.drawString(x, y, wline)
            y -= 14
            if y < 72:
                pdf.showPage()
                y = height - 72
    pdf.save()
    return buffer.getvalue()


def _read_history(limit: int = 8) -> list[dict]:
    path = Path("data/history/history.jsonl")
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows

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

        st.subheader("Export")
        export_md = _build_export_markdown(resp)
        st.download_button(
            "Download Markdown",
            data=export_md,
            file_name="support_copilot_reply.md",
            mime="text/markdown",
        )
        st.download_button(
            "Download PDF",
            data=_build_export_pdf(export_md),
            file_name="support_copilot_reply.pdf",
            mime="application/pdf",
        )

        with st.expander("Session history"):
            history = _read_history()
            if not history:
                st.write("No history yet.")
            for item in history[::-1]:
                st.markdown(f"**{item.get('ts','')}** — {item.get('provider','')}")
                st.markdown(f"- Ticket: {item.get('ticket_text','')[:200]}")
                st.markdown(f"- Draft: {item.get('draft_reply','')[:200]}")
