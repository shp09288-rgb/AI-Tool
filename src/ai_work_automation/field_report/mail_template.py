"""출장 작업보고 메일 제목·본문 초안 (HTML)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import escape

ETHAN_EMAIL = "ethan.lee@parksystems.com"
_SIGNATURE_BLUE = "#002060"
PNG_MARKER = "<!--FIELD_SHEET_PNG-->"

_ASSET_RE = re.compile(
    r"^(?P<area>[A-Za-z0-9]+?)_(?P<model>.+?)(?:\s*#\s*\d+)?$"
)

_CUSTOMER_DISPLAY = {
    "SDC": "삼성디스플레이",
    "LGD": "엘지디스플레이",
}


@dataclass(frozen=True)
class MailDraft:
    subject: str
    body_html: str
    from_address: str = ETHAN_EMAIL
    to: str = ""
    cc: str = ""
    bcc: str = ETHAN_EMAIL

    @property
    def body_text(self) -> str:
        """테스트/폴백용 대략적 평문."""
        text = re.sub(r"<br\s*/?>", "\n", self.body_html, flags=re.I)
        text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_asset_tokens(customer: str, asset_folder: str) -> tuple[str, str, str]:
    """`SDC` + `A6_NX-TSH2326 #1` → (`SDC A6`, `A6`, `NX-TSH2326`)."""
    name = asset_folder.strip()
    m = _ASSET_RE.match(name)
    if not m:
        site = f"{customer.strip()} {name}".strip()
        return site, "", name
    area = m.group("area")
    model = m.group("model").strip()
    site = f"{customer.strip()} {area}".strip()
    return site, area, model


def customer_display_name(customer: str) -> str:
    code = (customer or "").strip().upper()
    return _CUSTOMER_DISPLAY.get(code, (customer or "").strip() or code)


def lightning_record_url(
    instance_url: str, object_api: str, record_id: str
) -> str:
    base = (instance_url or "").rstrip("/")
    if not base or not record_id:
        return ""
    if ".my.salesforce.com" in base:
        base = base.replace(".my.salesforce.com", ".lightning.force.com")
    elif ".salesforce.com" in base and ".lightning.force.com" not in base:
        base = re.sub(
            r"\.salesforce\.com$", ".lightning.force.com", base
        )
    return f"{base}/lightning/r/{object_api}/{record_id}/view"


def _linked_numbers(
    refs: list[dict[str, str]],
    *,
    object_api: str,
    instance_url: str,
) -> str:
    parts: list[str] = []
    for ref in refs:
        num = (ref.get("number") or "").strip()
        rid = (ref.get("id") or "").strip()
        if not num:
            continue
        url = lightning_record_url(instance_url, object_api, rid) if rid else ""
        if url:
            parts.append(
                f'<a href="{escape(url, quote=True)}">{escape(num)}</a>'
            )
        else:
            parts.append(escape(num))
    return ", ".join(parts) if parts else "-"


def signature_html(*, signer_name: str = "이동현") -> str:
    """이미지와 동일한 서명 블록 — 파란글씨 10pt."""
    name = escape(signer_name.strip() or "이동현")
    style = (
        f"font-family:'Malgun Gothic',sans-serif;font-size:10pt;"
        f"color:{_SIGNATURE_BLUE};line-height:1.35"
    )
    p = f'<p style="margin:0 0 0 0;{style}">'
    return "\n".join(
        [
            f'<div style="{style}">',
            f"{p}감사합니다</p>",
            f"{p}{name} 드림</p>",
            "<br/>",
            f"{p}Service Engineer I 대리</p>",
            f"{p}Domestic Field Service 2팀</p>",
            f"{p}국내사업부</p>",
            "<br/>",
            f'{p}<b>Park Systems Corp.</b></p>',
            f"{p}150 Gwacheon-daero 12-gil, Gwacheon-si, "
            "Gyeonggi-do 13824, Republic of Korea</p>",
            f"{p}Tel) 010-8923-8129 (Direct ) | Web) "
            '<a href="https://www.parksystems.com" '
            f'style="color:{_SIGNATURE_BLUE}">www.parksystems.com</a></p>',
            "</div>",
        ]
    )


def build_mail_draft(
    *,
    customer: str,
    asset_folder: str,
    work_day: date,
    fse_name: str,
    case_numbers: list[str] | None = None,
    wo_numbers: list[str] | None = None,
    case_refs: list[dict[str, str]] | None = None,
    wo_refs: list[dict[str, str]] | None = None,
    sf_instance_url: str = "",
    short_title: str = "",  # noqa: ARG001
    signer_name: str = "이동현",
) -> MailDraft:
    site, area, model = parse_asset_tokens(customer, asset_folder)
    subject = f"[작업보고] {site} / {model} / {work_day:%Y-%m-%d} 작업 보고"
    fse = (fse_name or "미지정").strip()
    company = customer_display_name(customer)
    intro_parts = [p for p in (company, area, model) if p]
    intro = f"{' '.join(intro_parts)} 작업 보고 드립니다."

    if not case_refs and case_numbers:
        case_refs = [{"number": n, "id": ""} for n in case_numbers]
    if not wo_refs and wo_numbers:
        wo_refs = [{"number": n, "id": ""} for n in wo_numbers]
    case_html = _linked_numbers(
        case_refs or [], object_api="Case", instance_url=sf_instance_url
    )
    wo_html = _linked_numbers(
        wo_refs or [], object_api="WorkOrder", instance_url=sf_instance_url
    )

    body_style = (
        "font-family:'Malgun Gothic',sans-serif;font-size:11pt;color:#000000"
    )
    p = f'<p style="margin:0 0 8px 0;{body_style}">'
    body_html = "\n".join(
        [
            f'<div style="{body_style}">',
            f"{p}안녕하세요</p>",
            f"{p}{escape(fse)}입니다.</p>",
            "<br/>",
            f"{p}{escape(intro)}</p>",
            "<br/>",
            f"{p}작업날짜 : {work_day:%Y-%m-%d}</p>",
            f"{p}인원 : {escape(fse)}</p>",
            f"{p}Case number : {case_html}</p>",
            f"{p}Work order number : {wo_html}</p>",
            "<br/>",
            f'{p}<b>작업내용</b></p>',
            PNG_MARKER,
            "<br/>",
            signature_html(signer_name=signer_name),
            "</div>",
        ]
    )
    return MailDraft(subject=subject, body_html=body_html)
