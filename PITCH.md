# Support Copilot — 1‑страничный pitch

## Problem (что болит)
- Саппорт-агенты тратят время на поиск правил/политик, копипасту и уточнения.
- Ответы бывают неодинаковые; ошибки в политике приводят к компенсациям/эскалациям.
- Длинный AHT, низкий FCR, падает CSAT.

## Solution (что строим): Support Copilot
Внутри агентского интерфейса показывает:
- Suggested reply (черновик ответа)
- Citations (точные ссылки на policy/help/FAQ)
- Next best action (эскалация / запрос данных / изменение брони / отмена / ваучер)
- Auto-summary разговора (для передачи на L2)

Принцип: RAG (retrieval augmented generation). Модель отвечает только на основе базы знаний + контекста кейса.

## ROI (как считаем эффект)
- −10–25% AHT (быстрее находить правила + готовый черновик)
- +5–15% FCR (меньше уточнений и “передам специалисту”)
- −X% эскалаций/ошибок (citations + policy guardrails)

Метрики пилота: AHT, FCR, CSAT, escalation rate, adoption rate, hallucination rate.

## Архитектура (простая, но “как у продакшена”)
**Данные**
- KB: help-статьи, policy, SOP, шаблоны ответов (можно начать с публичных страниц/markdown).
- (Опционально) история тикетов: для fine-tune позже, MVP не требует.

**Сервисы**
- Ingestion/Indexer: парсит документы → чанки → эмбеддинги → векторное хранилище.
- RAG API (FastAPI):
  - `/suggest-reply` (контекст тикета → поиск → draft + citations)
  - `/summarize` (короткое резюме)
  - `/eval` (оценка качества на тест-наборе)
- Vector DB: Qdrant (Docker) или pgvector.
- UI: Streamlit “Agent Console” — тикет слева → подсказки справа.

**Guardrails**
- Запрет на ответы без источников; “I don’t know” если нет совпадений.
- PII-редакция в логах.

**Telemetry**
- Логи: latency, confidence, источники, feedback 👍👎

**LLM/Embeddings**
- Вариант A (быстрый): OpenAI (embeddings + chat)
- Вариант B (дешевле/локально): Ollama + локальная модель

## План работ: 14 дней (реальный MVP)
- Дни 1–2: Skeleton (repo + docker-compose + FastAPI + базовые модели + UI-заготовка)
- Дни 3–4: Knowledge Base (ингест md/html, chunking + embeddings + Qdrant)
- Дни 5–6: RAG endpoint (`/suggest-reply`, строгий JSON)
- Дни 7–8: UI “Agent Console” (draft/citations/next steps + feedback)
- Дни 9–10: Мини-eval (30–50 кейсов, retrieval@k, faithfulness, latency)
- Дни 11–12: Guardrails (no citations → refuse, low confidence → clarify, PII mask)
- Дни 13–14: Demo pack (3 кейса, README с архитектурой и метриками, 60‑сек pitch)

## План 28 дней (если усилить)
- Intent routing (cancellation/payment/account)
- Multi-language (EN/RU/HE)
- Tool calling (эмуляция действий: refund/change/escalate)
- Feedback loop: плохие ответы → улучшение KB/чанкинга
- A/B: baseline (поиск + шаблон) vs Copilot

## Как презентовать (60–90 сек)
“I built a Support Copilot MVP for travel customer support. It generates agent reply drafts grounded in policy documents with explicit citations, plus next-best actions and an auto-summary for handoffs. The goal is to reduce AHT and improve first-contact resolution while keeping policy compliance. The MVP uses a RAG pipeline: ingestion → vector search → LLM response constrained by sources, with guardrails that refuse to answer without citations. I also added lightweight evaluation and agent feedback tracking to measure adoption and quality.”

## Самое важное: демо (3 сценария)
- “Guest wants to cancel due to illness” → ответ + ссылки на policy + уточняющие вопросы
- “Host asks about payout timing” → ответ + citations
- “User claims price mismatch” → шаги проверки + правильный тон коммуникации
