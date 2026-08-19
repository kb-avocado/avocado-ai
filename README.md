# avocado-ai

월간 소비 리포트(`child_spending_reports`)에 **AI 조언 2개**(아이용 / 보호자용)를 채워 넣는 배치.

REST API를 서빙하지 않고, 백엔드와 통신하지도 않는다. **같은 MySQL을 직접 UPDATE** 한다.
서비스 배경·데이터 모델·조언 규격은 레포 밖 `../ONBOARDING.md` 참고.

| 항목 | 값 |
| --- | --- |
| 언어 | Python 3.11+ |
| AI | OpenAI API (모델 미확정 — `gpt-5-nano` / `gpt-4o-mini`) |
| 대상 | `child_spending_reports.child_advice`, `.parent_advice` |
| 주기 | 매월 1일 (현재는 수동 실행만) |

---

## 1. 준비

### 1-1. DB

**MySQL이 떠 있어야 한다.** 백엔드 레포의 compose가 띄운다.

```bash
cd ../avocado-backend
docker compose up -d mysql
```

### 1-2. 환경 설치 (처음 1회)

`.venv`는 커밋되지 않으므로 각자 만들어야 한다.

```bash
# Windows
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .

# macOS / Linux
python3 -m venv .venv
./.venv/bin/python -m pip install -e .
```

> VS Code를 쓴다면 `Ctrl+Shift+P` → `Tasks: Run Task` → **"환경 설치 (처음 받았을 때 1회)"** 로 대신할 수 있다.

`-e`(editable) 설치라 **코드를 고치면 재설치 없이 바로 반영된다.**

### 1-3. `.env`

```bash
cp .env.example .env
```

채워야 하는 값은 둘뿐이다.

| 키 | 값 |
| --- | --- |
| `DB_PASSWORD` | 백엔드 `.env`의 `MYSQL_PASSWORD`와 같은 값 |
| `OPENAI_API_KEY` | 발급받은 키 |

나머지는 기본값으로 로컬에서 동작한다. **`.env`는 `.gitignore` 처리되어 있다. 커밋 금지.**

---

## 2. 실행

### 2-1. VS Code 작업 (권장)

**`Ctrl+Shift+B`** 를 누르면 목록이 뜬다.

```
① 상태 확인 — DB 접속과 채워진 건수 (API 호출 없음)
② 19번 전 기간 — 4개 유형 한 번에, DB 안 건드림
③ 19번 전 기간 + 프롬프트 출력 — 프롬프트 수정 확인용
④ 9종 샘플 — DB 없이 유형별 결과
⑤ 9종 샘플 (gpt-4o-mini) — 모델 비교용
⑥ 지난달 전체 — DB 안 건드림
⑦ 지난달 전체 — 실제 UPDATE ⚠
⑧ 전 기간 전원 — 실제 UPDATE ⚠⚠
```

`Ctrl+Shift+P` → `Tasks: Run Task` 에는 **"직접 입력"** 작업도 있다. 옵션을 타이핑해서 넘긴다.

> VS Code 루트가 `avocado-ai` 폴더여야 한다. `KB-AVO`를 열었다면
> `.vscode/tasks.json`의 `cwd`를 `"${workspaceFolder}/avocado-ai"`로 바꿀 것.

### 2-2. 터미널

```powershell
$PY = ".\.venv\Scripts\python.exe"     # mac/linux: ./.venv/bin/python

# DB 접속과 데이터 상태만 확인 (OpenAI 호출 없음)
& $PY -m avocado_ai.main --check

# DB 없이 9종 유형 샘플로 생성만
& $PY -m avocado_ai.main --sample

# 한 아이의 전 기간, DB 는 안 건드림
& $PY -m avocado_ai.main --child-id 19 --all-months --dry-run --force

# 특정 월 실제 실행
& $PY -m avocado_ai.main --year 2026 --month 7

# 지난달 전체 실제 실행 (스케줄러가 돌릴 형태)
& $PY -m avocado_ai.main
```

`--year`/`--month`를 생략하면 **Asia/Seoul 기준 지난달**이 대상이다.

---

## 3. 옵션

| 옵션 | 뜻 |
| --- | --- |
| `--check` | DB 접속·데이터 상태만 확인하고 끝낸다. API 호출 없음 |
| `--sample` | DB 없이 9종 유형 **가짜 데이터**로 생성만 해본다 |
| `--show-prompt` | 모델에 들어가는 system/user 프롬프트를 그대로 출력 |
| `--year` / `--month` | 대상 월. **둘 다 주거나 둘 다 생략** |
| `--all-months` | 리포트가 있는 모든 달. `--year`/`--month`와 함께 못 쓴다 |
| `--child-id N` | 특정 아이만 |
| `--limit N` | 앞에서 N건만 |
| `--dry-run` | **생성만 하고 DB를 건드리지 않는다** |
| `--force` | 이미 조언이 채워진 행도 다시 생성 |
| `--model` | `OPENAI_MODEL`을 무시하고 지정 모델로 실행 |

**확신이 없으면 `--dry-run`을 붙인다.** 붙어 있는 한 DB는 절대 바뀌지 않는다.

`--dry-run --force` 조합이 반복 실험에 가장 유용하다. 같은 행을 몇 번이든 다시 돌릴 수 있다.

---

## 4. 구조

| 파일 | 역할 |
| --- | --- |
| `config.py` | `.env` 로딩 |
| `db.py` | MySQL 커넥션 (utf8mb4 / `+09:00` 고정) |
| `repository.py` | 대상 조회, advice UPDATE |
| `prompt.py` | **프롬프트 전체.** 유형별 제안 방향, 어휘 규칙, 응답 스키마 |
| `generator.py` | OpenAI 호출, 길이 검증, 재시도 |
| `main.py` | CLI |

### 조언 품질을 고치려면

**`prompt.py` 한 파일만 보면 된다.**

| 위치 | 내용 |
| --- | --- |
| `build_system_prompt()` | 어투·구조·어휘·길이·금지 등 **규칙 전체** |
| `SUGGESTION_DIRECTION` | 유형 9종별 제안 방향 |
| `build_user_prompt()` | 어떤 집계값을 넘길지 |

작업 흐름은 이렇다.

1. `prompt.py` 수정
2. `Ctrl+Shift+B` → ③ (또는 `--child-id 19 --all-months --dry-run --force --show-prompt`)
3. 결과 확인 후 반복

저장하면 바로 반영된다. 재설치 불필요.

---

## 5. 배포

**`.env` 파일을 서버에 올리지 않는다.** 환경변수로 주입한다.

`load_dotenv()`는 이미 존재하는 환경변수를 덮어쓰지 않으므로, 실제 환경변수가 항상 `.env`를 이긴다.
덕분에 환경별로 파일을 나눌 필요가 없다 — `.env.example`은 "어떤 값이 필요한지" 목록 하나면 된다.

| 실행 주체 | 주입 방법 |
| --- | --- |
| GitHub Actions | 리포지토리 Secrets → `env:` 블록 (`.env` 파일 자체가 불필요) |
| 서버 cron | systemd `EnvironmentFile=`, 또는 서버에 `.env` + `chmod 600` |
| Docker | `-e` / compose `environment:` / secrets |

로컬과 달라지는 값은 이것뿐이다.

```
DB_HOST          127.0.0.1 → 운영 DB 주소
DB_PORT          3307 → 3306      # 3307 은 로컬 compose 가 매핑한 포트일 뿐이다
DB_USER/PASSWORD 운영 계정
OPENAI_API_KEY   운영 키
```

나머지(`DB_NAME`, `OPENAI_MODEL`, 조언 규격)는 그대로 간다.

---

## 6. 동작상 주의

- **실패한 행은 컬럼을 NULL로 남긴다.** 조회 조건이 `child_advice IS NULL OR parent_advice IS NULL`
  이라 다음 실행 때 자동으로 다시 대상이 된다.
- **길이는 스키마로 강제되지 않는다.** Structured Outputs가 막아주는 건 JSON 형식뿐이라,
  90자 제한은 `generator.py`가 직접 재고 넘치면 재생성시킨다.
- **`child_advice`에 값이 있어도 AI 조언이 아닐 수 있다.** 백엔드 배치가 유형 설명 문구를
  넣어두기 때문에 채워진 것처럼 보인다.
- **`top_spots`는 앞 3개만 쓴다.** 백엔드가 5개를 넣어두므로 프롬프트 단계에서 자른다.
- **`merchants.category`(업종)는 쓰지 않는다.** 정식 데이터가 아닌 목업이다.
  가맹점에서 쓸 수 있는 건 상호명뿐이다.

---

## 7. 아직 안 된 것

- 조언 **어투가 흔들린다** — 반말/존댓말 혼용, 프롬프트 지시문이 결과 문장에 새어 나옴
- **모델 미확정** — `gpt-5-nano` / `gpt-4o-mini` 중 품질 보고 결정
- **스케줄러 없음** — 실행 주체(cron / Actions / 수동) 미정
- **테스트 코드 없음**
- 과거 월(2026-04~06) 백필 여부 미정
