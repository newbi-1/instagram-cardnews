"""발행: dry-run 기본 + 공식 Meta Graph API 경로."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

GRAPH_BASE = "https://graph.facebook.com/v21.0"


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

    # 공식 Graph API: 각 이미지를 컨테이너로 생성 → 캐러셀 컨테이너 → media_publish
    # 참고: 로컬 파일은 공개 URL이 필요. MVP에서는 로컬 경로를 받아
    # 사용자가 이미 CDN/호스팅 URL을 넣는 확장 지점을 남기고,
    # 여기서는 file 업로드가 불가한 경우를 명확히 안내한다.
    # Instagram Content Publishing API는 image_url(공개 HTTPS)을 요구한다.
    try:
        children: list[str] = []
        for p in paths:
            # Expect companion .url sidecar OR IG_IMAGE_BASE_URL + filename
            sidecar = p.with_suffix(".url")
            base = os.getenv("IG_IMAGE_BASE_URL", "").rstrip("/")
            if sidecar.exists():
                image_url = sidecar.read_text(encoding="utf-8").strip()
            elif base:
                image_url = f"{base}/{p.name}"
            else:
                return PublishResult(
                    ok=False,
                    dry_run=False,
                    message=(
                        "Graph API는 공개 HTTPS image_url이 필요합니다. "
                        "각 PNG 옆 .url 사이드카를 두거나 IG_IMAGE_BASE_URL을 설정하세요. "
                        "지금은 dry-run을 사용하세요."
                    ),
                    media_ids=[],
                )
            r = requests.post(
                f"{GRAPH_BASE}/{user_id}/media",
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
                    raw=data,
                )
            children.append(data["id"])

        create = requests.post(
            f"{GRAPH_BASE}/{user_id}/media",
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

        pub = requests.post(
            f"{GRAPH_BASE}/{user_id}/media_publish",
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
            raw=pub_data,
        )
    except requests.RequestException as e:
        return PublishResult(
            ok=False,
            dry_run=False,
            message=f"네트워크/API 오류: {e}",
            media_ids=[],
        )
