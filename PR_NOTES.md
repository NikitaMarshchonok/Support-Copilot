# PR Notes

## Summary
- Add heuristic reranking for citations to reduce noise
- Log request metrics and show summary in UI
- Add demo auto‑run, custom presets, and embedded demo script

## Test plan
- [ ] `python scripts/ingest_kb.py`
- [ ] `PYTHONPATH=. uvicorn apps.api.app.main:app --reload --port 8000`
- [ ] `streamlit run apps/ui/app.py --server.port 8501`
- [ ] Load demo scenario → auto‑generate reply
- [ ] Export Markdown and PDF
- [ ] Verify Metrics + Session history populate

## Notes
- Custom presets: `data/demo_presets.json` (see example file)
- Metrics log: `data/metrics/metrics.jsonl`
