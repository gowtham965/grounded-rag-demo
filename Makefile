ingest:
	python -m app.ingest
reindex:
	python -m app.ingest --reindex
serve:
	uvicorn app.main:app --reload --port 8000
eval:
	python -m eval.run_eval
eval-judge:
	python -m eval.run_eval --judge
test:
	pytest -q tests
