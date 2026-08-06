from typing import Protocol

from ai_work_automation.models import ConnectorResult, DraftContent


class Connector(Protocol):
    def create(self, draft: DraftContent, **kwargs) -> ConnectorResult: ...
