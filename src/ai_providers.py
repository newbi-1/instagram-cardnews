"""Buyer-owned AI caption helpers (BYOK) — thin HTTP, no heavy SDKs.

Providers (selectable in Settings):
  - gemini (Google)
  - openai
  - anthropic (Claude)
  - xai (Grok)
  - openrouter (optional gateway / DeepSeek etc.)

API keys stay in per-buyer settings (gitignored JSON) — never commit.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

PROVIDERS: list[dict[str, str]] = [
    {"id": "gemini", "label": "Google Gemini"},
    {"id": "openai", "label": "OpenAI GPT"},
    {"id": "anthropic", "label": "Anthropic Claude"},
    {"id": "xai", "label": "xAI Grok"},
    {"id": "openrouter", "label": "OpenRouter"},
]

PROVIDER_IDS = {p["id"] for p in PROVIDERS}

_SYSTEM = (
    "당신은 한국어 인스타그램 카드뉴스 본문 작성기입니다. "
    "짧고 읽기 쉬운 본문, 이모지 적당히, 해시태그 2~5개. "
    "과장·허위 금지. 마크다운 제목(#) 쓰지 마세요."
)


def provider_label(provider_id: str) -> str:
    for p in PROVIDERS:
        if p["id"] == provider_id:
            return p["label"]
    return provider_id or "(미선택)"


def mask_api_key(key: str, keep: int = 4) -> str:
    k = (key or "").strip()
    if not k:
        return ""
    if len(k) <= keep * 2:
        return k[:1] + "…" + k[-1:]
    return k[:keep] + "…" + k[-keep:]


def _http_json(
    url: str,
    *,
    method: str = "POST",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 45.0,
) -> tuple[bool, Any, str]:
    data = None
    hdrs = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return True, json.loads(raw) if raw else {}, ""
            except json.JSONDecodeError:
                return True, raw, ""
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            pass
        return False, None, f"HTTP {exc.code}: {err_body or exc.reason}"
    except urllib.error.URLError as exc:
        return False, None, f"네트워크 오류: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)


def _build_user_prompt(topic: str, headlines: list[str] | None) -> str:
    topic = (topic or "").strip() or "오늘 소식"
    heads = [h.strip() for h in (headlines or []) if h and str(h).strip()][:5]
    lines = [
        f"주제: {topic}",
        "",
        "위 주제로 인스타그램 피드에 올릴 카드뉴스 본문(캡션)을 한국어로 작성해 주세요.",
        "3~8문장 정도, 마지막에 해시태그.",
    ]
    if heads:
        lines.append("")
        lines.append("참고 뉴스 제목:")
        for h in heads:
            lines.append(f"- {h}")
    return "\n".join(lines)


def _extract_text_openai_style(data: Any) -> str:
    if not isinstance(data, dict):
        return str(data or "").strip()
    choices = data.get("choices") or []
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or {}
        if isinstance(msg, dict) and msg.get("content"):
            return str(msg["content"]).strip()
        if choices[0].get("text"):
            return str(choices[0]["text"]).strip()
    return ""


def _friendly_err(name: str, err: str) -> str:
    e = (err or "").lower()
    if "401" in e or "unauthorized" in e or ("invalid" in e and "key" in e):
        return f"{name} 키가 거부됐어요. 설정에서 키를 다시 붙여 넣어 주세요."
    if "429" in e or "rate" in e:
        return f"{name} 요청이 너무 많아요. 잠시 후 다시 시도해 주세요."
    if "402" in e or "quota" in e or "billing" in e or "credit" in e:
        return f"{name} 사용량·결제를 확인해 주세요."
    if "network" in e or "네트워크" in (err or ""):
        return f"{name}에 연결하지 못했어요. 인터넷 상태를 확인해 주세요."
    short = (err or "")[:180]
    return f"{name} 호출에 실패했어요. ({short})"


def generate_caption_with_provider(
    *,
    provider: str,
    api_key: str,
    topic: str,
    headlines: list[str] | None = None,
) -> tuple[bool, str, str]:
    """Return (ok, text_or_empty, error_ko)."""
    provider = (provider or "").strip().lower()
    api_key = (api_key or "").strip()
    if provider not in PROVIDER_IDS:
        return False, "", "AI 제공자를 설정에서 골라 주세요."
    if not api_key:
        return False, "", "AI API 키가 없어요. 설정에 본인 키를 넣어 주세요."

    user_prompt = _build_user_prompt(topic, headlines)

    if provider == "gemini":
        model = "gemini-2.0-flash"
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={urllib.parse.quote(api_key)}"
        )
        body = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{_SYSTEM}\n\n{user_prompt}"}]}
            ],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 800},
        }
        ok, data, err = _http_json(url, body=body)
        if not ok:
            return False, "", _friendly_err("Gemini", err)
        text = ""
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(
                str(p.get("text") or "") for p in parts if isinstance(p, dict)
            ).strip()
        except Exception:
            text = ""
        if not text:
            return False, "", "Gemini 응답이 비어 있어요. 모델·키 권한을 확인해 주세요."
        return True, text, ""

    if provider == "openai":
        ok, data, err = _http_json(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            body={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 800,
            },
        )
        if not ok:
            return False, "", _friendly_err("OpenAI", err)
        text = _extract_text_openai_style(data)
        if not text:
            return False, "", "OpenAI 응답이 비어 있어요. 모델·결제·키를 확인해 주세요."
        return True, text, ""

    if provider == "anthropic":
        ok, data, err = _http_json(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            body={
                "model": "claude-3-5-haiku-latest",
                "max_tokens": 800,
                "system": _SYSTEM,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
        if not ok:
            return False, "", _friendly_err("Claude", err)
        text = ""
        if isinstance(data, dict):
            for block in data.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += str(block.get("text") or "")
        text = text.strip()
        if not text:
            return False, "", "Claude 응답이 비어 있어요. 키·모델 이름을 확인해 주세요."
        return True, text, ""

    if provider == "xai":
        ok, data, err = _http_json(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            body={
                "model": "grok-2-latest",
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
            },
        )
        if not ok:
            return False, "", _friendly_err("Grok", err)
        text = _extract_text_openai_style(data)
        if not text:
            return False, "", "Grok 응답이 비어 있어요. 키·모델 권한을 확인해 주세요."
        return True, text, ""

    if provider == "openrouter":
        ok, data, err = _http_json(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://instagram-cardnews.local",
                "X-Title": "instagram-cardnews",
            },
            body={
                "model": "deepseek/deepseek-chat",
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        if not ok:
            return False, "", _friendly_err("OpenRouter", err)
        text = _extract_text_openai_style(data)
        if not text:
            return False, "", "OpenRouter 응답이 비어 있어요. 키·모델·크레딧을 확인해 주세요."
        return True, text, ""

    return False, "", "지원하지 않는 AI 제공자예요."
