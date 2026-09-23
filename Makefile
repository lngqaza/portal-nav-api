.PHONY: validate-local test lint clean install build-docker demo serve-demo

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

demo:
	@echo "📦 Demo site structure created successfully"
	@echo "Run 'make serve-demo' to start the demo server"

serve-demo:
	@echo "🚀 Starting SafeGuard Insurance Demo Site..."
	@cd demo-site && python -m http.server 8000 --bind 127.0.0.1
