from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_work_automation.field_report.mail_template import (
    ETHAN_EMAIL,
    PNG_MARKER,
    build_mail_draft,
    lightning_record_url,
    parse_asset_tokens,
    signature_html,
)


def test_parse_asset_tokens() -> None:
    site, area, model = parse_asset_tokens("SDC", "A6_NX-TSH2326 #1")
    assert site == "SDC A6"
    assert area == "A6"
    assert model == "NX-TSH2326"


def test_lightning_record_url() -> None:
    url = lightning_record_url(
        "https://parksystems.my.salesforce.com", "Case", "500xx"
    )
    assert url == (
        "https://parksystems.lightning.force.com/lightning/r/Case/500xx/view"
    )


def test_build_mail_draft_html_signature_and_links() -> None:
    draft = build_mail_draft(
        customer="SDC",
        asset_folder="A5_NX-TSH2225 #1",
        work_day=date(2026, 7, 29),
        fse_name="이동현",
        case_refs=[
            {"number": "00200687", "id": "500AAA"},
            {"number": "00191458", "id": "500BBB"},
        ],
        wo_refs=[
            {"number": "00001234", "id": "0WOAAA"},
            {"number": "00001235", "id": "0WOBBB"},
        ],
        sf_instance_url="https://parksystems.my.salesforce.com",
    )
    assert draft.subject == "[작업보고] SDC A5 / NX-TSH2225 / 2026-07-29 작업 보고"
    assert draft.from_address == ETHAN_EMAIL
    html = draft.body_html
    assert "font-size:11pt" in html
    assert "Malgun Gothic" in html
    assert "삼성디스플레이 A5 NX-TSH2225 작업 보고 드립니다." in html
    assert "Case number :" in html
    assert "lightning/r/Case/500AAA/view" in html
    assert "lightning/r/WorkOrder/0WOAAA/view" in html
    assert PNG_MARKER in html
    assert "감사합니다" in html
    assert "이동현 드림" in html
    assert "Park Systems Corp." in html
    assert "font-size:10pt" in html
    assert "#002060" in html


def test_signature_html_blue_10pt() -> None:
    sig = signature_html()
    assert "10pt" in sig
    assert "#002060" in sig
    assert "Service Engineer I 대리" in sig


def test_customer_display_name_lgd() -> None:
    draft = build_mail_draft(
        customer="LGD",
        asset_folder="A1_NX-TSH1111 #1",
        work_day=date(2026, 1, 2),
        fse_name="홍길동",
        case_numbers=["001"],
        wo_numbers=["002"],
    )
    assert "엘지디스플레이 A1 NX-TSH1111 작업 보고 드립니다." in draft.body_html


def test_send_mail_requires_to() -> None:
    from ai_work_automation.field_report.outlook_com import (
        MailSendRequest,
        send_mail_via_outlook,
    )

    req = MailSendRequest(
        to="",
        cc="",
        subject="t",
        body_html="<p>hello</p>",
        png_path=None,
    )
    with pytest.raises(ValueError, match="To"):
        send_mail_via_outlook(req, outlook_factory=lambda: MagicMock())


def test_send_mail_via_outlook_mocked(tmp_path: Path) -> None:
    from ai_work_automation.field_report.mail_template import ETHAN_EMAIL
    from ai_work_automation.field_report.outlook_com import (
        MailSendRequest,
        send_mail_via_outlook,
    )

    png = tmp_path / "sheet.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    xlsx = tmp_path / "day.xlsx"
    xlsx.write_bytes(b"PK\x03\x04")

    mail = MagicMock()
    accounts = MagicMock()
    account = MagicMock()
    account.SmtpAddress = ETHAN_EMAIL
    accounts.__iter__ = lambda self: iter([account])
    accounts.Count = 1
    accounts.Item = lambda i: account

    outlook = MagicMock()
    outlook.Session.Accounts = accounts
    outlook.CreateItem.return_value = mail

    html = (
        '<div><p><b>작업내용</b></p>'
        f"{PNG_MARKER}"
        "<p>감사합니다</p></div>"
    )
    req = MailSendRequest(
        to="boss@parksystems.com",
        cc="peer@parksystems.com",
        subject="[작업보고] SDC A6 / NX-TSH2326 / Tip",
        body_html=html,
        png_path=png,
        xlsx_path=xlsx,
    )
    send_mail_via_outlook(req, outlook_factory=lambda: outlook)

    assert mail.To == "boss@parksystems.com"
    assert mail.BCC == ETHAN_EMAIL
    assert "cid:field_sheet.png" in mail.HTMLBody
    assert PNG_MARKER not in mail.HTMLBody
    mail.Send.assert_called_once()
