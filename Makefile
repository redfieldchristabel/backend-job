.PHONY: install run test clean

install:
	docker compose build

run:
	docker compose up -d 

test:
	./test.sh

clean:
	docker compose down -v
	rm -rf __pycache__ .pytest_cache *.db src/__pycache__ tests/__pycache__ src/services/__pycache__
