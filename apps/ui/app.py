import json
import os
import textwrap
from pathlib import Path

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
    def esc(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    lines: list[str] = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.replace("#", "").strip()
        wrapped = textwrap.wrap(line, width=95) or [""]
        lines.extend(wrapped)

    lines_per_page = 48
    pages = [lines[i : i + lines_per_page] for i in range(0, len(lines), lines_per_page)] or [[]]

    obj: dict[int, bytes] = {}
    obj[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    page_ids: list[int] = []
    for i, page_lines in enumerate(pages):
        content_id = 4 + i * 2
        page_id = 5 + i * 2

        content = ["BT", "/F1 11 Tf", "72 720 Td", "12 TL"]
        for line in page_lines:
            content.append(f"({esc(line)}) Tj")
            content.append("T*")
        content.append("ET")
        stream = "\n".join(content)
        obj[content_id] = (
            f"<< /Length {len(stream.encode('utf-8'))} >>\nstream\n{stream}\nendstream".encode("utf-8")
        )
        obj[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("utf-8")
        page_ids.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    obj[2] = f"<< /Type /Pages /Kids [ {kids} ] /Count {len(page_ids)} >>".encode("utf-8")
    obj[1] = b"<< /Type /Catalog /Pages 2 0 R >>"

    max_id = max(obj.keys())
    xref_positions: list[int] = []
    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")
    for i in range(1, max_id + 1):
        xref_positions.append(len(pdf))
        pdf.extend(f"{i} 0 obj\n".encode("utf-8"))
        pdf.extend(obj.get(i, b"<<>>"))
        pdf.extend(b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {max_id + 1}\n".encode("utf-8"))
    pdf.extend(b"0000000000 65535 f \n")
    for pos in xref_positions:
        pdf.extend(f"{pos:010d} 00000 n \n".encode("utf-8"))
    pdf.extend(
        f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode("utf-8")
    )
    return bytes(pdf)


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
    demo_mode = st.checkbox("Demo mode (auto-fill + auto-generate)", value=False)
    demo_name = st.selectbox("Demo scenarios", ["(none)"] + list(DEMO_SCENARIOS.keys()))
    if st.button("Load scenario", disabled=(demo_name == "(none)")):
        demo = DEMO_SCENARIOS[demo_name]
        st.session_state["ticket_text"] = demo["ticket_text"]
        st.session_state["language"] = demo["language"]
        st.session_state["category"] = demo["category"]
        if demo_mode:
            st.session_state["auto_generate"] = True

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

    if st.session_state.pop("auto_generate", False) and len(ticket_text.strip()) >= 3:
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
            else:
                rows = [
                    {
                        "ts": item.get("ts", ""),
                        "provider": item.get("provider", ""),
                        "ticket": (item.get("ticket_text", "")[:120]),
                        "draft": (item.get("draft_reply", "")[:120]),
                    }
                    for item in history[::-1]
                ]
                st.dataframe(rows, use_container_width=True, hide_index=True)
