# AI 업무 자동화 CLI

이 프로젝트는 Case 옵트인을 관리하고, 선택된 Case에 대해 Salesforce와 PMS 연동 작업을 실행하는 CLI 도구입니다.

## 실행 방법

1. 가상환경을 만들고 의존성을 설치합니다.
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e ".[dev]"
   ```
2. 환경 예시를 복사해 값을 채웁니다.
   ```powershell
   Copy-Item .env.example .env
   Copy-Item config\settings.example.yaml config\settings.yaml
   ```
3. `config/settings.yaml`에서 `automation_enabled_after`, 경로, `pms_project_id`를 확인하고, `.env`에서 Salesforce와 PMS 토큰을 설정합니다.
4. Case를 선택하고 확인합니다.
   ```powershell
   ai-work select <CaseId>
   ai-work list-selected
   ```
5. 실행합니다.
   ```powershell
   ai-work run <CaseId>
   ```

## 안전 규칙

- 선택되지 않은 Case는 실행하지 않습니다.
- `automation_enabled_after` 이전의 Case/Work Order는 쓰기 작업을 하지 않습니다.
- 외부 게시 전 Human Gate가 기본으로 동작합니다.
- 실제 비밀값은 커밋하지 마세요. `config/settings.yaml`은 로컬에서만 사용합니다.
