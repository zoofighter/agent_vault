---
title: AgentVault 작업 백로그
type: backlog
updated: 2026-05-15
---

# AgentVault 작업 백로그

## 즉시 필요

| 작업 | 설명 |
|------|------|
| `run_daily.sh` HTML/PDF 배치 연동 | `report_download/`에 쌓인 파일을 07:00/18:00 배치에서 자동 처리 |
| Alphabet/Google 중복 정리 | `companies.csv`에 GOOGL 티커 두 개 — 노트가 Google로만 저장됨 |
| `20250910_구글_분석.md` 처리 | `report_download/`에 방치된 `.md` 파일 수동 등록 또는 배치 지원 추가 |

## 안정성

| 작업 | 설명 |
|------|------|
| 배치 실패 시 Telegram 자동 알림 | LaunchAgent 에러 종료 시 즉시 알림. 현재는 로그 직접 확인 필요 |
| ChromaDB 자동 헬스체크 | 배치 시작 시 컬렉션 이상(차원 불일치, 손상) 감지 → 자동 재구축 트리거 |

## 필터 품질

| 작업 | 설명 |
|------|------|
| 회사별 맞춤 임베딩 쿼리 | 뉴스 제목+스니펫에 회사 프로필·투자 메모 핵심 문장을 함께 쿼리 → 필터 정확도 향상 |
| LLM 거절 패턴 확장 | `_REJECT_PHRASES`에 없는 거절 표현 누락으로 무관 기사 통과 가능성 존재 |

## 사용성

| 작업 | 설명 |
|------|------|
| Telegram Bot `/research` 명령 | `/research SK하이닉스` 입력 시 최신 Research 노트 요약 반환 |
| 주간 Digest 롤업 | `agent_vault/Digest/` 일별 기록을 주간 단위로 자동 요약 |

## 파이프라인 확장

| 작업 | 설명 |
|------|------|
| YouTube Summary → Research 연동 | `/a_0515_youtube_summary` 결과물을 Research 폴더로 자동 등록 |
| 뉴스 소스 추가 | Reuters/Bloomberg RSS, SEC EDGAR 공시 등 영문 소스 보강 |
| 11개 섹터 심층 분석 자동화 | `docs/sector-deep-analysis.md` 설계 기반 섹터별 주간 리포트 자동 생성 (`run_tech_report_weekly.py` 활용) |

## 완료

| 날짜 | 작업 |
|------|------|
| 2026-05-15 | HTML 배치 등록 (`run_html_reports.py`) |
| 2026-05-15 | PDF 배치 등록 (`run_pdf_reports.py`) |
| 2026-05-15 | 임베딩 모델 교체 nomic-embed-text → bge-m3 |
| 2026-05-15 | ChromaDB `sample_vault/` 잔존 데이터 정리 |
| 2026-05-15 | TechReport Phase 2 Commander 자동 트리거 개선 (폴백 + 크로스런 중복 방지) |
| 2026-05-15 | `_SIM_THRESHOLD` 0.50 → 0.55 (bge-m3 거리 분포 기반) |
