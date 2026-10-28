Release steps (local)

1. Build distributions:

   python -m build

2. Verify packages:

   python -m twine check dist/*

3. Upload to PyPI (you will need appropriate credentials in environment or ~/.pypirc):

   python -m twine upload dist/*

4. Push commits and tags to remote:

   git push origin main --follow-tags

5. Create a GitHub Release (optional) using the tag (you can use the website or `gh` CLI):

   gh release create v0.1.2 --title "v0.1.2" --notes-file CHANGELOG.md

Notes:
- This repo now includes a `pyproject.toml` and uses setuptools/build. The package name is `folder-size-tui` and version is 0.1.2.
- The top-level `folder_size_explorer.py` is a thin shim and the canonical entrypoint is the console script `folder-size-tui`.
