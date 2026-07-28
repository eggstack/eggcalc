# Releasing eggcalc

Releases are prepared and published manually to PyPI. GitHub CI is for current-code correctness only. GitHub Actions does not determine release cadence, publish distributions, create releases, or validate historical release evidence.

## Prerequisites

```bash
pip install -e ".[dev]"
```

## Release Procedure

1. **Choose the version.** Update `eggcalc/_version.py` with the new version string.

2. **Update the changelog.** Edit `CHANGELOG.md` with the release notes.

3. **Commit the release metadata.**

   ```bash
   git add eggcalc/_version.py CHANGELOG.md
   git commit -m "Release vX.Y.Z"
   ```

4. **Ensure the working tree is clean.**

   ```bash
   git status   # should show nothing to commit
   ```

5. **Run the full release check.**

   ```bash
   make release-check
   ```

   This runs `make check` (lint, format, typecheck, docs-check, full test suite) followed by `make package-check` (build, twine check, installed-wheel smoke tests, single-file smoke tests).

6. **Inspect `dist/`.** Confirm the filenames and version match expectations.

   ```bash
   ls dist/
   ```

7. **Create the version tag** on the exact checked commit.

   ```bash
   git tag vX.Y.Z
   ```

8. **Upload to PyPI.**

   ```bash
   make publish
   ```

   Or equivalently:

   ```bash
   python -m twine upload dist/*
   ```

9. **Push main and the tag manually.**

   ```bash
   git push origin main
   git push origin vX.Y.Z
   ```

10. **Optionally create a GitHub Release** manually from the tag.

## Important Notes

- **PyPI versions are immutable.** A failed or incorrect publication requires a new version number. You cannot overwrite a published release.
- **GitHub Actions does not publish.** No workflow triggers publication or creates GitHub Releases from tags.
- **Tag pushes have no automated side effects.** Pushing a tag is a plain Git operation.
- **TestPyPI is optional and manual.** If you want to test on TestPyPI, upload there first as a separate manual step. It is not a required release gate.
- **Credentials** are supplied through normal Twine/PyPI mechanisms (e.g. `~/.pypirc` or environment variables). They are never stored in repository files.
- **No release step depends on CI run IDs, artifact IDs, candidate SHAs, evidence records, performance baselines, or generated closure manifests.**
