# Releasing and maintaining `schwaby`

Notes for whoever works on this next, including future me. `schwaby` is a
standalone project: there is no upstream to track, no pull request queue, and no
compatibility to preserve with anything but its own published releases.

## Rules that have earned their place

**Write a test that fails before the fix.** Every defect found so far sat in code
with 100% line coverage. Coverage measures which lines ran, not whether the
result was right. Before accepting a test, revert the fix and watch it fail — a
test that passes both ways is worse than none, because it looks like protection.

**Check the mutation actually applied.** A `sed` expression spanning two lines
matches nothing, and a restore within the same second reuses stale bytecode
(CPython invalidates on mtime and size). Both have produced a false green here.
Clear `__pycache__`, and confirm the file changed before believing the result.

**The suite mocks the network.** It proves the library builds the request it
intended and says nothing about whether Schwab accepts it. Anything asserting
real API behaviour has to be established against a live account, and the
assertion should say so and give the date.

**Never send a price as a binary float.** `set_price` and `set_stop_price` take a
string or a `decimal.Decimal` and refuse a float, because scaling one and
truncating sent a price a tick low.

**When fixing a defect class, grep for the shape rather than the instance.**
`truncate_float` was fixed to truncate in decimal rather than binary. The
identical defect — `int(float(value) * 1000)` — sat untouched in
`OptionSymbol.build()` for another release and mis-encoded 590 of the 100,000
cent-granular strikes between `$0.01` and `$1000.00`, naming a different contract
on the order-placement path. Nobody looked, because the first fix felt complete.
The same shape recurred in 3.0.0: a fix removed one empty package from the wheel
and stopped, while `find_packages()` was also shipping `tests/`.

**Ask what the bug was covering for.** Several times now a correctness fix has
exposed something worse the defect had been masking. Truncating prices hid that a
`Decimal` built from a float renders its 57-character binary expansion. Migrating
to `httpx2` for correct types flipped the exception hierarchy under the
downstream consumer. The question belongs in the fix, not the postmortem.

**An assertion about an empty result needs a positive control.**
`assertEqual([], offenders)` holds when the guard works *and* when the input
never reached it. Prove the collection found something, in the same test.

**A claim nothing checks will drift, silently.** A README, a changelog preamble
or a docstring asserting something no test covers goes stale without a symptom.
Prefer the weaker sentence you can verify.

**Do not bundle.** A commit that fixes one thing and tidies another cannot be
reverted, bisected to, or described in a changelog entry without dragging the
tidying along.

**Run the suite after merging into `main`, not just on the branch.** Two branches
that each pass can still fail together. It costs four seconds.

## Dependencies

`.github/dependabot.yml` watches the GitHub Actions used by the workflows and
opens a pull request when one goes stale. They had drifted five major versions
behind before anyone noticed, and the only symptom was a deprecation warning
inside a job annotation nobody reads.

It deliberately does not watch the Python dependencies. Those are floors rather
than pins, this library places trades, and upgrading one is a decision that wants
the verification below — not a bot's pull request merged on a quiet afternoon.

**There are no optional dependencies and there should not be any.** `dev` is the
only extra. An extra that everybody has to install is a hard dependency with a
way to get it wrong, and `pip freeze` silently drops extras — which is what
turned the 2.3.0 `login` split from a saving into three late failure modes.

## Cutting a release

1. `CHANGELOG.md` — a new section, written for someone deciding whether to
   upgrade.

2. `schwab/version.py` — bump. **Major if anything public is removed or
   renamed**, minor for added surface or changed behaviour, patch for fixes
   alone.

   Since 2.6.0 this is on PyPI, so `schwaby` or `schwaby>=2.6` in a requirements
   file resolves to whatever is newest and upgrades into a breaking release by
   accident. A changelog banner does not reach someone who never opens one, so
   the version number has to carry it.

3. **Anything naming a version**, which goes stale silently:

   ```shell
   grep -rn 'schwaby@v\|schwaby==' README.md docs/ schwab/
   ```

   Should be empty. Prose naming a version is worse than a pin, because that
   grep does not match it and the release may land under a different number than
   the one written. Say what changed, not which release changed it.

4. Verify, on **3.11, 3.12 and 3.14** — 3.14 is what the downstream consumer
   runs, and `asyncio` semantics differ below 3.12 as well as above it:

   ```shell
   pytest tests/ -q
   python -m build
   python -m twine check --strict dist/*
   python -m sphinx -W docs/ /tmp/docs-build
   ```

   **`twine check`'s output must be read, not glanced at.** It once reported a
   failure that was missed in truncated output, which would have published a
   release with no description. Note it is a much weaker gate for a markdown
   README than it was for reStructuredText: measured, it rejects only an empty or
   whitespace-only document. `tests/packaging_test.py::LongDescriptionTest`
   asserts the real property, and `readme_renderer[md]` must be installed or the
   check silently passes having rendered nothing.

   `python -m build` earns its place: `setup.py` is not imported by the suite, so
   an edit leaving it unparseable is invisible to `pytest`.

5. Commit, then `git tag -a vX.Y.Z`. Write the message from a file — backticks in
   `git tag -m` are executed as command substitution, which silently swallowed a
   word from the v2.5.0 tag.

6. `git push origin main && git push origin vX.Y.Z`

7. `gh release create vX.Y.Z -R Hu1kSmash/schwaby --notes-file ...`

   **Creating the release is what publishes to PyPI.**
   `.github/workflows/publish.yml` runs on a published release, re-runs the suite
   on all five Pythons, runs `twine check --strict`, verifies the built version
   matches the tag, and uploads via trusted publishing. Pushing a tag alone
   publishes nothing, so a tag can be moved before the release is created. After
   it, the version is permanent: PyPI refuses a re-upload even after a delete.

8. **Re-check any claim about the release against the tag, after tagging.**

   The range available while preparing a release is `vPREV..HEAD`, which excludes
   the commit that bumps `version.py` — so the convenient measurement is
   systematically the one that flatters the claim. "v2.4.1 touches nothing under
   `schwab/`" was measured that way, asserted about `v2.4.0..v2.4.1`, and a
   consumer ran the command and found `schwab/version.py`.

## The distribution name and the import name

The distribution is `schwaby`; the importable package is `schwab`. Those differ
on purpose — keeping the import means a consumer moving to this changes one line
of `requirements.txt`.

The cost is that `schwaby` cannot be installed alongside `schwab-py`. Both
provide the `schwab` package, so whichever lands second silently overwrites the
other's files, with no warning from `pip` and no failure at install time. Say so
wherever the install is documented.

A git install works for testing an unreleased commit:

```shell
pip install "schwaby @ git+https://github.com/Hu1kSmash/schwaby@<sha>"
```

Pin a commit, never a branch. Tags before the 2.6.0 rename carry `schwab-py` in
their metadata, so `pip` refuses `schwaby @ git+...@v2.5.1`.

**Never write `pip install schwab-py` as an instruction for this project.** That
installs a different, much older codebase, and it will appear to work because the
importable package has the same name either way.
