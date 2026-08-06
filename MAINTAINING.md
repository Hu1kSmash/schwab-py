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

## Rules that have earned their place

**Write a test that fails before the fix.** Every defect found so far sat in code with 100% line
coverage. Coverage measures which lines ran, not whether the result was right. Before accepting a
test, revert the fix and watch it fail — a test that passes both ways is worse than none, because it
looks like protection.

**The suite mocks the network.** It proves the library builds the request it intended and says
nothing about whether the venue accepts it. Anything asserting real API behaviour has to be
established against a live account, and the assertion should say so and give the date.

**Never send a price as a binary float.** `truncate_float` is now correct, but strings are the
supported path and the float path is deprecated upstream.

**Do not bundle.** A PR that fixes one thing and tidies another does not get reviewed. This applies
even though upstream is currently quiet; the PRs are a queue for whenever it is not.

## Cutting a release

1. `CHANGELOG.md` — a new section, written for someone who has to decide whether to upgrade.
2. `schwab/version.py` — bump. Minor for added surface or changed behaviour, patch for fixes alone.
3. Commit, then `git tag -a vX.Y.Z`.
4. `git push origin main && git push origin vX.Y.Z`.
5. `gh release create vX.Y.Z -R Hu1kSmash/schwab-py --notes-file ...`

Verify before tagging: full suite on **both** CPython 3.12 and 3.14, and `python -m build --sdist`.

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
