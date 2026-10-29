"""web_search: Tavily when a key is set, DuckDuckGo otherwise — and on any Tavily failure."""

import io
import json

from yumii.tools import web_search_tool as ws

_DDG_HITS = [{"title": "DDG result", "url": "https://ddg.example", "snippet": "from duckduckgo"}]


def test_tavily_answers_when_keyed(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.setattr(ws, "_run_tavily", lambda q, n, k: (
        "It's sunny in Tokyo, 24°C.",
        [{"title": "Tokyo weather", "url": "https://w.example", "snippet": "Sunny, 24C"}],
    ))
    monkeypatch.setattr(ws, "_run_search", lambda q, n: (_ for _ in ()).throw(AssertionError("ddgs used")))

    out = ws.web_search.invoke({"query": "weather in Tokyo"})

    assert out.startswith("Quick answer: It's sunny in Tokyo")
    assert "Tokyo weather" in out


def test_tavily_failure_falls_back_to_duckduckgo(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-bad")

    def boom(q, n, k):
        raise OSError("401 Unauthorized")

    monkeypatch.setattr(ws, "_run_tavily", boom)
    monkeypatch.setattr(ws, "_run_search", lambda q, n: _DDG_HITS)

    out = ws.web_search.invoke({"query": "anything"})

    assert "DDG result" in out and "Quick answer" not in out
    assert "401" not in out  # never voice raw internals


def test_no_key_goes_straight_to_duckduckgo(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(ws, "_run_tavily", lambda *a: (_ for _ in ()).throw(AssertionError("tavily used")))
    monkeypatch.setattr(ws, "_run_search", lambda q, n: _DDG_HITS)

    assert "DDG result" in ws.web_search.invoke({"query": "anything"})


def test_tavily_request_shape(monkeypatch):
    seen = {}

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["auth"] = request.get_header("Authorization")
        seen["body"] = json.loads(request.data)
        return _Resp(json.dumps({
            "answer": "Forty-two.",
            "results": [{"title": "T", "url": "https://u", "content": "C"}],
        }).encode())

    monkeypatch.setattr(ws.urllib.request, "urlopen", fake_urlopen)

    answer, hits = ws._run_tavily("meaning of life", 5, "tvly-key")

    assert seen["url"] == "https://api.tavily.com/search"
    assert seen["auth"] == "Bearer tvly-key"
    assert seen["body"]["include_answer"] is True and seen["body"]["max_results"] == 5
    assert answer == "Forty-two."
    assert hits == [{"title": "T", "url": "https://u", "snippet": "C"}]
