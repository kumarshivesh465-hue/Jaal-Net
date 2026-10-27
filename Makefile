.PHONY: help install run-backend run-frontend test test-integration \
        check verify load-test demo docker-up docker-down simulate clean

help:
	@echo "Targets:"
	@echo "  install           Install Python dependencies"
	@echo "  run-backend       Start FastAPI on port 8000"
	@echo "  run-frontend      Start Streamlit on port 8501"
	@echo "  test              Run unit tests (skip integration)"
	@echo "  test-integration  Run integration tests"
	@echo "  check             Alias for the default test suite (not integration)"
	@echo "  verify            Full gate: py_compile + tests + metrics + import app"
	@echo "  load-test         Measure P50/P95/P99 at 100 concurrent (writes artifacts/load_test.json)"
	@echo "  demo              Bootstrap API + console and print URLs"
	@echo "  docker-up         Build and start backend + frontend"
	@echo "  docker-down       Stop containers"
	@echo "  simulate          Generate N mock transactions and score them"
	@echo "  clean             Remove caches and __pycache__"

install:
	pip install -r requirements.txt

run-backend:
	uvicorn backend:app --host 0.0.0.0 --port 8000 --reload

run-frontend:
	streamlit run app.py --server.port 8501

test:
	pytest tests/ -m "not integration" -v

test-integration:
	pytest tests/ -m integration -v

check:
	./.venv/Scripts/python -m pytest tests/ -m "not integration" -q

verify:
	bash scripts/verify.sh

# Reports, and exits non-zero when the 300 ms budget is missed: the point is
# the measurement, not a green tick.
load-test:
	./.venv/Scripts/python scripts/load_test.py

demo:
	bash scripts/demo.sh

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

simulate:
	python simulate_stream.py --count 50

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
