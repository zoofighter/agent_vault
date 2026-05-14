# CLAUDE.md — AgentVault

## 프로젝트 개요

**AgentVault** — 여러 AI 에이전트가 협력하여 매일 나 대신 뉴스를 읽고,
Obsidian 볼트에 축적된 리서치를 필터 삼아 관련 뉴스만 골라 Daily 노트로 저장하는 개인 투자 인텔리전스 시스템.

- 단순 키워드 필터가 아닌 **볼트에 쓴 내 글**이 필터 기준
- 선택된 뉴스마다 "왜 관련 있는지" 근거 텍스트 자동 생성
- 볼트가 커져도 **변경된 파일만 증분 임베딩** → 일일 실행 시간 일정 유지

시스템 상세: [docs/system-overview.md](docs/system-overview.md)

## 에이전트 구조

```
Memory Agent   → 볼트 변경 파일 임베딩 (ChromaDB)
Scout Agent    → 8개 소스에서 38개사 뉴스 수집
Filter Agent   → 유사도 필터 + LLM 근거 생성
Analyst Agent  → 종합 분석 합성
Scribe Agent   → Daily 노트 저장
Research Agent → 증권사 PDF 수집·요약
```

## 현재 구현 상태

| 파일 | 역할 | 상태 |
|------|------|------|
| `companies.csv` | 기업 레지스트리 38개사 | ✅ |
| `collect_news.py` | 전체 파이프라인 오케스트레이터 | ✅ |
| `run_daily.sh` | 일일 배치 (07:00 / 18:00) | ✅ |
| `migrate_vault.py` | 볼트 구조 마이그레이션 | ✅ |
| `src/obsidian/company_manager.py` | 볼트 폴더 동기화, `company_dir()` 경로 기준 | ✅ |
| `src/obsidian/indexer.py` | mtime+MD5 변경 감지 | ✅ |
| `src/obsidian/embedder.py` | ChromaDB 증분 임베딩, 손상 자동 복구 | ✅ |
| `src/obsidian/writer.py` | Daily 노트 저장 (종합분석 + 뉴스목록 단일 파일) | ✅ |
| `src/obsidian/templates.py` | 기업 프로필 마크다운 템플릿 | ✅ |
| `src/sources/` | 뉴스 소스 8종 (Naver/DDG/Yahoo/GoogleNews/HKEX/TWSE/TSE) | ✅ |
| `src/scraper/fetcher.py` | BeautifulSoup 본문 추출 | ✅ |
| `src/llm/analyzer.py` | 벡터 유사도 필터 + LLM 근거 생성 | ✅ |
| `src/llm/curator.py` | 종합 분석 합성 `synthesize()` | ✅ |
| `src/research/naver_research.py` | KRX 리서치 PDF 수집 + LLM 요약 | ✅ |
| `src/research/naver_industry.py` | 해외 기업 산업분석 리포트 수집 | ✅ |
| `src/research/register_pdf.py` | 로컬 PDF 수동 등록 | ✅ |
| `agent_vault/` | 38개사 볼트 (KR/US/CN/TW/JP/Private) | ✅ |
| `src/obsidian/inbox.py` | Inbox.md 알림 공유 헬퍼 | ✅ |
| `src/commander/` | Commander Agent — Daily 분석 → Inbox 액션 명령 | ✅ |
| `src/content/` | Content Writer Agent — Daily → 블로그/유튜브 초안 | ✅ |
| `run_commander.py` | Commander Agent CLI | ✅ |
| `run_content.py` | Content Writer Agent CLI | ✅ |
| `run_briefing.py` | Briefing Agent — 대화체 브리핑 → Telegram 전송 | ✅ |
| `run_telegram_bot.py` | Telegram Bot — 양방향 명령 인터페이스 | ✅ |
| `archive_daily.sh` | 30일 이상 Daily 노트 Archive/ 폴더로 이동 | ✅ |
| `src/telegram/` | Telegram 단방향 전송 + Bot 핸들러 | ✅ |
| `src/obsidian/digest.py` | Digest/{date}.md 기록 헬퍼 | ✅ |

## 기업 관리

기업 추가/수정은 `companies.csv` 편집 후 동기화 실행.

```bash
# 현황 확인
python -m src.obsidian.company_manager --vault ./agent_vault --status

# 볼트 동기화 (새 기업 파일 자동 생성, 기존 파일 보호)
python -m src.obsidian.company_manager --vault ./agent_vault

# 변경 없이 미리보기
python -m src.obsidian.company_manager --vault ./agent_vault --dry-run
```

`active: false` 설정 시 뉴스 수집 제외 (볼트 파일은 유지).

## 볼트 구조

거래소 지역별 하위폴더로 38개사 관리.

```
agent_vault/
└── Companies/
    ├── KR/          삼성전자 · SK하이닉스 · 현대차 · LG에너지솔루션 · 포스코홀딩스
    ├── US/          Apple · NVIDIA · Microsoft · Alphabet · Google · Amazon 외 12개
    ├── CN/          Tencent · Alibaba · CATL · BYD · Xiaomi
    ├── TW/          TSMC · MediaTek · Delta Electronics · Nanya
    ├── JP/          SoftBank · Kioxia · Tokyo Electron
    └── Private/     OpenAI · Anthropic · SpaceX

    각 기업 폴더:
    ├── {기업명}.md    프로필 — 시스템 자동 생성, 이후 덮어쓰지 않음
    ├── Daily/         일일 뉴스 노트 — 시스템 전용
    ├── Research/      증권사 리포트 요약 — 시스템 전용
    └── Memos/         투자 메모 — 사용자 전용, 시스템 수정 불가
```

Daily 파일명: `{날짜}{순서}.md` (예: `2026-05-14a.md`, `2026-05-14b.md`)

## 기술 스택

| 영역 | 선택 |
|------|------|
| 임베딩 | `nomic-embed-text` (Ollama, 로컬) |
| 벡터 DB | ChromaDB (`data/chroma/`) |
| 분석 LLM | `llama3.2` (Ollama, 로컬) |
| 뉴스 소스 | Naver API, DuckDuckGo, Yahoo Finance, Google News RSS, HKEX/TWSE/TSE 공시 |
| 본문 추출 | BeautifulSoup → Playwright 폴백 |
| 자동화 | macOS LaunchAgent (07:00 / 18:00) |

## 설계 원칙

- **증분 인덱싱**: mtime + MD5로 변경 파일만 재임베딩
- **2단계 필터**: 벡터 유사도 사전 필터 → 통과 기사만 LLM 처리 (비용 절감)
- **비파괴 동기화**: 기존 프로필·메모 파일 덮어쓰지 않음
- **부분 실패 허용**: 소스 하나 실패해도 전체 파이프라인 중단 없음
- **단일 경로 출처**: `company_dir()` 함수가 모든 경로의 기준
