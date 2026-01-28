# Support Copilot (RAG MVP)

RAG демо для саппорта: FastAPI + Qdrant + Streamlit + OpenAI.

## Быстрый запуск (5 команд)
```bash
# 1) Поднять Qdrant
docker compose -f infra/docker-compose.yml up -d

# 2) Виртуальное окружение + зависимости
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3) env
cp .env.example .env
# Выберите провайдер в .env: LLM_PROVIDER=openai|ollama|mock

# 4) Индексация KB
python scripts/ingest_kb.py

# 5) Запуск API + UI
PYTHONPATH=. uvicorn apps.api.app.main:app --reload --port 8000
streamlit run apps/ui/app.py --server.port 8501
```

## Проверка без UI
```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/suggest-reply \
  -H "Content-Type: application/json" \
  -d '{"ticket_text":"I want to cancel due to illness. Can I get a refund?","language":"en","category":"cancellation"}'
```

## Demo flow
- Запустите сервисы и UI (см. быстрый запуск)
- В UI выберите **Demo scenarios → Load scenario**
- Для авто‑генерации включите **Demo mode**
- Нажмите **Generate** и покажите Draft reply + Citations + Next actions
- Покажите **Policy preview** и статус KB в сайдбаре
- Готовые тексты сценариев: `DEMO_PACK.md`
- Экспорт результата: **Download Markdown** / **Download PDF**
- История запросов пишется в `data/history/history.jsonl`
- Скрипт демо‑презентации: `DEMO_SCRIPT.md`
- Кастомные пресеты: скопируйте `data/demo_presets.example.json` → `data/demo_presets.json`

## RAG eval (качество)
```bash
# Запуск базовой оценки (retrieval + generation)
python scripts/eval_rag.py

# Только retrieval (без LLM)
python scripts/eval_rag.py --no-llm
```
Кейсы лежат в `data/eval/cases.jsonl`, результаты пишутся в `data/eval/results.jsonl`.
Итоговая сводка сохраняется в `data/eval/results.summary.json`.
В UI есть блок **RAG eval** с краткой сводкой и последними кейсами.

## Структура
```
apps/api/app     # FastAPI + RAG
apps/ui          # Streamlit UI
infra            # docker-compose (Qdrant)
scripts          # ingest_kb.py
data/kb          # knowledge base (создается при ingest)
```

## Примечания
- Если Qdrant недоступен, проверьте контейнер: `docker ps`.
- Если используете VS Code: откройте папку проекта и запускайте команды в терминале внутри IDE.
 - Локально/бесплатно (Ollama): `LLM_PROVIDER=ollama`, затем:
   - `ollama pull llama3.1`
   - `ollama pull nomic-embed-text`
 - Без моделей (mock): `LLM_PROVIDER=mock` (генерация без LLM)
- Low‑confidence режим настраивается через `LOW_CONFIDENCE_THRESHOLD`
