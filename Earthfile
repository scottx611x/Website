VERSION 0.8
FROM python:3.12-slim
WORKDIR /app

# deps: install dependencies once; cached unless requirements.txt changes.
deps:
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt pytest

# test: run the suite in a clean container.
test:
    FROM +deps
    COPY . .
    RUN python -m pytest tests.py -q

# ci: the default gate (what the pre-push hook and `make ci` run).
ci:
    BUILD +test
