from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CaseRecord(BaseModel):
    id: str
    case_number: str
    subject: str
    created_date: datetime
    description: str | None = None
    status: str | None = None


class WorkOrderRecord(BaseModel):
    id: str
    work_order_number: str
    record_type: str
    relevant_department: str | None = None
    subject: str | None = None
    voc_title: str | None = None
    background: str | None = None
    activities: str | None = None
    case_id: str | None = None
    created_date: datetime | None = None
    priority: str | None = None
    sw_version: str | None = None


class AttachmentRef(BaseModel):
    title: str
    url: str


class DraftContent(BaseModel):
    title: str
    body: str
    extra: dict[str, Any] = Field(default_factory=dict)


class ConnectorResult(BaseModel):
    ok: bool
    ref: str | None = None
    url: str | None = None
    error: str | None = None
    retryable: bool = False
    raw: dict[str, Any] | None = None
