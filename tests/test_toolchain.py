from __future__ import annotations

import pytest

from nucleant.gradle.gradle_project import GradleProject, GradleProjectError
from nucleant.swift import sdks
from nucleant.swift.swiftly import _first_json_object

RELEASES = [
    {
        "name": "6.3.3",
        "platforms": [
            {"platform": "Linux", "name": "Ubuntu 24.04"},
            {"platform": "wasm-sdk", "checksum": "aaa"},
            {"platform": "android-sdk", "checksum": "bbb"},
        ],
    }
]


def test_sdk_naming():
    assert sdks.sdk_id("6.3.3", "android") == "swift-6.3.3-RELEASE_android"
    assert sdks.sdk_url("6.3.3", "wasm") == (
        "https://download.swift.org/swift-6.3.3-release/wasm-sdk/swift-6.3.3-RELEASE/"
        "swift-6.3.3-RELEASE_wasm.artifactbundle.tar.gz"
    )


def test_sdk_checksum_from_release_index():
    assert sdks.sdk_checksum("6.3.3", "android", RELEASES) == "bbb"
    assert sdks.sdk_checksum("6.3.3", "wasm", RELEASES) == "aaa"
    with pytest.raises(sdks.SwiftSdkError, match="not a release"):
        sdks.sdk_checksum("9.9.9", "android", RELEASES)


def test_parse_sdk_list():
    out = "swift-6.3.3-RELEASE_android\nswift-6.3.3-RELEASE_wasm\nswift-6.3.3-RELEASE_wasm-embedded\n"
    assert sdks.parse_sdk_list(out) == [
        "swift-6.3.3-RELEASE_android",
        "swift-6.3.3-RELEASE_wasm",
        "swift-6.3.3-RELEASE_wasm-embedded",
    ]
    assert sdks.parse_sdk_list("No Swift SDKs are currently installed.\n") == []


def test_first_json_object_skips_banners():
    text = '-----\nA new release of swiftly is available.\n-----\n{"paths": {"runtimeResourcePath": "/t/usr/lib/swift"}}\n'
    assert _first_json_object(text) == {"paths": {"runtimeResourcePath": "/t/usr/lib/swift"}}
    assert _first_json_object("no json here") is None


def test_gradle_task_names():
    task = GradleProject._gradle_task
    assert task(None, "debug", aar=False, bundle=False) == "assembleDebug"
    assert task(None, "release", aar=False, bundle=False) == "assembleRelease"
    assert task(None, "release", aar=False, bundle=True) == "bundleRelease"
    assert task(None, "release", aar=True, bundle=False) == "assembleRelease"
    with pytest.raises(GradleProjectError):
        task(None, "beta", aar=False, bundle=False)
