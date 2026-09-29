"""Tests for scripts/update_build_log.py (the dashboard's generated PR log)."""

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("update_build_log", ROOT / "scripts" / "update_build_log.py")
ubl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ubl)

PAGE = """head
  /* prs:start (x) */
  var PRS = [
    {n:1, title:"old", date:"2020-01-01"}
  ];
  /* prs:end */
  /* prs-ko:start (x) */
  var PR_KO = {
    1:"옛 제목"
  };
  /* prs-ko:end */
tail
"""


def pr(n, title="T", body=None, merged="2026-09-29T10:00:00Z"):
    return {"number": n, "title": title, "merged_at": merged, "body": body}


def test_korean_title_from_body():
    assert ubl.korean_title_from_body("## Summary\nKorean title: 새 제목\n- x") == "새 제목"
    assert ubl.korean_title_from_body("한글 제목： 다른 제목  ") == "다른 제목"
    assert ubl.korean_title_from_body("no marker here") is None
    assert ubl.korean_title_from_body(None) is None
    assert ubl.korean_title_from_body("Korean title:   ") is None  # empty value is not a title


def test_stored_title_wins_and_is_never_retranslated():
    calls = []
    titles = ubl.resolve_korean_titles(
        [pr(1, body="Korean title: 본문 제목")], {"1": "저장된 제목"}, translate=lambda t: calls.append(t)
    )
    assert titles == {"1": "저장된 제목"} and calls == []


def test_body_marker_beats_translation():
    calls = []
    titles = ubl.resolve_korean_titles([pr(2, body="Korean title: 본문 제목")], {}, translate=lambda t: calls.append(t))
    assert titles == {"2": "본문 제목"} and calls == []


def test_translation_is_the_last_resort_and_failure_leaves_no_entry():
    assert ubl.resolve_korean_titles([pr(3, "Fix it")], {}, translate=lambda t: "고치기") == {"3": "고치기"}
    assert ubl.resolve_korean_titles([pr(3, "Fix it")], {}, translate=lambda t: None) == {}


def test_update_page_rewrites_both_blocks_and_is_idempotent():
    prs = [pr(2, 'Say "hi"'), pr(1, "old", merged="2020-01-01T00:00:00Z")]
    titles = {"1": "옛 제목", "2": "안녕"}
    out = ubl.update_page(PAGE, prs, titles)
    assert '{n:1, title:"old", date:"2020-01-01"},' in out
    assert '{n:2, title:"Say \\"hi\\"", date:"2026-09-29"}' in out
    assert '2:"안녕"' in out and out.startswith("head") and out.endswith("tail\n")
    assert ubl.update_page(out, prs, titles) == out


def test_update_page_needs_markers():
    with pytest.raises(SystemExit):
        ubl.update_page("no markers", [], {})


def fake_anthropic(monkeypatch, text="한국어 제목", stop_reason="end_turn", error=False):
    mod = types.ModuleType("anthropic")

    class APIError(Exception):
        pass

    class Client:
        class messages:
            @staticmethod
            def create(**kwargs):
                Client.kwargs = kwargs
                if error:
                    raise APIError("boom")
                block = types.SimpleNamespace(type="text", text=text)
                return types.SimpleNamespace(stop_reason=stop_reason, content=[block])

    mod.Anthropic, mod.APIError, mod.Client = Client, APIError, Client
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    return Client


def test_translate_title_without_a_key_does_nothing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert ubl.translate_title("Anything") is None


def test_translate_title_cleans_the_reply(monkeypatch):
    client = fake_anthropic(monkeypatch, text='  "Grafana 대시보드 추가"\n설명은 무시  ')
    assert ubl.translate_title("Add Grafana dashboard") == "Grafana 대시보드 추가"
    assert client.kwargs["model"] == "claude-opus-5-5"
    assert "Add Grafana dashboard" in client.kwargs["messages"][0]["content"]


def test_translate_title_survives_refusals_and_api_errors(monkeypatch):
    fake_anthropic(monkeypatch, stop_reason="refusal")
    assert ubl.translate_title("x") is None
    fake_anthropic(monkeypatch, error=True)
    assert ubl.translate_title("x") is None


def test_main_end_to_end(tmp_path, monkeypatch):
    page, ko, data = tmp_path / "page.html", tmp_path / "ko.json", tmp_path / "prs.json"
    page.write_text(PAGE, encoding="utf-8")
    ko.write_text(json.dumps({"1": "옛 제목"}, ensure_ascii=False), encoding="utf-8")
    data.write_text(json.dumps([pr(1, "old"), pr(2, "New", body="Korean title: 새 것")]), encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    argv = ["x", "--from-json", str(data), "--page", str(page), "--ko-file", str(ko)]
    monkeypatch.setattr(sys, "argv", argv + ["--check"])
    assert ubl.main() == 1  # stale, nothing written
    assert json.loads(ko.read_text(encoding="utf-8")) == {"1": "옛 제목"}
    monkeypatch.setattr(sys, "argv", argv)
    assert ubl.main() == 0
    assert json.loads(ko.read_text(encoding="utf-8")) == {"1": "옛 제목", "2": "새 것"}
    monkeypatch.setattr(sys, "argv", argv + ["--check"])
    assert ubl.main() == 0
