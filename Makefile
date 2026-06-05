.PHONY: help install dev test lint fmt cover backtest montecarlo clean

help:               ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:            ## Install the package (runtime deps only)
	pip install -e .

dev:                ## Install with dev + all optional extras
	pip install -e ".[dev,all]"

test:               ## Run the test suite
	pytest

cover:              ## Run tests with coverage report
	pytest --cov=quantalgo --cov-report=term-missing

lint:               ## Lint with ruff
	ruff check src tests

fmt:                ## Auto-format / fix with ruff
	ruff check --fix src tests

backtest:           ## Run a sample backtest
	quantalgo backtest --symbol MES --days 180

montecarlo:         ## Run a sample Monte-Carlo simulation
	quantalgo montecarlo --symbol MES --sims 10000

clean:              ## Remove build / cache artefacts
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
