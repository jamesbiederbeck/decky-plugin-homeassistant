# Release Process

Currently we don't publish to the decky plugin store. Instead, we publish releases on GitHub.

## Steps to Release
Bump the version references in the following files:
   - `package.json`
   - `decky.pyi`
   - `install.sh` 

After merging a version which touches those files, .github/workflows/release.yml will automatically create a new release on GitHub and upload the necessary artifacts.

