from collections.abc import Callable

from ai_work_automation.models import DraftContent


def human_approve(
    draft: DraftContent,
    prompt_fn: Callable[[str], str] | None = None,
) -> bool:
    ask = prompt_fn or input
    message = (
        f"제목: {draft.title}\n\n본문:\n{draft.body}\n\n"
        "이 내용으로 외부 게시를 승인할까요? [y/N]: "
    )
    answer = ask(message).strip().lower()
    return answer in {"y", "yes", "ㅇ"}
