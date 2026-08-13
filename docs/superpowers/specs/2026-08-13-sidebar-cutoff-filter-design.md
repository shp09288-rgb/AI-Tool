# 사이드바 컷오프 날짜 필터 — 설계 스펙

**날짜:** 2026-08-13  
**상태:** 설계 승인됨 (대화 합의)  
**관련:** `automation_enabled_after`, `src/ai_work_automation/webui.py` 사이드바, `config_store.update_settings_yaml`

## 1. 목표

클린 PC 등에서 `settings.example.yaml`의 미래 컷오프(예: 2026-12-01) 때문에 스캔이 0건인 문제를, **사이드바 필터에서 날짜를 바꿔 즉시 해결**할 수 있게 한다.

성공 기준:

1. 사이드바에서 컷오프 날짜를 과거로 바꾸면 yaml에 저장되고, 다음 「Salesforce 스캔」부터 새 컷오프가 적용된다.
2. 미래 날짜면 0건일 수 있다는 안내가 보인다.
3. 기존 장비/상태/담당자 필터·설정 탭·SF 로그인 UI는 회귀 없음.

## 2. 비목표

- 설정 탭에 동일 컨트롤 중복
- 시·분·타임존 선택 UI (고정 `00:00:00+09:00`)
- 세션 전용(비저장) 컷오프
- SOQL/어댑터 컷오프 로직 변경 (설정 값만 UI로 편집)

## 3. 접근 (확정)

**사이드바 필터 + 변경 시 `settings.yaml` 즉시 저장 (옵션 A + 유지 B).**

## 4. UI

| 항목 | 내용 |
|------|------|
| 위치 | 사이드바 「필터」 영역 — Relevant Department **위** (날짜가 스캔 전제임을 강조) |
| 라벨 | `컷오프 (이 날짜 이후 WO만)` |
| 위젯 | `st.date_input`, 초기값 = `settings.automation_enabled_after`의 날짜 부분 |
| Caption | `미래 날짜면 스캔 결과가 0건일 수 있습니다. 변경 시 settings.yaml에 저장됩니다.` |
| 히어로/기존 컷오프 표시 | 기존 표시는 유지하되, 저장 후 최신 설정을 읽게 함 |

## 5. 저장·반영

1. 사용자가 날짜를 바꾸면 ISO 문자열로 변환:  
   `YYYY-MM-DDT00:00:00+09:00` (기존 example과 동일 오프셋).
2. `update_settings_yaml(SETTINGS_PATH, {"automation_enabled_after": <iso-or-datetime>})`  
   — `config_store`가 datetime/str을 yaml에 쓰도록 기존 헬퍼를 확인·필요 시 문자열로 통일.
3. 저장 직후 설정 캐시가 있으면 무효화하고, `_settings()` / `_sf()`가 새 컷오프를 쓰게 한다.
4. Streamlit 전체 프로세스 재시작은 요구하지 않는다.

### 5.1 위젯 상태

- `date_input`에 안정적인 `key` 사용 (예: `sidebar_cutoff_date`).
- yaml 저장 후 다른 경로로 컷오프가 바뀌는 경우는 1차 범위에서 없음. 초기화는 세션 첫 로드 시 settings에서.

## 6. 테스트

- 단위: 날짜 → `automation_enabled_after` 문자열/저장 호출을 검증할 수 있으면 헬퍼로 분리; 아니면 `update_settings_yaml`에 datetime/str 저장 스모크.
- 수동: 컷오프를 과거로 저장 → 스캔에 건수 증가(또는 0이 아님); 다시 미래로 두면 0건 가능.

## 7. 구현 순서

1. (필요 시) `update_settings_yaml` / 컷오프 직렬화 헬퍼  
2. 사이드바 `date_input` + 저장 + caption  
3. 스캔이 새 settings를 쓰는지 확인  
4. (선택) example yaml 주석에 「사이드바에서 변경 가능」 한 줄
