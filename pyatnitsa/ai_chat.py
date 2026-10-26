"""Suhbat AI moduli (qayta ishlatiladigan, GUI'ga bog'liq emas): suhbat tarixi, tizim ko'rsatmasi, oqimli so'rov (Anthropic SDK),
xatolarni turlarga ajratish va bekor qilish. AI faqat MATN qaytaradi — undan hech qachon buyruq bajarilmaydi."""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from . import credentials

log = logging.getLogger("pyatnitsa.ai")

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-fable-5")   # serverdagi qayta urinishni qo'llaydigan modellar
LANG_NAMES = {"uz": "Uzbek (Latin script)", "ru": "Russian", "en": "English"}


class AIError(Exception):
    """Foydalanuvchiga tushuntiriladigan AI xatosi. `kind` — i18n kaliti qismi (ai.err.<kind>)."""
    def __init__(self, kind: str, detail: str = "", retry_after: float | None = None):
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind, self.detail, self.retry_after = kind, detail, retry_after

    @property
    def retryable(self) -> bool:
        return self.kind in ("rate_limit", "timeout", "network", "server", "empty", "unknown")


@dataclass
class Reply:
    text: str
    stop_reason: str | None = None
    model: str = ""
    seconds: float = 0.0
    cancelled: bool = False
    truncated: bool = False             # max_tokens'ga yetib kesilgan
    fallback_used: bool = False
    input_tokens: int = 0
    output_tokens: int = 0


# ----------------------------------------------------------------------------- suhbat tarixi
class ConversationHistory:
    """Joriy sessiya tarixi (faqat xotirada). Hajm cheklovlari sozlanadi; yuborishda eng yangi xabarlar saqlanadi."""

    def __init__(self, max_messages: int = 16, max_chars: int = 12000):
        self.max_messages, self.max_chars = max_messages, max_chars
        self._m: list[dict] = []

    def __len__(self) -> int:
        return len(self._m)

    def add_user(self, text: str) -> None:
        self._m.append({"role": "user", "content": text})

    def add_assistant(self, text: str) -> None:
        self._m.append({"role": "assistant", "content": text})

    def pop_last_user(self) -> str | None:
        """Muvaffaqiyatsiz so'rovdan keyin oxirgi foydalanuvchi xabarini olib tashlaydi (qayta urinishda qayta qo'shiladi)."""
        if self._m and self._m[-1]["role"] == "user":
            return self._m.pop()["content"]
        return None

    def clear(self) -> None:
        self._m.clear()

    def messages(self) -> list[dict]:
        """API'ga yuboriladigan xabarlar: oxirgi `max_messages` ta va `max_chars` belgidan oshmaydigan, user'dan boshlanadigan to'plam."""
        msgs = self._m[-self.max_messages:]
        while len(msgs) > 1 and sum(len(m["content"]) for m in msgs) > self.max_chars:
            msgs = msgs[1:]
        while msgs and msgs[0]["role"] != "user":
            msgs = msgs[1:]
        return [dict(m) for m in msgs]


# ----------------------------------------------------------------------------- tizim ko'rsatmasi
def build_system_prompt(lang_hint: str = "uz", has_history: bool = False, live_unsupported: bool = False, now: datetime | None = None) -> str:
    now = now or datetime.now()
    p = (
        "You are ПЯТНИЦА (Pyatnitsa), a friendly voice-and-text assistant inside a desktop application on the user's Windows PC.\n"
        "LANGUAGE: reply in the language of the user's latest message - Uzbek (Latin script), Russian, or English. If the user mixes "
        "languages, reply in Uzbek unless they ask otherwise. If they explicitly ask for a language, use it. "
        f"The latest message looks like: {LANG_NAMES.get(lang_hint, 'Uzbek (Latin script)')}.\n"
        "STYLE: natural, warm and concise. Your answers may be read aloud, so prefer short paragraphs. Use a list or a code block only when it "
        "genuinely helps. Avoid headings, tables and emojis.\n"
        "CONTEXT: use the conversation so far to resolve follow-ups (\"it\", \"uni\", \"он\", \"misol ber\") without asking which topic is meant, "
        "when it is clear. Only rely on what is in this conversation; never claim to remember anything else.\n"
        "LIMITS: you cannot run commands, open programs, read files or browse the internet, and you must never claim that you did. The app executes "
        "computer commands separately when the user says them, e.g. \"Open Chrome\", \"Chrome'ni och\", \"Открой Chrome\". If the user wants an action "
        "done, tell them to say it as a short command. The app can also show the USD rate, weather, time and PC status when asked.\n"
        "LIVE DATA: you have no live data. For news, prices, scores, weather or anything that changes, say you cannot look it up here; if you answer "
        "from memory, say it may be outdated. Do not invent current facts.\n"
        "TROUBLESHOOTING (e.g. why a program does not open): list the likely causes and concrete steps, clearly as possibilities, not diagnoses.\n"
        "ENGLISH PRACTICE: when asked to practise English, act as a friendly tutor - speak simple English at the learner's level, gently correct "
        "mistakes, ask one question at a time, and use the learner's own language only to explain when needed.\n"
        f"Current local date and time: {now:%Y-%m-%d %H:%M}.\n"
    )
    p += ("This is the start of the conversation - there is no earlier discussion to continue.\n" if not has_history else "")
    if live_unsupported:
        p += "The user's latest message needs live data you cannot access. Say so plainly; do not invent it; you may add general background labelled as possibly outdated.\n"
    return p


# ----------------------------------------------------------------------------- xatolarni turlarga ajratish
def map_error(e: BaseException) -> AIError:
    import anthropic
    if isinstance(e, AIError):
        return e
    text = credentials.redact(str(e))[:300]
    if isinstance(e, TypeError) and "authentication" in str(e).lower():
        return AIError("no_key", text)
    if isinstance(e, anthropic.APITimeoutError):
        return AIError("timeout", text)
    if isinstance(e, anthropic.APIConnectionError):
        return AIError("network", text)
    if isinstance(e, anthropic.AuthenticationError):
        return AIError("auth", text)
    if isinstance(e, anthropic.PermissionDeniedError):
        return AIError("permission", text)
    if isinstance(e, anthropic.RateLimitError):
        ra = None
        try:
            ra = float(e.response.headers.get("retry-after", ""))
        except (ValueError, AttributeError, TypeError):
            pass
        return AIError("rate_limit", text, ra)
    if isinstance(e, anthropic.NotFoundError):
        return AIError("model", text)
    too_large = getattr(anthropic, "RequestTooLargeError", None)
    if too_large and isinstance(e, too_large):
        return AIError("too_large", text)
    if isinstance(e, anthropic.BadRequestError):
        low = text.lower()
        return AIError("billing" if "credit" in low or "billing" in low else "bad_request", getattr(e, "message", text)[:300])
    server_classes = tuple(c for c in (getattr(anthropic, n, None) for n in ("OverloadedError", "InternalServerError", "ServiceUnavailableError")) if c)
    if server_classes and isinstance(e, server_classes):
        return AIError("server", text)
    if isinstance(e, anthropic.APIStatusError):
        return AIError("server" if e.status_code >= 500 else "bad_request", text)
    return AIError("unknown", f"{type(e).__name__}: {text}")


# ----------------------------------------------------------------------------- mijoz
class ChatClient:
    """Anthropic Messages API (oqimli). Bitta so'rov — bitta oqim; `cancel()` boshqa oqimdan chaqirilishi mumkin."""

    def __init__(self, settings, client_factory=None):
        self.settings = settings
        self._factory = client_factory
        self._lock = threading.Lock()
        self._active = None
        self._active_rid = 0
        self._rid = 0
        self._cancel = threading.Event()
        self._fallback_ok = True

    # ---- sozlamalar
    @property
    def model(self) -> str:
        return (self.settings.ai_model or DEFAULT_MODEL).strip()

    def key_status(self) -> tuple[bool, str]:
        key, source = credentials.get_api_key()
        return bool(key), source

    def _client(self):
        import anthropic
        if self._factory:
            return self._factory()
        key, _ = credentials.get_api_key()
        kw = dict(timeout=float(self.settings.ai_timeout_s), max_retries=2)
        return anthropic.Anthropic(api_key=key, **kw) if key else anthropic.Anthropic(**kw)

    # ---- bekor qilish
    def cancel(self) -> None:
        self._cancel.set()
        self._close_active()

    # ---- so'rov
    def stream_reply(self, messages: list[dict], system: str, on_text, on_first=None) -> Reply:
        """Matnni qismlab `on_text`ga beradi. Xatoda AIError ko'taradi; bekor qilinsa — `Reply(cancelled=True)` (qisman matn bilan)."""
        self._cancel.clear()
        t0 = time.monotonic()
        use_fb = self._fallback_ok and self.settings.ai_fallback and self.model in FALLBACK_MODELS
        for attempt in (1, 2):
            parts: list[str] = []
            try:
                return self._once(messages, system, on_text, on_first, parts, use_fb, t0)
            except BaseException as e:  # noqa: BLE001
                if self._cancel.is_set():
                    return Reply("".join(parts), cancelled=True, model=self.model, seconds=time.monotonic() - t0)
                err = map_error(e)
                if use_fb and attempt == 1 and err.kind == "bad_request" and any(w in err.detail.lower() for w in ("fallback", "beta")):
                    log.warning("Server fallback rad etildi; usiz qayta uriniladi")
                    self._fallback_ok, use_fb = False, False
                    continue
                raise err from e
        raise AIError("unknown")

    def _once(self, messages, system, on_text, on_first, parts: list[str], use_fb: bool, t0: float) -> Reply:
        """O'qish alohida oqimda bajariladi: bekor qilinganda (hatto birinchi token kutilayotganda ham) DARHOL qaytadi."""
        client = self._client()
        kw = dict(model=self.model, max_tokens=int(self.settings.ai_max_tokens), system=system, messages=messages,
                  output_config={"effort": self.settings.ai_effort})
        cm = (client.beta.messages.stream(**kw, betas=[FALLBACK_BETA], fallbacks="default") if use_fb else client.messages.stream(**kw))
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._rid += 1
            rid = self._rid

        def reader():
            try:
                with cm as stream:
                    with self._lock:
                        self._active, self._active_rid = stream, rid
                    try:
                        for chunk in stream.text_stream:
                            q.put(("chunk", chunk))
                        q.put(("final", stream.get_final_message()))
                    finally:
                        with self._lock:
                            if self._active_rid == rid:
                                self._active = None
            except BaseException as e:  # noqa: BLE001
                q.put(("err", e))

        threading.Thread(target=reader, name="ai-reader", daemon=True).start()
        first, final = True, None
        while final is None:
            try:
                kind, val = q.get(timeout=0.05)
            except queue.Empty:
                if self._cancel.is_set():
                    self._close_active()
                    return Reply("".join(parts), cancelled=True, model=self.model, seconds=time.monotonic() - t0)
                continue
            if self._cancel.is_set():
                self._close_active()
                return Reply("".join(parts), cancelled=True, model=self.model, seconds=time.monotonic() - t0)
            if kind == "chunk":
                if first:
                    first = False
                    if on_first:
                        on_first()
                parts.append(val)
                on_text(val)
            elif kind == "final":
                final = val
            else:
                raise val
        text = "".join(parts)
        stop = getattr(final, "stop_reason", None)
        usage = getattr(final, "usage", None)
        fb = any(getattr(it, "type", "") == "fallback_message" for it in (getattr(usage, "iterations", None) or []))
        if stop == "refusal" and not text.strip():
            raise AIError("refusal", str(getattr(final, "stop_details", "") or ""))
        if not text.strip():
            raise AIError("empty", f"stop_reason={stop}")
        return Reply(text, stop, getattr(final, "model", self.model), time.monotonic() - t0, truncated=(stop == "max_tokens"), fallback_used=fb,
                     input_tokens=getattr(usage, "input_tokens", 0) or 0, output_tokens=getattr(usage, "output_tokens", 0) or 0)

    def _close_active(self) -> None:
        with self._lock:
            stream = self._active
        if stream is not None:
            try:
                stream.close()
            except Exception:  # noqa: BLE001
                pass

    def test_connection(self) -> Reply:
        """Kichik so'rov bilan kalit/model/ulanishni tekshiradi."""
        got: list[str] = []
        return self.stream_reply([{"role": "user", "content": "Reply with the single word: OK"}], "You are a connectivity test. Answer with one word.", got.append)


# ----------------------------------------------------------------------------- xizmat (tarix + mijoz)
class ChatService:
    def __init__(self, settings, client: ChatClient | None = None):
        self.settings = settings
        self.client = client or ChatClient(settings)
        self.history = ConversationHistory(settings.ai_context_messages)

    def available(self) -> tuple[bool, str]:
        """(tayyormi, sabab_kaliti): 'disabled' | 'no_key'."""
        if not self.settings.ai_enabled:
            return False, "disabled"
        ok, _ = self.client.key_status()
        return (True, "") if ok else (False, "no_key")

    def apply_settings(self) -> None:
        self.history.max_messages = max(2, int(self.settings.ai_context_messages))

    def cancel(self) -> None:
        self.client.cancel()
