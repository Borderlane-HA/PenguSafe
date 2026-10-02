# Publish this repository on GitHub

Repository: https://github.com/Borderlane-HA/PenguSafe

1. Create the public repository with the default branch named **main**.
2. Extract `PenguSafe-0.2.0-GitHub-Upload.zip` on your computer.
3. Use **Add file → Upload files** and upload the extracted files/folders.
   `README.md`, `Makefile`, `LICENSE`, `src`, `tools` and `docs` must be at the
   repository root, not inside an extra `PenguSafe` directory.
4. Include `.gitignore` if your file picker hides files starting with a dot.
   The source tarball install uses `sh`, so the WebUI upload does not need to
   preserve executable bits. The installer sets the installed runtime modes.
5. Commit the upload to **main**. Verify the hero image renders in the README.
6. Optionally create a release/tag **v0.2.0** and attach the full ZIP. Mark it as a
   **pre-release** and state that this is alpha software for non-production tests.
7. The README's `main` download instructions then work. The tagged instructions
   work only after the matching tag exists.

The full ZIP includes a `PenguSafe/` parent folder for copying to OPNsense.
The GitHub upload ZIP contains the complete repository at its root, suitable
for the initial publication; it is not merely a patch over an existing repo.

GitHub's repository social preview is separate from the README hero. You can
set an image in **Settings → General → Social preview** if desired.
