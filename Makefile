.PHONY: ci test run hooks

## ci: run the containerized test suite via Earthly (local CI)
ci:
	earthly +ci

## test: alias for ci
test:
	earthly +test

## run: start the app locally (outside containers) for development
run:
	python -m flask --app index run --host 0.0.0.0 --port 5055

## hooks: install the git pre-push hook that runs `earthly +test`
hooks:
	git config core.hooksPath .githooks
	@echo "pre-push hook installed (runs 'earthly +test' before each push)"
