.PHONY: install run test clean

install:
	docker compose build

run:
	docker compose up

test:
	docker compose exec api python -m pytest tests/ -v

clean:
	docker compose down -v
	rm -rf __pycache__ .pytest_cache *.db src/__pycache__ tests/__pycache__ src/services/__pycache__
