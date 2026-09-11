"""발행: dry-run 기본 + 공식 Meta Graph API 경로."""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

GRAPH_FACEBOOK = "https://graph.facebook.com/v21.0"
GRAPH_INSTAGRAM = "https://graph.instagram.com/v21.0"


@dataclass
class PublishResult:
    ok: bool
    dry_run: bool
    message: str
    media_ids: list[str]
    raw: dict[str, Any] | None = None


def has_ig_credentials() -> bool:
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    user_id = os.getenv("IG_USER_ID", "").strip()
    return bool(token and user_id)


def graph_base_for_token(token: str) -> str:
    """Instagram Login tokens (IG…) use graph.instagram.com; Facebook (EAA…) use graph.facebook.com."""
    t = (token or "").strip()
    if t.startswith("IG"):
        return GRAPH_INSTAGRAM
    return GRAPH_FACEBOOK


def _png_to_jpeg_bytes(path: Path, quality: int = 92) -> bytes:
    from PIL import Image

    with Image.open(path) as im:
        rgb = im.convert("RGB")
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()


def upload_temp_public_image(path: Path) -> str:
    """Upload local image to a temporary public HTTPS host; return URL.

    Tries litterbox.catbox.moe, 0x0.st, then uguu.se. Prefers JPEG for IG compatibility.
    """
    path = Path(path)
    jpeg_bytes = _png_to_jpeg_bytes(path) if path.suffix.lower() == ".png" else path.read_bytes()
    filename = path.stem + ".jpg"

    errors: list[str] = []

    # litterbox.catbox.moe — temporary (1h–72h)
    try:
        r = requests.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": "24h"},
            files={"fileToUpload": (filename, jpeg_bytes, "image/jpeg")},
            timeout=90,
        )
        if r.status_code == 200 and r.text.strip().startswith("https://"):
            return r.text.strip()
        errors.append(f"litterbox: HTTP {r.status_code} {r.text[:200]}")
    except requests.RequestException as e:
        errors.append(f"litterbox: {e}")

    # 0x0.st fallback
    try:
        r = requests.post(
            "https://0x0.st",
            files={"file": (filename, jpeg_bytes, "image/jpeg")},
            data={"expires": "24"},
            timeout=90,
        )
        if r.status_code == 200 and r.text.strip().startswith("https://"):
            return r.text.strip()
        errors.append(f"0x0.st: HTTP {r.status_code} {r.text[:200]}")
    except requests.RequestException as e:
        errors.append(f"0x0.st: {e}")

    # uguu.se — temporary direct HTTPS JPEG (works when catbox/0x0 TLS fails)
    try:
        r = requests.post(
            "https://uguu.se/upload",
            files={"files[]": (filename, jpeg_bytes, "image/jpeg")},
            timeout=90,
        )
        if r.status_code == 200:
            data = r.json()
            files = data.get("files") or []
            if data.get("success") and files and str(files[0].get("url", "")).startswith("https://"):
                return str(files[0]["url"])
            errors.append(f"uguu.se: {str(data)[:200]}")
        else:
            errors.append(f"uguu.se: HTTP {r.status_code} {r.text[:200]}")
    except (requests.RequestException, ValueError) as e:
        errors.append(f"uguu.se: {e}")

    raise RuntimeError("임시 공개 URL 업로드 실패: " + " | ".join(errors))


def resolve_image_url(path: Path) -> str:
    """Resolve public HTTPS image_url: sidecar .url → IG_IMAGE_BASE_URL → temp upload."""
    path = Path(path)
    sidecar = path.with_suffix(".url")
    base = os.getenv("IG_IMAGE_BASE_URL", "").rstrip("/")
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8").strip()
    if base:
        return f"{base}/{path.name}"
    return upload_temp_public_image(path)



def wait_for_container_ready(
    graph_base: str,
    creation_id: str,
    token: str,
    *,
    timeout_sec: int = 120,
    interval_sec: float = 3.0,
) -> dict[str, Any]:
    """Poll container status_code until FINISHED or ERROR/timeout."""
    import time

    deadline = time.time() + timeout_sec
    last: dict[str, Any] = {}
    while time.time() < deadline:
        r = requests.get(
            f"{graph_base}/{creation_id}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=30,
        )
        last = r.json() if r.content else {"http_status": r.status_code}
        code = str(last.get("status_code") or "")
        if code == "FINISHED":
            return last
        if code in {"ERROR", "EXPIRED"}:
            return last
        time.sleep(interval_sec)
    last["_wait_timeout"] = True
    return last


def publish_carousel(
    image_paths: list[Path],
    caption: str,
    *,
    dry_run: bool = True,
) -> PublishResult:
    """캐러셀 발행. dry_run=True 또는 자격증명 없으면 stub."""
    paths = [Path(p) for p in image_paths]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        return PublishResult(
            ok=False,
            dry_run=dry_run,
            message=f"이미지 없음: {', '.join(missing)}",
            media_ids=[],
        )

    if dry_run or not has_ig_credentials():
        reason = "dry-run 모드" if dry_run else "IG_ACCESS_TOKEN / IG_USER_ID 미설정"
        return PublishResult(
            ok=True,
            dry_run=True,
            message=(
                f"[STUB] {reason}. 실제 발행하지 않았습니다. "
                f"슬라이드 {len(paths)}장, caption 길이 {len(caption)}자."
            ),
            media_ids=[f"stub_media_{i+1}" for i in range(len(paths))],
            raw={"paths": [str(p) for p in paths], "caption": caption},
        )

    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    user_id = os.getenv("IG_USER_ID", "").strip()
    graph_base = graph_base_for_token(token)

    # 공식 Graph API: 각 이미지를 컨테이너로 생성 → 캐러셀 컨테이너 → media_publish
    # Instagram Content Publishing API는 image_url(공개 HTTPS)을 요구한다.
    # 로컬 PNG는 임시 호스트 업로드(또는 .url / IG_IMAGE_BASE_URL)로 해결.
    try:
        children: list[str] = []
        uploaded_urls: list[str] = []
        for p in paths:
            try:
                image_url = resolve_image_url(p)
            except RuntimeError as e:
                return PublishResult(
                    ok=False,
                    dry_run=False,
                    message=str(e),
                    media_ids=children,
                )
            uploaded_urls.append(image_url)
            r = requests.post(
                f"{graph_base}/{user_id}/media",
                data={
                    "image_url": image_url,
                    "is_carousel_item": "true",
                    "access_token": token,
                },
                timeout=60,
            )
            data = r.json()
            if "id" not in data:
                return PublishResult(
                    ok=False,
                    dry_run=False,
                    message=f"미디어 컨테이너 생성 실패: {data}",
                    media_ids=children,
                    raw={**(data if isinstance(data, dict) else {"response": data}), "image_url": image_url},
                )
            children.append(data["id"])

        create = requests.post(
            f"{graph_base}/{user_id}/media",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(children),
                "caption": caption,
                "access_token": token,
            },
            timeout=60,
        )
        create_data = create.json()
        if "id" not in create_data:
            return PublishResult(
                ok=False,
                dry_run=False,
                message=f"캐러셀 컨테이너 실패: {create_data}",
                media_ids=children,
                raw=create_data,
            )

        # Wait until carousel container is ready (IG often needs a few seconds)
        for child_id in children:
            st = wait_for_container_ready(graph_base, child_id, token)
            if str(st.get("status_code")) not in {"FINISHED", ""} and st.get("status_code"):
                if str(st.get("status_code")) in {"ERROR", "EXPIRED"}:
                    return PublishResult(
                        ok=False,
                        dry_run=False,
                        message=f"자식 컨테이너 준비 실패 ({child_id}): {st}",
                        media_ids=children,
                        raw=st,
                    )
        ready = wait_for_container_ready(graph_base, create_data["id"], token)
        if str(ready.get("status_code")) == "ERROR" or ready.get("_wait_timeout"):
            return PublishResult(
                ok=False,
                dry_run=False,
                message=f"캐러셀 컨테이너 미준비: {ready}",
                media_ids=children + [create_data["id"]],
                raw=ready,
            )

        pub = requests.post(
            f"{graph_base}/{user_id}/media_publish",
            data={"creation_id": create_data["id"], "access_token": token},
            timeout=60,
        )
        pub_data = pub.json()
        if "id" not in pub_data:
            return PublishResult(
                ok=False,
                dry_run=False,
                message=f"발행 실패: {pub_data}",
                media_ids=children,
                raw=pub_data,
            )
        return PublishResult(
            ok=True,
            dry_run=False,
            message=f"발행 완료. media id={pub_data['id']}",
            media_ids=children + [pub_data["id"]],
            raw={**pub_data, "image_urls": uploaded_urls, "graph_base": graph_base},
        )
    except requests.RequestException as e:
        return PublishResult(
            ok=False,
            dry_run=False,
            message=f"네트워크/API 오류: {e}",
            media_ids=[],
        )
