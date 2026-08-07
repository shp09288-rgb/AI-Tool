# Outlook Field Report Mail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After field-report SF registration, Tool drafts a work-report email, lets the user edit it in Streamlit, and sends via Outlook COM as `ethan.lee@parksystems.com`.

**Architecture:** Pure template builders (`mail_template.py`) + Outlook COM sender (`outlook_com.py`) + Streamlit editor wired to post-registration session state. PNG/xlsx regenerated from the loaded workbook at draft time (no reliance on deleted temp dirs).

**Tech Stack:** Python, Streamlit, pywin32 Outlook COM, pytest

## Global Constraints

- From / Bcc always `ethan.lee@parksystems.com`
- To required before send; Cc optional empty
- No Outlook Display window for edit; Tool editor only
- No Graph API in v1
- TDD for template and send validation

---

### Task 1: Mail template

**Files:**
- Create: `src/ai_work_automation/field_report/mail_template.py`
- Test: `tests/test_field_report_mail.py`

- [x] Subject + body text + meta line (Case/WO comma list)
- [x] Asset label parse helper (`SDC` + `A6_NX-TSH2326 #1` → site/model)
- [x] pytest green

### Task 2: Outlook COM send wrapper

**Files:**
- Create: `src/ai_work_automation/field_report/outlook_com.py`
- Test: `tests/test_field_report_mail.py` (mock COM)

- [x] `MailSendRequest` dataclass; reject empty To; force Bcc/From
- [x] `send_mail_via_outlook(...)` with injectable Outlook app factory
- [x] Inline PNG + optional xlsx attach

### Task 3: Enrich registration result + WebUI editor

**Files:**
- Modify: `src/ai_work_automation/field_report/pipeline.py` (case_number on single-mode acted; optional WO number lookup)
- Modify: `src/ai_work_automation/webui.py` (draft button, editor, send confirm)
- Modify: `src/ai_work_automation/sf/adapter.py` if needed for WO number read

- [x] On success/partial: store `fr_mail_ctx` in session
- [x] 「메일 초안 만들기」 → editor fields + PNG preview
- [x] 「전송」 with confirm → COM send
- [x] Spec status → Approved/Implemented note
