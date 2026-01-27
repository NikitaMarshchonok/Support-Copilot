# Demo Script (2–3 min)

## 0) Setup
- Ensure Qdrant, API, UI running
- Open UI: `http://localhost:8501`
- Enable **Demo mode**

## 1) Scenario A: Refund within policy
Say:
"This is a typical refund request. I’ll load a demo scenario and generate a reply."
Action:
- Select **Refund within policy → Load scenario**
- The reply auto-generates
Point out:
- Draft reply is concise and policy-aware
- Citations show the exact policy source
- Next actions and clarifying questions help the agent

## 2) Scenario B: Price mismatch
Say:
"Now a price mismatch. We ask for evidence and verify conditions."
Action:
- Select **Price mismatch claim → Load scenario**
Point out:
- Draft asks for proof (screenshot/link)
- Actions show verification steps

## 3) Scenario C: Date change
Say:
"Date changes depend on availability and policy rules."
Action:
- Select **Date change request → Load scenario**
Point out:
- Draft requests confirmation
- Actions highlight availability + price check

## 4) Export + history
Say:
"We can export responses and keep session history."
Action:
- Click **Download Markdown** or **Download PDF**
- Expand **Session history**

## Closing (10 sec)
"Support Copilot reduces handling time and ensures consistent, policy‑aligned replies, while remaining fully explainable via citations."
