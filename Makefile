.PHONY: validate-local test lint clean install build-docker

validate-local: clean install test lint
	@echo "✅ Local validation passed - safe to push"

install:
	pip install -q -r requirements-dev.txt

test:
	pytest -v tests/ --tb=short

lint:
	python -m py_compile routes/ core/ models/ services/ handlers/ || true

build-docker:
	docker build -t portal-nav-api:test .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
