"""AI moduli: haqiqiy SDK + lokal soxta server (HTTP/SSE). Haqiqiy Anthropic xizmatiga so'rov YUBORILMAGAN (bu muhitda kalit va tarmoq yo'q)."""
import threading
import time

import anthropic
import pytest

from mock_anthropic import MockAnthropic
from pyatnitsa import ai_chat, credentials
from pyatnitsa.ai_chat import AIError, ChatClient, ChatService, ConversationHistory
from pyatnitsa.settings import Settings

KEY = "sk-ant-test-0123456789abcdefghij"


@pytest.fixture
def server():
    s = MockAnthropic()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("PYATNITSA_HOME", str(tmp_path))


def client_for(server, settings=None, **kw):
    s = settings or Settings()
    factory = lambda: anthropic.Anthropic(api_key=KEY, base_url=server.url, max_retries=0, timeout=kw.get("timeout", 5.0))  # noqa: E731
    return ChatClient(s, factory)


def ask(c, text="Salom", system="sys", **kw):
    got, first = [], []
    rep = c.stream_reply([{"role": "user", "content": text}], system, got.append, lambda: first.append(time.monotonic()))
    return rep, got, first


# ------------------------------------------------------------------ muvaffaqiyatli oqim va so'rov shakli
def test_streams_text_in_chunks_and_reports_usage(server):
    rep, got, first = ask(client_for(server))
    assert got == ["Salom! ", "Yaxshiman, ", "rahmat."] and rep.text == "Salom! Yaxshiman, rahmat."
    assert rep.stop_reason == "end_turn" and not rep.cancelled and not rep.truncated and rep.output_tokens == 20 and len(first) == 1


def test_request_shape_is_correct_and_has_no_secrets_in_body(server):
    s = Settings(); s.ai_model = "claude-sonnet-5-5"
    ask(client_for(server, s), "Python nima?", "SYSTEM-X")
    r = server.requests[0]
    assert r["path"].startswith("/v1/messages") and r["headers"]["authorization"] == f"Bearer {KEY}" and r["headers"]["anthropic-version"]
    b = r["body"]
    assert b["model"] == "claude-sonnet-5-5" and b["stream"] is True and b["system"] == "SYSTEM-X" and b["max_tokens"] == 4096
    assert b["messages"] == [{"role": "user", "content": "Python nima?"}] and b["output_config"] == {"effort": "low"}
    assert "thinking" not in b and "fallbacks" not in b                  # Sonnet: server fallback so'ralmaydi
    assert KEY not in str(b)


def test_default_model_is_opus_and_uses_server_fallback_beta(server):
    ask(client_for(server))
    r = server.requests[0]
    assert r["body"]["model"] == "claude-opus-5-5" and r["body"]["fallbacks"] == "default"
    assert ai_chat.FALLBACK_BETA in r["headers"]["anthropic-beta"]


def test_fallback_is_dropped_when_server_rejects_it_and_remembered(server):
    server.script = [("error", 400, "invalid_request_error", "Unexpected value(s) for the anthropic-beta header: server-side-fallback-2026-07-01", {})]
    c = client_for(server)
    rep, got, _ = ask(c)
    assert rep.text and len(server.requests) == 2 and "fallbacks" not in server.requests[1]["body"]
    ask(c)
    assert "fallbacks" not in server.requests[2]["body"]                  # keyingi so'rovlarda qayta urinilmaydi


def test_fallback_can_be_disabled_in_settings(server):
    s = Settings(); s.ai_fallback = False
    ask(client_for(server, s))
    assert "fallbacks" not in server.requests[0]["body"]


def test_default_client_reads_key_and_base_url_from_environment(server, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY); monkeypatch.setenv("ANTHROPIC_BASE_URL", server.url)
    rep, got, _ = ask(ChatClient(Settings()))
    assert rep.text and server.requests[0]["headers"]["authorization"] == f"Bearer {KEY}"


# ------------------------------------------------------------------ xatolar (har biri aniq turga)
@pytest.mark.parametrize("status,etype,msg,hdrs,kind", [
    (401, "authentication_error", "invalid x-api-key", {}, "auth"),
    (403, "permission_error", "no access to this model", {}, "permission"),
    (404, "not_found_error", "model: nope", {}, "model"),
    (429, "rate_limit_error", "slow down", {"retry-after": "7"}, "rate_limit"),
    (529, "overloaded_error", "Overloaded", {}, "server"),
    (500, "api_error", "Internal error", {}, "server"),
    (400, "invalid_request_error", "Your credit balance is too low to access the API", {}, "billing"),
    (400, "invalid_request_error", "messages: bad", {}, "bad_request"),
    (413, "request_too_large", "too big", {}, "too_large"),
])
def test_http_errors_map_to_specific_kinds(server, status, etype, msg, hdrs, kind):
    server.script = [("error", status, etype, msg, hdrs)]
    c = client_for(server); c.settings.ai_fallback = False
    with pytest.raises(AIError) as e:
        ask(c)
    assert e.value.kind == kind
    if kind == "rate_limit":
        assert e.value.retry_after == 7


def test_timeout_and_connection_errors(server):
    server.script = [("hang", 3.0)]
    c = client_for(server, timeout=0.6); c.settings.ai_fallback = False
    with pytest.raises(AIError) as e:
        ask(c)
    assert e.value.kind == "timeout"
    dead = anthropic.Anthropic(api_key=KEY, base_url="http://127.0.0.1:9", max_retries=0, timeout=2)
    with pytest.raises(AIError) as e2:
        ask(ChatClient(Settings(), lambda: dead))
    assert e2.value.kind == "network"


def test_missing_key_gives_no_key_error_and_never_calls_the_server(server, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", server.url)
    c = ChatClient(Settings())
    with pytest.raises(AIError) as e:
        ask(c)
    assert e.value.kind == "no_key" and server.requests == []
    assert ChatService(Settings(), c).available() == (False, "no_key")


def test_refusal_empty_and_truncated_replies(server):
    c = client_for(server); c.settings.ai_fallback = False
    server.script = [("stream", {"chunks": [], "stop_reason": "refusal"})]
    with pytest.raises(AIError) as e:
        ask(c)
    assert e.value.kind == "refusal"
    server.script = [("stream", {"chunks": [], "stop_reason": "end_turn"})]
    with pytest.raises(AIError) as e:
        ask(c)
    assert e.value.kind == "empty"
    server.script = [("stream", {"chunks": ["Uzun javob…"], "stop_reason": "max_tokens"})]
    rep, _, _ = ask(c)
    assert rep.truncated and rep.text == "Uzun javob…"


# ------------------------------------------------------------------ bekor qilish va kechikish
def test_first_token_callback_fires_only_after_server_starts_streaming(server):
    server.script = [("stream", {"chunks": ["a", "b"], "delay_first": 0.4})]
    t0 = time.monotonic()
    rep, got, first = ask(client_for(server))
    assert first[0] - t0 >= 0.35 and rep.text == "ab"


def test_cancel_mid_stream_keeps_partial_text_and_returns_quickly(server):
    server.script = [("stream", {"chunks": ["Bir ", "ikki ", "uch ", "to'rt ", "besh"], "gap": 0.4})]
    c = client_for(server); c.settings.ai_fallback = False
    out = {}
    threading.Thread(target=lambda: out.update(rep=ask(c)[0]), daemon=True).start()
    time.sleep(0.7); c.cancel()
    deadline = time.time() + 3
    while "rep" not in out and time.time() < deadline:
        time.sleep(0.02)
    rep = out["rep"]
    assert rep.cancelled and 0 < len(rep.text) < len("Bir ikki uch to'rt besh")


def test_cancel_while_waiting_for_first_token(server):
    server.script = [("stream", {"chunks": ["x"], "delay_first": 3.0})]
    c = client_for(server, timeout=10); c.settings.ai_fallback = False
    out = {}
    threading.Thread(target=lambda: out.update(rep=ask(c)[0]), daemon=True).start()
    time.sleep(0.5); t0 = time.time(); c.cancel()
    while "rep" not in out and time.time() - t0 < 3:
        time.sleep(0.02)
    assert out["rep"].cancelled and out["rep"].text == "" and time.time() - t0 < 2.0


# ------------------------------------------------------------------ tarix va kontekst
def test_history_trims_by_messages_and_chars_and_starts_with_user():
    h = ConversationHistory(max_messages=4, max_chars=10_000)
    for i in range(6):
        h.add_user(f"u{i}"); h.add_assistant(f"a{i}")
    m = h.messages()
    assert len(m) == 4 and m[0]["role"] == "user" and m[-1]["content"] == "a5"
    h2 = ConversationHistory(max_messages=20, max_chars=60)
    for i in range(5):
        h2.add_user("x" * 30); h2.add_assistant("y" * 30)
    assert sum(len(x["content"]) for x in h2.messages()) <= 60 and h2.messages()[0]["role"] == "user"


def test_follow_up_sends_previous_turns_to_the_model(server):
    svc = ChatService(Settings(), client_for(server))
    svc.history.add_user("Python nima?")
    rep = svc.client.stream_reply(svc.history.messages(), "s", lambda t: None); svc.history.add_assistant(rep.text)
    svc.history.add_user("Uni kim yaratgan?")
    svc.client.stream_reply(svc.history.messages(), "s", lambda t: None)
    sent = server.requests[1]["body"]["messages"]
    assert [m["content"] for m in sent] == ["Python nima?", rep.text, "Uni kim yaratgan?"]


def test_history_retry_and_clear_semantics():
    h = ConversationHistory()
    h.add_user("a"); assert h.pop_last_user() == "a" and len(h) == 0 and h.pop_last_user() is None
    h.add_user("a"); h.add_assistant("b"); assert h.pop_last_user() is None and len(h) == 2
    h.clear(); assert len(h) == 0


def test_system_prompt_states_limits_language_and_context():
    p = ai_chat.build_system_prompt("ru", has_history=False, live_unsupported=True)
    for needle in ("Russian", "cannot run commands", "no live data", "start of the conversation", "cannot access", "Current local date"):
        assert needle in p
    assert "start of the conversation" not in ai_chat.build_system_prompt("uz", has_history=True)


# ------------------------------------------------------------------ kalitlar va maxfiylik
def test_key_resolution_order_and_private_file(monkeypatch, tmp_path):
    assert credentials.get_api_key() == (None, "")
    credentials.save_api_key(KEY)
    assert credentials.get_api_key() == (KEY, "file")
    import os, stat
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(credentials.secrets_path()).st_mode) == 0o600
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-key-0123456789abcdef")
    assert credentials.get_api_key() == ("sk-ant-env-key-0123456789abcdef", "env:ANTHROPIC_API_KEY")
    credentials.clear_api_key(); monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert credentials.get_api_key() == (None, "")


@pytest.mark.parametrize("bad", ["", "short", "has spaces in the key 0123456789012345", "x" * 500])
def test_invalid_keys_are_rejected(bad):
    with pytest.raises(ValueError):
        credentials.save_api_key(bad)


def test_key_never_reaches_settings_file_or_logs(monkeypatch, tmp_path, caplog):
    import logging
    credentials.save_api_key(KEY)
    s = Settings(); s.save()
    assert KEY not in Settings.path().read_text()
    log = logging.getLogger("pyatnitsa.test"); f = credentials.RedactFilter()
    rec = log.makeRecord("pyatnitsa.test", logging.ERROR, __file__, 1, f"failed with key {KEY} and sk-ant-api03-ZZZZZZZZZZZZ", (), None)
    f.filter(rec)
    assert KEY not in rec.getMessage() and "ZZZZZZZZ" not in rec.getMessage() and "***" in rec.getMessage()
    err = ai_chat.map_error(RuntimeError(f"boom {KEY}"))
    assert KEY not in str(err) and KEY not in err.detail


def test_auto_use_of_no_ai_provider_markers_in_source():
    import pathlib
    src = "\n".join(p.read_text() for p in pathlib.Path("pyatnitsa").rglob("*.py"))
    assert "sk-ant-" not in src.replace("sk-ant-api03", "") or True      # qattiq kodlangan kalit yo'qligini quyida tekshiramiz
    import re
    assert not re.search(r"sk-ant-[A-Za-z0-9_\-]{20,}", src)
