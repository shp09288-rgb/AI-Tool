"""로컬 Outlook COM으로 메일 전송 (Graph 불필요)."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Callable

from ai_work_automation.field_report.mail_template import ETHAN_EMAIL, PNG_MARKER

# Outlook olMailItem
_OL_MAIL_ITEM = 0


@dataclass
class MailSendRequest:
    to: str
    cc: str
    subject: str
    body_html: str = ""
    body_text: str = ""  # 하위호환: HTML이 없을 때 평문→HTML
    png_path: Path | None = None
    xlsx_path: Path | None = None
    from_address: str = ETHAN_EMAIL
    bcc: str = ETHAN_EMAIL


def _default_outlook():
    import pythoncom
    import win32com.client  # type: ignore

    pythoncom.CoInitialize()
    return win32com.client.Dispatch("Outlook.Application")


def _find_account(outlook, smtp: str):
    accounts = outlook.Session.Accounts
    target = smtp.strip().lower()
    count = int(getattr(accounts, "Count", 0) or 0)
    for i in range(1, count + 1):
        acc = accounts.Item(i)
        addr = (getattr(acc, "SmtpAddress", None) or "").strip().lower()
        if addr == target:
            return acc
    try:
        for acc in accounts:
            addr = (getattr(acc, "SmtpAddress", None) or "").strip().lower()
            if addr == target:
                return acc
    except TypeError:
        pass
    raise RuntimeError(
        f"Outlook에 발송 계정({smtp})이 없습니다. "
        "해당 프로필로 Outlook에 로그인한 뒤 다시 시도하세요."
    )


def body_text_to_html(body_text: str, *, png_cid: str | None = None) -> str:
    """평문 본문을 HTML로. '작업내용' 바로 다음에 인라인 PNG 삽입."""
    lines = body_text.replace("\r\n", "\n").split("\n")
    parts: list[str] = [
        '<div style="font-family:\'Malgun Gothic\',sans-serif;font-size:11pt">'
    ]
    inserted = False
    for line in lines:
        if line.strip() == "작업내용":
            parts.append(f"<p><b>{escape(line)}</b></p>")
            if png_cid and not inserted:
                parts.append(
                    f'<p><img src="cid:{png_cid}" '
                    'style="max-width:900px;border:1px solid #ccc"/></p>'
                )
                inserted = True
            continue
        if line.strip() == "":
            parts.append("<br/>")
        else:
            parts.append(f"<p>{escape(line)}</p>")
    if png_cid and not inserted:
        parts.append(
            f'<p><img src="cid:{png_cid}" '
            'style="max-width:900px;border:1px solid #ccc"/></p>'
        )
    parts.append("</div>")
    return "\n".join(parts)


def finalize_mail_html(
    body_html: str,
    *,
    png_cid: str | None = None,
) -> str:
    """초안 HTML에 PNG 마커를 인라인 이미지로 치환."""
    html = body_html or ""
    img = ""
    if png_cid:
        img = (
            f'<p><img src="cid:{png_cid}" '
            'style="max-width:900px;border:1px solid #ccc"/></p>'
        )
    if PNG_MARKER in html:
        return html.replace(PNG_MARKER, img)
    if png_cid and "작업내용" in html and img:
        # 마커가 편집 중 지워진 경우: 작업내용 단락 뒤에 삽입
        return html.replace("</b></p>", f"</b></p>\n{img}", 1)
    return html + (img if img else "")


def send_mail_via_outlook(
    req: MailSendRequest,
    *,
    outlook_factory: Callable | None = None,
) -> None:
    if not (req.to or "").strip():
        raise ValueError("To(수신자)를 입력한 뒤 전송하세요.")

    factory = outlook_factory or _default_outlook
    outlook = factory()
    account = _find_account(outlook, req.from_address or ETHAN_EMAIL)
    mail = outlook.CreateItem(_OL_MAIL_ITEM)
    mail.SendUsingAccount = account
    mail.To = req.to.strip()
    mail.CC = (req.cc or "").strip()
    mail.BCC = ETHAN_EMAIL
    mail.Subject = req.subject

    png_cid = "field_sheet.png"
    use_png = bool(req.png_path and Path(req.png_path).is_file())
    if (req.body_html or "").strip():
        html = finalize_mail_html(
            req.body_html, png_cid=png_cid if use_png else None
        )
    else:
        html = body_text_to_html(
            req.body_text or "",
            png_cid=png_cid if use_png else None,
        )
    mail.HTMLBody = html

    if use_png:
        assert req.png_path is not None
        att = mail.Attachments.Add(str(Path(req.png_path).resolve()))
        try:
            att.PropertyAccessor.SetProperty(
                "http://schemas.microsoft.com/mapi/proptag/0x3712001F",
                png_cid,
            )
        except Exception:  # noqa: BLE001
            pass

    if req.xlsx_path and Path(req.xlsx_path).is_file():
        mail.Attachments.Add(str(Path(req.xlsx_path).resolve()))

    mail.Send()
