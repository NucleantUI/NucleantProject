"""GitHub Actions workflow generator for Google Play uploads.

The rendered workflow builds + signs a release AAB and uploads it to the Play
Console. Swift (swiftly + the pinned toolchain + the Android Swift SDK) and the
Android SDK/NDK are provisioned by nucleant itself; Java comes from
``setup-java``.

Required repository secrets:

- ``ANDROID_KEYSTORE_BASE64``  — base64 of the release keystore file
- ``STOREPASS``                — keystore password
- ``KEYALIAS``                 — key alias
- ``KEYPASS``                  — alias key password (may be empty if same as STOREPASS)
- ``PLAY_SERVICE_ACCOUNT_JSON`` — Google Cloud service-account JSON with
  access to the Play Console app
"""

from __future__ import annotations

from pathlib import Path

_WORKFLOW_TEMPLATE = """\
name: Android Play Store upload

on:
  push:
    tags:
      - "*"  # every new tag; narrow to e.g. "v*" if you also tag non-releases

jobs:
  upload:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Java
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "21"

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Sync project (installs the nucleant dev tool)
        run: uv sync

      - name: Install Swift + the Android Swift SDK
        run: uv run nucleant toolchain install --android

      - name: Stamp version_code / version_name
        run: |
          # Play requires a strictly increasing versionCode per upload.
          sed -i -E "s|^#? ?version_code = .*|version_code = ${{ github.run_number }}|" nucleant.toml
          # version_name is taken from the tag when it looks like 1.2.3 (a
          # leading "v" is stripped); otherwise the committed value is kept.
          TAG="${GITHUB_REF_NAME#v}"
          if [[ "$TAG" =~ ^[0-9]+(\\.[0-9]+){0,2}$ ]]; then
            if grep -qE "^#? ?version_name = " nucleant.toml; then
              sed -i -E "s|^#? ?version_name = .*|version_name = \\"$TAG\\"|" nucleant.toml
            else
              sed -i "/^\\[android\\]/a version_name = \\"$TAG\\"" nucleant.toml
            fi
          fi
          grep -E "^version_(code|name)" nucleant.toml

      - name: Write release keystore
        env:
          ANDROID_KEYSTORE_BASE64: ${{ secrets.ANDROID_KEYSTORE_BASE64 }}
        run: |
          echo -n "$ANDROID_KEYSTORE_BASE64" | base64 --decode > "$RUNNER_TEMP/release.keystore"

      - name: Build release AAB
        run: uv run nucleant android archive release --bundle

      - name: Sign AAB
        env:
          KEYSTORE: ${{ runner.temp }}/release.keystore
          STOREPASS: ${{ secrets.STOREPASS }}
          KEYALIAS: ${{ secrets.KEYALIAS }}
          KEYPASS: ${{ secrets.KEYPASS }}
        run: uv run nucleant android sign --bundle

      - name: Upload to Google Play
        uses: r0adkll/upload-google-play@v1
        with:
          serviceAccountJsonPlainText: ${{ secrets.PLAY_SERVICE_ACCOUNT_JSON }}
          packageName: __PACKAGE_NAME__
          releaseFiles: project_dist/gradle/app/build/outputs/bundle/release/app-release-signed.aab
          track: internal  # change to beta / production when ready
"""


def render_playstore_workflow(package_name: str) -> str:
    """Return the workflow YAML for the given Android package name."""
    return _WORKFLOW_TEMPLATE.replace("__PACKAGE_NAME__", package_name)


def write_playstore_workflow(project_path: Path, package_name: str) -> Path:
    """Write the workflow into ``<project>/.github/workflows`` and return its path."""
    workflows = project_path / ".github" / "workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    out = workflows / "playstore-android.yml"
    out.write_text(render_playstore_workflow(package_name))
    return out
