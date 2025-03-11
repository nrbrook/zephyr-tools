lint:
	black --check .
	isort --check .
	flake8 .

format:
	black .
	isort .
