.PHONY: ci test run hooks pull-curations push-curations

## ci: run the containerized test suite via Earthly (local CI)
ci:
	earthly +ci

## test: alias for ci
test:
	earthly +test

## run: start the app locally (outside containers) for development
run:
	python -m flask --app index run --host 0.0.0.0 --port 5055

## pull-curations: fold live-site (S3) curation edits back into the repo to commit
pull-curations:
	@BIRDS_USE_S3=1 BIRDS_S3_BUCKET=birds-scott-ouellette python -c "import birds; c=birds.pull_curations(); print('updated:', c or 'nothing changed')"

## push-curations: push repo curation files to S3 (make local edits live / seed)
push-curations:
	@BIRDS_USE_S3=1 BIRDS_S3_BUCKET=birds-scott-ouellette python -c "import birds; print('pushed:', birds.push_curations())"

## hooks: install the git pre-push hook that runs `earthly +test`
hooks:
	git config core.hooksPath .githooks
	@echo "pre-push hook installed (runs 'earthly +test' before each push)"
