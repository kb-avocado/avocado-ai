# avocado-ai

월간 소비 리포트(`child_spending_reports`)에 **AI 조언 2개**(아이용 / 보호자용)를 채워 넣는 배치.

REST API를 서빙하지 않고, 백엔드와 통신하지도 않는다. **같은 MySQL을 직접 UPDATE** 한다.
배경·규격·제약은 레포 밖 `../ONBOARDING.md` 참고.

## 준비

```bash
# 1. DB (백엔드 레포의 compose)
cd ../avocado-backend && docker compose up -d mysql

# 2. 가상환경 + 설치
cd ../avocado-ai
py -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .

# 3. 환경변수
cp .env.example .env
#   DB_PASSWORD      → 백엔드 .env 의 MYSQL_PASSWORD 와 같은 값
#   OPENAI_API_KEY   → 발급받은 키
```

`.env` 는 `.gitignore` 처리되어 있다. **커밋 금지.**

## 실행

```bash
PY=./.venv/Scripts/python.exe

# DB 붙는지 + 리포트 데이터 있는지만 확인 (OpenAI 호출 없음)
$PY -m avocado_ai.main --check

# DB 없이 9종 유형 샘플로 생성만 (프롬프트·품질 확인용)
$PY -m avocado_ai.main --sample
$PY -m avocado_ai.main --sample --show-prompt   # 실제 프롬프트도 출력

# 한 명분 생성, DB 는 안 건드림
$PY -m avocado_ai.main --year 2026 --month 7 --child-id 19 --dry-run

# 지난달 전체 순회 후 실제 UPDATE
$PY -m avocado_ai.main
```

`--year`/`--month` 를 생략하면 **Asia/Seoul 기준 지난달**이 대상이다.

## 구조

| 파일            | 역할                                                          |
| --------------- | ------------------------------------------------------------- |
| `config.py`     | `.env` 로딩                                                   |
| `db.py`         | PyMySQL 커넥션 (utf8mb4 / `+09:00` 고정)                      |
| `repository.py` | 대상 조회 (전월 행 LEFT JOIN), advice UPDATE                  |
| `prompt.py`     | 유형별 제안 방향, 만 6세 어휘 규칙, 응답 JSON 스키마          |
| `generator.py`  | OpenAI 호출 + 길이 검증 + 재시도                              |
| `main.py`       | CLI                                                           |

## 배포

**`.env` 파일을 서버에 올리지 않는다.** 환경변수로 주입한다.

`load_dotenv()` 는 이미 존재하는 환경변수를 덮어쓰지 않으므로, 실제 환경변수가 항상 `.env` 를 이긴다.
덕분에 환경별로 파일을 나눌 필요가 없다 — `.env.example` 은 "어떤 값이 필요한지" 목록 하나면 된다.

| 실행 주체      | 주입 방법                                                  |
| -------------- | ---------------------------------------------------------- |
| GitHub Actions | 리포지토리 Secrets → `env:` 블록 (`.env` 파일 자체가 불필요) |
| 서버 cron      | systemd `EnvironmentFile=`, 또는 서버에 `.env` + `chmod 600` |
| Docker         | `-e` / compose `environment:` / secrets                    |

로컬과 달라지는 값은 이것뿐이다.

```
DB_HOST          127.0.0.1 → 운영 DB 주소
DB_PORT          3307 → 3306      # 3307 은 로컬 compose 가 매핑한 포트일 뿐이다
DB_USER/PASSWORD 운영 계정
OPENAI_API_KEY   운영 키
```

나머지(`DB_NAME`, `OPENAI_MODEL`, 조언 규격)는 그대로 간다.

## 동작상 주의

- **실패한 행은 컬럼을 NULL 로 남긴다.** 다음 실행 때 자동으로 다시 대상이 된다
  (조회 조건이 `child_advice IS NULL OR parent_advice IS NULL`).
- **길이는 스키마로 강제되지 않는다.** Structured Outputs 가 막아주는 건 JSON 형식뿐이라,
  90자 제한은 `generator.py` 가 직접 재고 넘치면 재생성시킨다.
- **`top_spots` 는 앞 3개만 쓴다.** 백엔드가 5개를 넣어두기 때문에 프롬프트 단계에서 자른다.
- **가맹점 상호명은 기본적으로 프롬프트에 넣지 않는다** (`INCLUDE_MERCHANT_NAMES=false`).
  전 사용자가 만 14세 미만이라 식별 가능한 값은 빼는 쪽으로 잡았다.
