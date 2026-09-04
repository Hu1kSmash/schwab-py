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

# There is deliberately no release target. This fork is not published to PyPI:
# the name `schwab-py` there belongs to the upstream project, so uploading this
# code would replace someone else's package with a different library under the
# same name. Releases are git tags, and the steps are in MAINTAINING.md under
# "Cutting a release".
#
# What stood here ran `twine upload dist/*` with the test step commented out,
# inherited from upstream, where publishing to PyPI is the correct thing to do.
release:
	@echo 'No. This fork is not on PyPI -- `schwab-py` there is upstream'\''s.'
	@echo 'Releases here are git tags. See MAINTAINING.md, "Cutting a release".'
	@exit 1

clean:
	rm -rf build dist docs-build schwab_py.egg-info __pycache__ htmlcov
