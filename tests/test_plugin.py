import ast
import importlib
from pathlib import Path

import pytest
import requests
import yaml
from conftest import ROOT
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from provider.huntapi import HuntAPIProvider

KEY = "test-key-not-real"
BASE = "https://api.huntapi.com"
TOOLS = {
    "media_metadata": "HuntAPIMediaMetadataTool",
    "download_video": "HuntAPIDownloadVideoTool",
    "download_audio": "HuntAPIDownloadAudioTool",
    "job_status": "HuntAPIJobStatusTool",
}


def run(tool_cls, params):
    return list(tool_cls.from_credentials({"api_key": KEY}).invoke(params))


def texts(messages):
    return [m.message.text for m in messages if m.type.value == "text"]


def jsons(messages):
    return [m.message.json_object for m in messages if m.type.value == "json"]


def test_credentials_check_calls_the_free_endpoint(http):
    http.reply(200, {"credits": 100})
    HuntAPIProvider()._validate_credentials({"api_key": f" {KEY} "})
    call = http.calls[0]
    assert (call["method"], call["url"]) == ("GET", BASE + "/v1/usage")
    assert call["headers"]["x-api-key"] == KEY
    assert call["timeout"] == 30


def test_credentials_check_rejects_a_bad_key_without_showing_it(http):
    http.reply(401, {"error": f"Invalid API key {KEY}"})
    with pytest.raises(ToolProviderCredentialValidationError) as error:
        HuntAPIProvider()._validate_credentials({"api_key": KEY})
    assert "401" in str(error.value) and "not valid" in str(error.value)
    assert KEY not in str(error.value)


def test_credentials_check_needs_a_key(http):
    with pytest.raises(ToolProviderCredentialValidationError):
        HuntAPIProvider()._validate_credentials({"api_key": "  "})
    assert http.calls == []


def test_network_error_has_a_clear_message(http):
    http.raise_error(requests.ConnectionError(f"failed with {KEY}"))
    with pytest.raises(ToolProviderCredentialValidationError) as error:
        HuntAPIProvider()._validate_credentials({"api_key": KEY})
    assert "api.huntapi.com" in str(error.value) and KEY not in str(error.value)


def test_plugin_registers_provider_and_tools():
    from dify_plugin import DifyPluginEnv
    from dify_plugin.core.plugin_registration import PluginRegistration

    registration = PluginRegistration(DifyPluginEnv())
    assert registration.get_tool_provider_cls("huntapi").__name__ == "HuntAPIProvider"
    for tool, class_name in TOOLS.items():
        assert registration.get_tool_cls("huntapi", tool).__name__ == class_name


def test_each_tool_file_has_one_tool_class():
    for path in Path(ROOT, "tools").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert len([n for n in tree.body if isinstance(n, ast.ClassDef)]) == 1, path.name


def test_manifest_and_tool_files_agree():
    manifest = yaml.safe_load(Path(ROOT, "manifest.yaml").read_text(encoding="utf-8"))
    provider = yaml.safe_load(Path(ROOT, "provider/huntapi.yaml").read_text(encoding="utf-8"))
    assert manifest["version"] == manifest["meta"]["version"]
    assert manifest["author"] == provider["identity"]["author"] == "huntapi"
    assert manifest["network"]["domains"] == ["api.huntapi.com"]
    assert Path(ROOT, "_assets", manifest["icon"]).is_file()
    assert Path(ROOT, manifest["privacy"]).is_file()
    assert sorted(Path(f).stem for f in provider["tools"]) == sorted(TOOLS)
    for tool_file in provider["tools"]:
        tool = yaml.safe_load(Path(ROOT, tool_file).read_text(encoding="utf-8"))
        assert tool["identity"]["author"] == "huntapi"
        assert Path(ROOT, tool["extra"]["python"]["source"]).is_file()
        for param in tool["parameters"]:
            assert param["form"] in ("llm", "form")
            assert param["form"] == "form" or param.get("llm_description")


CASES = [
    (
        "media_metadata",
        "HuntAPIMediaMetadataTool",
        {"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"},
        "GET",
        "/v1/media/metadata",
        {"query": "https://www.youtube.com/watch?v=jNQXAC9IVRw"},
    ),
    ("job_status", "HuntAPIJobStatusTool", {"job_id": "abc-123"}, "GET", "/v1/jobs/abc-123", {}),
]


@pytest.mark.parametrize("tool, cls_name, sample, method, url, values", CASES)
def test_tool_request(http, tool, cls_name, sample, method, url, values):
    http.reply(200, {"ok": True, "items": [1, 2]})
    cls = getattr(importlib.import_module(f"tools.{tool}"), cls_name)
    messages = run(cls, sample)
    call = http.calls[0]
    assert (call["method"], call["url"]) == (method, BASE + url)
    sent = call["params"] if method in ("GET", "DELETE") else call["json"]
    assert sent == values
    assert call["headers"]["x-api-key"] == KEY
    assert '"ok": true' in texts(messages)[0]
    assert jsons(messages) == [{"ok": True, "items": [1, 2]}]


@pytest.mark.parametrize("tool, cls_name, sample, method, url, values", CASES)
def test_required_inputs_are_checked_before_any_request(http, tool, cls_name, sample, method, url, values):
    cls = getattr(importlib.import_module(f"tools.{tool}"), cls_name)
    tool_yaml = yaml.safe_load(Path(ROOT, f"tools/{tool}.yaml").read_text(encoding="utf-8"))
    if not any(p["required"] for p in tool_yaml["parameters"]):
        pytest.skip("no required input")
    messages = run(cls, {})
    assert "is required" in texts(messages)[0] and jsons(messages) == []
    assert http.calls == []


def test_errors_are_returned_as_text(http):
    if not CASES:
        pytest.skip("covered by the brand tests")
    tool, cls_name, sample = CASES[0][:3]
    cls = getattr(importlib.import_module(f"tools.{tool}"), cls_name)
    http.reply(402, {"error": "No credits"})
    assert texts(run(cls, sample)) == ["HuntAPI error 402: Not enough credits. (No credits)"]


def test_timeout(http):
    if not CASES:
        pytest.skip("covered by the brand tests")
    tool, cls_name, sample = CASES[0][:3]
    cls = getattr(importlib.import_module(f"tools.{tool}"), cls_name)
    http.raise_error(requests.Timeout("slow"))
    assert texts(run(cls, sample)) == ["HuntAPI did not answer in time. Try again."]


import huntapi_api  # noqa: E402
from tools.download_audio import HuntAPIDownloadAudioTool  # noqa: E402
from tools.download_video import HuntAPIDownloadVideoTool  # noqa: E402

DONE = {
    "status": "CompletedJob",
    "progress": 100,
    "result": {"metadata": {"title": "Me at the zoo"}, "response": "https://s3.huntapi.com/videos/x.mp4"},
}


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(huntapi_api.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(huntapi_api.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now


def test_download_waits_for_the_link(http, clock):
    http.reply(200, {"job_id": "j1"})
    http.reply(200, {"status": "Running", "progress": 40})
    http.reply(200, DONE)
    messages = run(
        HuntAPIDownloadVideoTool, {"url": "https://youtu.be/x", "video_quality": "720p", "video_format": "mp4"}
    )
    assert http.calls[0]["url"] == BASE + "/v1/video/download"
    assert http.calls[0]["params"] == {"query": "https://youtu.be/x", "video_quality": "720p", "video_format": "mp4"}
    assert [c["url"] for c in http.calls[1:]] == [BASE + "/v1/jobs/j1"] * 2
    assert texts(messages) == ["Download link for Me at the zoo: https://s3.huntapi.com/videos/x.mp4"]
    assert [m.type.value for m in messages] == ["text", "link", "json"]
    assert jsons(messages)[0]["job_id"] == "j1"


def test_download_still_running_returns_the_job_id(http, clock):
    http.reply(200, {"job_id": "j2"})
    for _ in range(60):
        http.reply(200, {"status": "Running", "progress": 10})
    messages = run(HuntAPIDownloadAudioTool, {"url": "https://youtu.be/x"})
    assert "still running" in texts(messages)[0] and "j2" in texts(messages)[0]
    assert clock[0] >= 140


def test_download_failure(http, clock):
    http.reply(200, {"job_id": "j3"})
    http.reply(200, {"status": "Error", "error": "Private video"})
    assert (
        texts(run(HuntAPIDownloadAudioTool, {"url": "https://youtu.be/x"}))[0]
        == "The download failed (Error): Private video."
    )


def test_download_needs_a_url(http, clock):
    assert "is required" in texts(run(HuntAPIDownloadVideoTool, {}))[0]
    assert http.calls == []
