# Maintaining this fork

Notes for whoever works on this next, including future me.

## Branch model

| Branch | What it is |
|---|---|
| `main` | The fork's release line. Tagged releases come from here. |
| `upstream-main` | A mirror of `alexgolec/schwab-py`'s `main`. Never commit to it. |
| topic branches | One concern each, **branched from `upstream-main`**, opened as PRs upstream. |

The reason topic branches start from `upstream-main` rather than `main` is that a pull request
against upstream must not carry this fork's identity — the version bump, the changed URLs, the
changelog, the README notice. Branching from `main` would drag all of that into the diff and the PR
would be unreviewable.

Remotes:

```
origin    git@github.com:Hu1kSmash/schwab-py.git      (this fork)
upstream  https://github.com/alexgolec/schwab-py.git  (the original)
```

## Adding a change

```shell
git fetch upstream
git checkout upstream-main && git merge --ff-only upstream/main   # keep the mirror current
git checkout -b some-focused-change upstream-main

# ... make the change, with tests ...

git push origin some-focused-change
gh pr create -R alexgolec/schwab-py --base main --head Hu1kSmash:some-focused-change

git checkout main && git merge some-focused-change                # then take it into the fork
```

Every change goes upstream as a PR **first**, then into `main`. Not the other way round, and not
only into `main`. Two reasons: it is the honest thing to do given essentially all of this code is
Alex Golec's, and every merged PR shrinks the divergence this fork has to carry.

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

**Do not bundle.** A PR that fixes one thing and tidies another does not get reviewed. This applies
even though upstream is currently quiet; the PRs are a queue for whenever it is not.

**Check a branch really went upstream before calling it done.** `stream-reader-routing` was
branched from `main` instead of `upstream-main`, so it could never be opened as a pull request —
its diff carries the version bump and the fork notice along with the actual change — and it was
merged here anyway. Nothing noticed for months: the branch existed, the code worked, the tests
passed, and the README went on claiming everything had been offered upstream. To audit it:

```shell
gh pr list -R alexgolec/schwab-py --author Hu1kSmash --state all --limit 60 \
    --json headRefName --jq '.[].headRefName' | sort -u > /tmp/prs
git branch --merged main --format='%(refname:short)' | sort > /tmp/merged
comm -23 /tmp/merged /tmp/prs
```

What comes out should be only fork-identity branches, fork-only features, and changes vendored
from someone else's upstream PR. Anything else is a claim the README is making and the repository
is not keeping.

**Run the suite after every merge into `main`, not just on the topic branch.** This fork removed
imports upstream still carries, so a branch which passes against `upstream-main` can fail here on
names that exist there and not here. It has happened three times — `warnings`, `json` and the `abc`
line in `client/base.py` — and the failure is a `NameError` at runtime, not a merge conflict, so
nothing warns you. The fix is always to put the import back; the point is to notice.

## Cutting a release

1. `CHANGELOG.md` — a new section, written for someone who has to decide whether to upgrade.
2. `schwab/version.py` — bump. Minor for added surface or changed behaviour, patch for fixes alone.
3. **The install instructions**, which name the version and go stale silently:

   ```shell
   grep -rn 'schwab-py@v' README.rst docs/
   ```

   Today that is the fork notice and the install section in `README.rst`, and
   the install step in `docs/getting-started.rst`. Nothing checks these, and a
   reader following a stale one installs the wrong release without any sign
   that they have.

4. Commit, then `git tag -a vX.Y.Z`.
5. `git push origin main && git push origin vX.Y.Z`.
6. `gh release create vX.Y.Z -R Hu1kSmash/schwab-py --notes-file ...`

Verify before tagging: full suite on **both** CPython 3.12 and 3.14,
`python -m build --sdist`, and `sphinx-build -W docs/ docs-build`.

Never write a bare `pip install schwab-py` anywhere. That installs the original
project from PyPI, which is not this code — and it will appear to work, since
the importable package has the same name.

## Not on PyPI, deliberately

`schwab-py` on PyPI is upstream's. This fork installs from git:

```shell
pip install "schwab-py @ git+https://github.com/Hu1kSmash/schwab-py@vX.Y.Z"
```

Pin a tag or a commit, never a branch — a branch moves, and a rebuild months later would silently
pull different code.

The importable package stays `schwab`, which is what makes this a drop-in replacement and keeps
merges from upstream clean. The cost is that this cannot be installed alongside the PyPI package:
both provide `schwab`, and whichever was installed last wins.

## If upstream comes back

Merge what lands, drop the corresponding local commits, and reassess whether the fork still needs to
exist. It was created because upstream had not merged anything in twelve months while defects
affecting live trading stayed open. If that stops being true, the right move is to go back to
upstream, not to defend the fork.
