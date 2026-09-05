test:
	python -m pytest tests/

fix:
	autopep8 --in-place -r -a schwab
	#autopep8 --in-place -r -a tests
	#autopep8 --in-place -r -a examples

coverage:
	python3 -m coverage run --source=schwab -m pytest tests/
	python3 -m coverage html

dist: clean
	python3 -m build

# Releasing is not a make target and should not become one. Publishing goes
# through .github/workflows/publish.yml, which fires on a published GitHub
# release and uploads with a trusted-publishing token -- so it re-runs the
# suite on all five Pythons, runs `twine check --strict`, and refuses if the
# tag and the built version disagree. A local `twine upload` skips every one of
# those, which is what the target inherited from upstream did.
#
# The steps are in MAINTAINING.md under "Cutting a release".
release:
	@echo 'No. Releases publish from CI on a published GitHub release.'
	@echo 'See MAINTAINING.md, "Cutting a release".'
	@exit 1

clean:
	rm -rf build dist docs-build schwaby.egg-info schwab_py.egg-info \
		__pycache__ htmlcov
