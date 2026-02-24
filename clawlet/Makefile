# Clawlet Makefile
.PHONY: install dev test lint clean

install:
	pip install -r requirements-core.txt

dev: install
	pip install -r requirements-dev.txt

test:
	pytest tests/ --cov=clawlet --cov-report=html --cov-report=term

test-unit:
	pytest tests/ -m unit --cov=clawlet

test-integration:
	pytest tests/ -m integration

lint:
	 flake8 clawlet/ --max-line-length=100 --extend-ignore=E203,W503

format:
	 black clawlet/ --line-length 100

clean:
	rm -rf .pytest_cache htmlcov .coverage *.db __pycache__ clawlet/__pycache__ tests/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
