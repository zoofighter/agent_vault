---
title: Commander Agent — 요건 정의
type: design-doc
status: draft
created: 2026-05-14
---

# Commander Agent

> "시스템이 먼저 말을 건다 — 사용자가 읽는 것이 아니라 명령을 받는다"

AgentVault가 뉴스를 수집해 Daily 노트에 저장하는 **인바운드** 파이프라인이라면,
Commander Agent는 그 결과를 분석하여 사용자에게 액션 아이템을 푸시하는 **아웃바운드** 레이어다.

---

## 1. 역할과 목표

| 구분 | AgentVault | Commander Agent |
|------|-----------|----------------|
| 방향 | 뉴스 → 볼트 저장 | 볼트 분석 → 사용자 지시 |
| 주체 | 시스템이 수집 | 시스템이 판단 |
| 사용자 행동 | 볼트를 직접 읽음 | 명령을 받아 심층 분석 수행 |

**목표**: 볼트를 매일 직접 읽지 않아도 중요한 신호를 놓치지 않도록.
중요도가 높은 항목만 선별해 사용자에게 구체적 액션을 지시한다.

---

## 2. 명령 유형 (Command Types)

| 유형 | 트리거 조건 | 예시 메시지 |
|------|-----------|------------|
| **리포트 발견** | 신규 고품질 리포트 감지 | "삼성전자 HBM 분석 리포트 발견 → 심층 분석 권장" |
| **테마 급등** | N개 기업에서 동일 키워드 동시 급증 | "반도체 CoWoS 테마 5사 동시 언급 → 섹터 리뷰 필요" |
| **Thesis 충돌** | 볼트 투자근거와 반대 방향 뉴스 지속 | "현대차 EV 부정 시그널 3일 연속 → 투자 thesis 재검토" |
| **심층 분석 프롬프트** | 중요도 상위 기사 클러스터 감지 | Claude에게 바로 물어볼 구체적 질문 생성 후 전달 |
| **주간 리뷰** | 매주 일요일 스케줄 | 한 주 핵심 테마 3가지 + 다음 주 주목 포인트 |

### 명령 메시지 형식 (Telegram)

```
[★★★★] 삼성전자 — HBM4 공급 우선권 확보 보도

근거: 오늘 Daily 노트에서 HBM4 관련 기사 7건 집중. 볼트의
HBM 경쟁력 분석 문서와 높은 유사도.

권장 액션:
→ python collect_news.py --companies "삼성전자" --deep
→ 또는 Claude에게: "삼성전자 HBM4 공급망 변화가 SK하이닉스
   점유율에 미치는 영향을 분석해줘"
```

---

## 3. LLM 이중 구조

```
Daily Notes
    │
    ▼
[Local LLM — Ollama llama3.2]
    • 중요도 점수 계산 (0~1)
    • 키워드 클러스터링
    • Thesis 충돌 탐지
    │
    ├── 점수 < 임계값 → skip
    │
    └── 점수 ≥ 임계값
            │
            ▼
        [Cloud LLM — Claude API]
            • 고품질 분석 명령 텍스트 생성
            • 사용자가 물어볼 구체적 질문 작성
            • 중요도 ★ 등급 부여
            │
            ▼
        [Telegram Push]
```

**비용 제어**: Local LLM이 1차 필터. Cloud LLM은 하루 상위 N건(기본 3건)에만 적용.

---

## 4. 전달 채널

| 채널 | 용도 | 비고 |
|------|------|------|
| **Telegram** | 실시간 푸시 (메인) | 기존 봇 재사용 |
| **Obsidian Digest** | 명령 이력 기록 (백업) | `Digest/2026-05-14-commander.md` |

---

## 5. 트리거

### 스케줄 기반
- Daily 노트 생성 직후 자동 실행 → `run_daily.sh`의 **Phase D**로 추가
- 주간 리뷰: 매주 일요일 오전 8시 별도 LaunchAgent

### 이벤트 기반 (향후)
- 뉴스 볼륨 전일 대비 200% 이상 급증
- ★★★★★ 등급 기사 단독 감지 시 즉시 푸시

---

## 6. 파일 구조

```
src/commander/
├── __init__.py
├── scanner.py      # Daily 노트 읽기 + Local LLM 중요도 평가
├── dispatcher.py   # Cloud LLM으로 액션 명령 텍스트 생성
└── notifier.py     # Telegram 전송 + Digest 노트 저장

run_commander.sh    # 독립 실행 or run_daily.sh에서 호출
```

### 주요 인터페이스

```python
# scanner.py
def scan_daily_notes(vault_path: Path, date_str: str) -> list[ScanResult]:
    """오늘 Daily 노트 전체 읽기 → Local LLM 중요도 평가 → 상위 반환"""

# dispatcher.py
def generate_commands(results: list[ScanResult]) -> list[Command]:
    """중요도 상위 항목 → Cloud LLM → 액션 명령 텍스트 생성"""

# notifier.py
def push(commands: list[Command], telegram_chat_id: str) -> None:
    """Telegram 전송 + Digest 노트 저장"""
```

---

## 7. 미결 설계 결정

| 항목 | 현재 상태 | 결정 필요 |
|------|---------|---------|
| Cloud LLM 모델 | claude-sonnet-4-5 예정 | API 비용 vs 품질 |
| 중요도 임계값 | 미정 | 초기값 0.7, 실사용 후 조정 |
| 하루 최대 명령 수 | 미정 | 3~5건 권장 (알림 피로 방지) |
| 명령에 CLI 커맨드 포함 여부 | 미정 | 사용자가 터미널에서 바로 실행 가능 형식 포함 검토 |
| 주간 리뷰 형식 | 미정 | Telegram 단문 vs Obsidian 장문 |

---

## 8. 확장 가능성

- **포트폴리오 연동**: 보유 비중이 높은 종목 명령 우선순위 상향
- **사용자 피드백 루프**: "유용함/불필요함" 반응 → 중요도 모델 재학습
- **멀티 채널**: Slack, 이메일, SMS 추가
- **인터랙티브 모드**: Telegram에서 명령 받아 Claude가 즉시 분석 수행 후 결과 반환
