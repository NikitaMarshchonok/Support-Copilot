# Support Copilot Demo Pack

## 1) Demo scenarios (3)

### Scenario A — Refund within policy
Ticket text:
"""
Hi, I booked a stay for March 12–15 but had to cancel today. Can I get a full refund?
Reservation: 884512
"""

Expected reply (agent draft):
"""
Hi there — thanks for the details. I can see the reservation was canceled within the eligible window, so a full refund applies. I have submitted the refund and you’ll receive a confirmation email shortly. Depending on your bank, the credit typically appears within 5–10 business days.

If you have any other questions about the refund timeline, I’m here to help.
"""

Expected next actions:
- Confirm cancellation timestamp in policy window
- Trigger refund workflow in billing system

Expected clarifying questions:
- None (only if missing reservation ID)

Expected citations:
- Cancellation policy: refunds within eligible window
- Refund processing timelines


### Scenario B — Price mismatch claim
Ticket text:
"""
I booked this apartment yesterday, but now I see a lower price for the same dates. 
Can you match it? Booking ID: 992341
"""

Expected reply (agent draft):
"""
Thanks for flagging this. I can help check a price mismatch, but I’ll need a quick verification. 
Please send a screenshot or link showing the lower price for the same property, dates, and number of guests. 
Once I have that, I’ll review it and confirm whether we can apply a match.
"""

Expected next actions:
- Verify listing, dates, and guest count against the booking
- Request evidence (screenshot/link)

Expected clarifying questions:
- Please share a screenshot or link to the lower price

Expected citations:
- Price mismatch policy (same dates, same property, evidence required)


### Scenario C — Date change request near stay
Ticket text:
"""
My flight was moved. I need to change my stay from Apr 6–9 to Apr 8–11.
Is that possible? Reservation 553210.
"""

Expected reply (agent draft):
"""
I can help with that. Date changes are possible if the host has availability and the policy allows changes close to check‑in. 
I’ll check availability for Apr 8–11 and confirm any price difference before making updates.

Can you confirm the number of guests is still the same?
"""

Expected next actions:
- Check host availability for new dates
- Confirm policy for changes near check-in
- Calculate any price difference

Expected clarifying questions:
- Is the guest count unchanged?

Expected citations:
- Date change policy (availability + potential fare differences)


## 2) Short pitch text
Support Copilot turns support tickets into consistent, policy‑aware replies in seconds. 
Agents paste a ticket, get a draft response grounded in the knowledge base, plus next steps and clarifying questions. 
This reduces handle time, improves consistency, and scales best‑practice support without heavy training.


## 3) Launch checklist
- Docker Desktop running
- `docker compose -f infra/docker-compose.yml up -d`
- Create venv and install deps: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Create `.env` from `.env.example` (no OpenAI key needed if using Ollama or Mock)
- Start Qdrant is healthy (port `6333`)
- Ingest KB: `python scripts/ingest_kb.py`
- Start API: `PYTHONPATH=. uvicorn apps.api.app.main:app --reload --port 8000`
- Start UI: `streamlit run apps/ui/app.py --server.port 8501`
- Open UI: `http://localhost:8501`
