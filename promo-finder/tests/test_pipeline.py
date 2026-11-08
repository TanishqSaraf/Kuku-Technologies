"""Run: python -m pytest -q  (needs the input pack at $PROMO_INPUT or ./data)"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from promo_finder.parse import load_dir, parse_text
from promo_finder.candidates import generate, _speech_at
from promo_finder import llm as L

DATA = os.getenv("PROMO_INPUT", str(Path(__file__).parents[1] / "data"))
pytestmark = pytest.mark.skipif(not Path(DATA).exists(), reason="input pack not present")


@pytest.fixture(scope="module")
def eps():
    return load_dir(DATA)


def test_parse_counts(eps):
    assert len(eps) >= 1
    assert all(e.events for e in eps)
    kinds = {ev.kind for e in eps for ev in e.events}
    assert {"dialogue", "camera"} <= kinds


def test_parser_handles_offscreen_and_tags():
    raw = '''EPISODE NUMBER: Episode 7
--- SCRIPT START ---
**MATRIARCH (O.S.) (Firm, Cold):**
Start: (00:01.00) | End: (00:02.50)
"Enough!"
'''
    ep = parse_text(raw)
    e = ep.events[0]
    assert (ep.ep, e.speaker, e.tags, e.text) == (7, "MATRIARCH", ["firm", "cold"], "Enough!")


def test_every_candidate_is_clean(eps):
    E = {e.ep: e for e in eps}
    ps = generate(eps)
    assert ps
    for p in ps:
        assert 20 <= p.duration <= 60, p.segments
        for s in p.segments:
            assert not _speech_at(E[s.ep], s.start) and not _speech_at(E[s.ep], s.end), "cut splits a line"


class _Stub(BaseHTTPRequestHandler):
    reply = {}
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Stub.seen.append((self.path, self.headers.get("Authorization"), body["model"]))
        out = {"choices": [{"message": {"content": "```json\n" + json.dumps(_Stub.reply) + "\n```"}}],
               "usage": {"prompt_tokens": 100, "completion_tokens": 20}}
        data = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_llm_http_path_and_guardrail(eps, tmp_path, monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("PROMO_LLM_BASE_URL", f"http://127.0.0.1:{srv.server_port}/v1")
    monkeypatch.setenv("PROMO_LLM_API_KEY", "test-key")
    monkeypatch.chdir(tmp_path)
    E = {e.ep: e for e in eps}
    p = sorted(generate(eps), key=lambda x: -x.rule_score)[0]
    before = [(s.start, s.end) for s in p.segments]
    # the model invents IDs and a 300 s clip -> must be ignored, scores still read
    _Stub.reply = {"hook": 8, "cliffhanger": 7, "standalone": 6, "overall": 7.5,
                   "start_id": "E99-0001", "end_id": "E99-9999", "hook_id": "nope", "cliff_id": "nope",
                   "why": "test", "problems": []}
    client = L.Client("openai_compat", model="stub-model")
    out = L.review(client, p, E, "Show")
    assert [(s.start, s.end) for s in out.segments] == before
    assert out.llm["ok"] and out.llm["score"] == 75.0
    path, auth, model = _Stub.seen[-1]
    assert path == "/v1/chat/completions" and auth == "Bearer test-key" and model == "stub-model"
    assert client.usage["in_tokens"] == 100
    srv.shutdown()
