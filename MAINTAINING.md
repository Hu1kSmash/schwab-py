# Maintaining this fork

Notes for whoever works on this next, including future me.

## Branch model

| Branch | What it is |
|---|---|
| `main` | The release line. Tagged releases come from here. |
| `upstream-main` | A mirror of `alexgolec/schwab-py`'s `main`. Never commit to it. Kept as a merge source in case upstream revives, not as a branch point. |
| topic branches | One concern each, **branched from `main`**. |

**This changed in 2.2.0.** Topic branches used to start from `upstream-main`, because a pull
request against upstream must not carry this fork's identity — the version bump, the changed URLs,
the changelog, the README notice — and branching from `main` drags all of that into the diff.

That constraint is gone, because the pull requests are gone. See *Why this fork stopped tracking
upstream* below.

Remotes:

```
origin    git@github.com:Hu1kSmash/schwaby.git      (this fork)
upstream  https://github.com/alexgolec/schwab-py.git  (the original)
```

## Adding a change

```shell
git checkout -b some-focused-change main

# ... make the change, with tests ...

git checkout main && git merge --no-ff some-focused-change
```

Then run the suite on `main`, not only on the branch — see the rules below.

## Keeping CI current

`.github/dependabot.yml` watches the GitHub Actions used by the workflow and opens a
pull request when one goes stale. They had drifted five major versions behind before
anyone noticed, and the only symptom was a deprecation warning inside a job annotation
that nobody reads.

It deliberately does not watch the Python dependencies. Those are floors rather than
pins, this library places trades, and upgrading one is a decision that wants the
verification described below -- not a bot's pull request merged on a quiet afternoon.

## Rules that have earned their place

**Write a test that fails before the fix.** Every defect found so far sat in code with 100% line
coverage. Coverage measures which lines ran, not whether the result was right. Before accepting a
test, revert the fix and watch it fail — a test that passes both ways is worse than none, because it
looks like protection.

**The suite mocks the network.** It proves the library builds the request it intended and says
nothing about whether the venue accepts it. Anything asserting real API behaviour has to be
established against a live account, and the assertion should say so and give the date.

**Never send a price as a binary float.** As of 2.1.0 the library refuses one: `set_price` and
`set_stop_price` take a string or a `decimal.Decimal`. `truncate_float` is gone. Upstream still
has it, and still truncates, so a price example ported from there will not run here.

**When fixing a defect class, grep for the shape rather than the instance.** `truncate_float` was
fixed to truncate in decimal rather than binary. The identical defect —
`int(float(value) * 1000)` — sat untouched in `OptionSymbol.build()` for another release and
mis-encoded 590 of the 100,000 cent-granular strikes between `$0.01` and `$1000.00`, naming a
different contract on the order-placement path. Nobody looked, because the first fix felt complete.
That is the failure mode: a fix that resolves the symptom stops the search for the pattern.

**Ask what the bug was covering for.** Three times now a correctness fix has exposed something
worse that the defect had been masking. Truncating prices hid that a `Decimal` built from a float
renders its 57-character binary expansion. Migrating to `httpx2` for correct types flipped the
exception hierarchy under the downstream consumer. Removing the float price path exposed that the
constructor's zero-stripping never fired except on a trailing `.`. The question belongs in the fix,
not in the postmortem.

**Do not bundle.** This used to be about pull requests getting reviewed. It survives them for a
better reason: a commit that fixes one thing and tidies another cannot be reverted, bisected to, or
described in a changelog entry without dragging the tidying along. The 2.1.0 option-strike fix
landed bundled with release changes rather than on a branch of its own, and could not afterwards be
separated from them, which is the kind of debt this rule prevents.

**Say what the repository is actually keeping.** `stream-reader-routing` was branched from `main`
rather than `upstream-main`, so it could never have been opened as a pull request, and it was
merged here anyway. Nothing noticed for months: the branch existed, the code worked, the tests
passed, and the README went on claiming everything had been offered upstream. The specific trap is
gone with the upstream model, but the general one is not — a README, a changelog preamble or a
docstring asserting something nothing checks will drift, and it drifts silently. Three separate
review passes on 2.1.0 caught claims of exactly this kind.

**Run the suite after every merge into `main`, not just on the topic branch.** This began as a
guard against branches cut from `upstream-main`, which could pass there and fail here on imports
this fork had removed — `warnings`, `json` and the `abc` line in `client/base.py`, three times,
each a `NameError` at runtime rather than a merge conflict, so nothing warns you. Branching from
`main` removes that particular cause and not the general one: two branches that each pass can still
fail together. It costs four seconds.

## Cutting a release

1. `CHANGELOG.md` — a new section, written for someone who has to decide whether to upgrade.
2. `schwab/version.py` — bump. **Major if anything public is removed or renamed**, minor for
   added surface or changed behaviour, patch for fixes alone.

   The major rule is newer than the project and worth the sentence. 2.1.0 was breaking and
   shipped as a minor, justified by "this fork is installed from pinned tags rather than
   version ranges — nothing upgrades into it by accident." That was true then and stopped
   being true at 2.6.0, the first PyPI release: `schwaby` or `schwaby>=2.6` in a requirements
   file now resolves to whatever is newest. A changelog banner does not reach someone who
   never opens one, so the version number has to carry it. 3.0.0 removed
   `schwab.contrib.orders` and was numbered accordingly.
3. **Anything naming a version**, which goes stale silently:

   ```shell
   grep -rn 'schwaby@v\|schwaby==' README.md docs/ schwab/
   ```

   Should be empty. Since 2.6.0 the install instructions say `pip install
   schwaby` with no version, so a reader following them gets the current
   release. Anything that reintroduces a number is a thing nothing checks, and a
   reader following a stale one installs the wrong release with no sign of it.

   Prose which names a version is worse than a pin, because the grep above does
   not match it and the release may land under a different number than the one
   written. Say what changed, not which release changed it, and let
   `CHANGELOG.md` carry the number.

4. Commit, then `git tag -a vX.Y.Z`.
5. `git push origin main && git push origin vX.Y.Z`.
6. `gh release create vX.Y.Z -R Hu1kSmash/schwaby --notes-file ...`

   **Creating the release is what publishes to PyPI.** `.github/workflows/publish.yml`
   runs on a published release, re-runs the suite on all five Pythons, checks
   `twine check --strict`, verifies the built version matches the tag, and
   uploads via trusted publishing. Pushing a tag alone publishes nothing, so a
   tag can be fixed or moved before the release is created — after it, the
   version is permanent, because PyPI refuses a re-upload of a version even
   after you delete it.
7. **Re-check any claim about the release against the tag, after tagging.**

   A statement like "nothing under `schwab/` changed" is checkable, so a reader
   will run it. The range you can check while preparing the release is
   `vPREV..HEAD`, and it excludes the commit that bumps `version.py` — which is
   the commit that makes the tag a tag. So the convenient range is
   systematically the one that makes the claim look truer than it is, and it
   will be true every time right up until you publish.

   This is not hypothetical: "v2.4.1 touches nothing under `schwab/`" was
   measured before the release commit, asserted about `v2.4.0..v2.4.1`, and a
   consumer ran the command and found `schwab/version.py` in it. The substance
   was fine and the checkable form was false, which is the worse half to get
   wrong. Prefer the weaker sentence you can defend after tagging.

Verify before tagging: full suite on **both** CPython 3.12 and 3.14,
`python -m build --sdist`, `python -m twine check dist/*`, and
`sphinx-build -W docs/ docs-build`.

`twine check` is not optional and its output must be read, not glanced at. It
is the only thing that checks `README.md` renders as PyPI will render it —
`sphinx -W` passes on markup PyPI rejects, because they are different parsers.
A title whose underline is one character short fails `twine check` and would
publish a release with no description at all.

`python -m build --sdist` earns its place here: `setup.py` is not imported by
the suite, so an edit which leaves it unparseable is invisible to `pytest`.
`tests/packaging_test.py` now covers the common cases, but the build is what
proves the artifact.

Never write `pip install schwab-py` as an instruction for this project. That
installs the original
project from PyPI, which is not this code — and it will appear to work, since
the importable package has the same name.

## The distribution name and the import name

Since 2.6.0 this publishes to PyPI as `schwaby`:

```shell
pip install schwaby
```

The importable package stays `schwab`. Those differ on purpose: keeping the import makes this a
drop-in replacement, so a consumer changes one line of `requirements.txt` and nothing else.

The cost is that `schwaby` cannot be installed alongside `schwab-py`, the original project. Both
provide the `schwab` package, so whichever lands second silently overwrites the other's files —
`pip` gives no warning and nothing fails at install time. Say so wherever the install is
documented; a reader with both installed is running code they did not choose.

A git install still works for testing an unreleased commit:

```shell
pip install "schwaby @ git+https://github.com/Hu1kSmash/schwaby@<sha>"
```

Pin a tag or a commit, never a branch — a branch moves, and a rebuild months later would silently
pull different code. Note that tags before the repository rename carry `schwab-py` in their
metadata, so `pip` refuses a `schwaby @ git+...@v2.5.1`.

## No extras

As of 3.0.0 the only extra is `dev`, and nothing a user installs is optional. Do not add one back:
an extra that everybody has to install is a hard dependency with a way to get it wrong, and
`pip freeze` silently drops extras, which is what turned the 2.3.0 split from a saving into three
late failure modes.

`login` and `codegen` were briefly kept as empty names so an old pin would not warn. That went too,
once measured: `schwaby[login]` was installable from PyPI for about four hours, in 2.6.0 alone, and
pip treats an unknown extra as a warning and installs anyway. A shim defending that is legacy on
the day it ships.

## Why this fork stopped tracking upstream

Until 2.2.0, every change here was branched from a mirror of upstream and offered as a pull request
before being merged. That was the honest arrangement: essentially all of this code is Alex Golec's,
and every merged PR would have shrunk the divergence this fork has to carry.

It stopped being an arrangement and became a ritual. Upstream merged nothing for over a year while
defects affecting live trading stayed open. The maintainer was asked directly in September 2026 and
confirmed he does not intend to update the project. Meanwhile the machinery kept costing: the last
several changes were cut from `main` because they could not sensibly be cut from anywhere else, and
each one needed a paragraph in the README explaining why it had not been sent.

So this fork is now the authoritative project, and does not maintain compatibility with upstream.
Practically:

- Topic branches come from `main`. There is no PR queue and no branch-point discipline to keep.
- Changes are made because they are right for this library, not because upstream might take them.
- `upstream-main` stays as a mirror. If upstream ever revives, it is a merge source — reconcile
  what lands, drop the corresponding local commits, and reassess. That is the same advice as
  before; only the default direction has changed.

What has *not* changed is the debt: this is still overwhelmingly Alex Golec's work, the README says
so, and the licence and attribution stay exactly as they are. Going authoritative is a statement
about maintenance, not about authorship.
