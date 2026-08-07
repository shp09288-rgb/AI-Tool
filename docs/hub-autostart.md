# 집 PC 허브 자동 기동 (Tailscale + Streamlit)

재부팅·로그온 후 Streamlit이 자동으로 떠서, 회사/개인 노트북이 Tailscale로 UI에 접속할 수 있게 합니다.  
PMS 등 **회사 내부망 라우트(기존 Tailscale)** 와 충돌하지 않습니다.

## 1회 등록

PowerShell에서 저장소 루트로 이동한 뒤:

```powershell
cd "C:\Users\shp09\Documents\01_AI Tool\AI 업무 자동화 Tool"
powershell -ExecutionPolicy Bypass -File scripts\register-hub-autostart.ps1
```

지연을 늘리려면 (업데이트 직후 OneDrive/Tailscale가 느릴 때):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-hub-autostart.ps1 -DelaySeconds 120
```

## 즉시 테스트

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-hub-streamlit.ps1 -DelaySeconds 0
```

- 로컬: http://localhost:8501  
- Tailscale: `http://<집PC-MagicDNS-또는-100.x.x.x>:8501`

## Windows 전원·잠금 (권장)

- 전원 옵션: **절전 안 함** (디스플레이만 끄기 OK)
- Tailscale·OneDrive: 시작 프로그램/서비스 자동 실행 ON
- Outlook: 로그온 후 자동 실행 권장 (메일 COM)

### 화면 잠금(Win+L) vs 문제

| 상태 | Streamlit / Tailscale UI | Outlook·Excel COM(메일·PNG) |
|------|--------------------------|-----------------------------|
| 로그인된 채 **화면만 잠금** | 보통 **정상** (세션 유지) | 대부분 동작. 간헐 실패 시 잠금 해제 후 재시도 |
| **로그아웃** / 로그인 화면만 | 작업이 안 떠 있거나 COM 불가 | **불가**에 가깝음 |
| **절전** | 끊김 | 끊김 |

비밀번호가 걸리는 잠금 화면 자체는 보안상 정상이고, 허브 용도로는 **잠금은 허용·로그아웃/절전은 피할 것**이 안전합니다.

## 로그

- `logs/hub-streamlit.log` — 기동 이력  
- `logs/hub-streamlit.out.log` / `.err.log` — Streamlit stdout/stderr  

## 제거

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-hub-autostart.ps1 -Unregister
```

## 참고

- Streamlit은 `0.0.0.0:8501`에 바인딩됩니다. **공유기 포트포워딩은 하지 말고** Tailscale만 사용하세요.
- 작업은 **사용자 로그온 시** 실행됩니다 (잠금 화면 전용 세션의 COM 이슈를 피하기 위함).
