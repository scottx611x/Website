.PHONY: ci test run hooks pull-curations push-curations wildlife deploy

## deploy: stamp version.txt with HEAD (busts the 1-year asset cache) + zappa update.
## Always deploy with this, never bare `zappa update` — zappa zeroes file mtimes in
## the package, so version.txt is the ONLY thing that rotates the css/js cache key.
## deploy: package from a clean production venv and ship it
#
# NOT from .venv. Zappa packages whatever virtualenv it is run from, and the
# dev venv produced a zip with werkzeug MISSING — the Lambda then died at
# import with "No module named 'werkzeug'" and the site 502'd. (Rolling back
# was worse: the previous Lambda version was old enough to contain Python 2.7
# bytecode, so it failed too.) A venv built from requirements.txt alone
# packages cleanly.
#
# The zip is inspected before it goes anywhere, because "it uploaded" and "it
# imports" turned out to be very different things.
DEPLOY_VENV := .deploy-venv

deploy:
	@test -d $(DEPLOY_VENV) || python3.12 -m venv $(DEPLOY_VENV)
	@$(DEPLOY_VENV)/bin/pip install -q --upgrade pip
	@$(DEPLOY_VENV)/bin/pip install -q -r requirements.txt "zappa==0.62.1"
	git rev-parse --short HEAD > version.txt
	@rm -f /tmp/zappa-pkg.zip
	@VIRTUAL_ENV=$(PWD)/$(DEPLOY_VENV) PATH=$(PWD)/$(DEPLOY_VENV)/bin:$$PATH \
		$(DEPLOY_VENV)/bin/zappa package production -o /tmp/zappa-pkg.zip >/dev/null
	@python3 -c "import zipfile,sys; \
		n=zipfile.ZipFile('/tmp/zappa-pkg.zip').namelist(); \
		missing=[m for m in ('werkzeug/__init__.py','flask/__init__.py','jinja2/__init__.py','handler.py','index.py') if m not in n]; \
		sys.exit('REFUSING TO DEPLOY - package is missing: %s' % missing) if missing else print('package OK (%d entries)' % len(n))"
	@VIRTUAL_ENV=$(PWD)/$(DEPLOY_VENV) PATH=$(PWD)/$(DEPLOY_VENV)/bin:$$PATH \
		$(DEPLOY_VENV)/bin/zappa update production
	@echo "deployed $$(cat version.txt)"
	@curl -sL -o /dev/null -w "live check: / = %{http_code}\n" --max-time 45 https://www.scott-ouellette.com/

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

## wildlife: publish non-bird photos from wildlife_incoming/<Category>/ to S3 + /photography
wildlife:
	@BIRDS_S3_BUCKET=birds-scott-ouellette python wildlife.py $(DIR)

## hooks: install the git pre-push hook that runs `earthly +test`
hooks:
	git config core.hooksPath .githooks
	@echo "pre-push hook installed (runs 'earthly +test' before each push)"
