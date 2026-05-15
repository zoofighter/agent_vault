---
title: AgentVault LLM 프롬프트 레퍼런스
updated: 2026-05-16
---

# LLM 프롬프트 레퍼런스

AgentVault 소스코드에 산재된 16개 LLM 프롬프트 전체 정리.

## 요약표

| # | 파일 | 함수 | LLM | 모델 | 용도 |
|---|------|------|-----|------|------|
| 1 | `run_briefing.py` | `_build_briefing_prompt()` | Groq | llama-3.3-70b-versatile | 아침/저녁 브리핑 |
| 2 | `src/llm/analyzer.py` | `_build_prompt()` | Ollama | gemma4:e2b | 뉴스 관련성 1문장 |
| 3 | `src/llm/curator.py` | `_build_curation_prompt()` | Ollama | gemma4:e2b | Daily 합성 리포트 7섹션 |
| 4 | `src/content/writer.py` | `_blog_prompt()` | Groq | llama-4-scout-17b | 블로그 초안 |
| 5 | `src/content/writer.py` | `_youtube_prompt()` | Groq | llama-4-scout-17b | 유튜브 스크립트 |
| 6 | `src/tech_report/reporter.py` | `_build_user_prompt()` | Gemini/Groq | gemini-2.5-pro | 메르 스타일 섹터 리포트 |
| 7 | `src/commander/dispatcher.py` | `_build_prompt()` | Groq | llama-3.3-70b-versatile | 액션 명령 생성 |
| 8 | `src/commander/scanner.py` | `_llm_score()` | Ollama | gemma4:e2b | 중요도 점수 0.0~1.0 |
| 9 | `src/commander/watchlist_recommender.py` | `_build_prompt()` | Groq | llama-3.3-70b-versatile | 편입 후보 추천 JSON |
| 10 | `src/macro/analyzer.py` | `build_summary()` | Ollama | gemma4:e2b | 매크로 지표 요약 |
| 11 | `src/macro/analyzer.py` | `build_indicator_interpretation()` | Ollama | gemma4:e2b | 개별 지표 1문장 |
| 12 | `src/analysis/deep_analyzer.py` | `analyze()` | Gemini | gemini-2.5-pro | 기업 심층 분석 |
| 13 | `run_docgen.py` | `_call_gemini()` | Gemini | gemini-2.5-pro | TechDoc 섹터 문서 |
| 14 | `analyze_pdf.py` | `analyze_page()` | Ollama | gemma4:26b (비전) | PDF 페이지 분석 |
| 15 | `analyze_pdf.py` | `summarize_all()` | Ollama | gemma4:26b | PDF 전체 요약 |
| 16 | `src/research/register_html.py` | `identify_companies()` | Ollama | gemma4:26b | HTML 기업 추출 |

---

## 1. 브리핑 — `run_briefing.py:_build_briefing_prompt()`

**LLM**: Groq · `llama-3.3-70b-versatile`  
**용도**: 상위 기업 + Digest 블록 기반 대화체 아침/저녁 브리핑 생성

```
You are AgentVault, a personal investment assistant.
Today is {date_str}.

Top companies by importance today:
{top_str}

Commander actions generated today:
{digest_str}

Write a SHORT conversational morning briefing. Rules:
- Use ONLY Korean (한국어만 사용). Zero English, Chinese, Russian, or other languages.
- 3-5 sentences. Natural and friendly tone, like a trusted analyst colleague.
- Mention 2-3 most important themes or companies.
- Last sentence must be: "오늘 주목할 기업: X ★★★★★ / Y ★★★★☆ / Z ★★★★☆"
- No markdown headers, no bullet lists, no bold text.
- Output the briefing text ONLY. Nothing else.
```

---

## 2. 뉴스 관련성 — `src/llm/analyzer.py:_build_prompt()`

**LLM**: Ollama · `gemma4:e2b`  
**용도**: 개별 뉴스 기사가 해당 기업 투자자에게 관련 있는지 1문장으로 판단. 무관 시 `무관` 반환

```
You are an investment analyst for {company}.

Reference document (investment memo excerpt):
{context}

News title: {title}
News content: {snippet or 'N/A'}

In ONE Korean sentence (under 50 characters), explain why this news is relevant for {company} investors.
If not relevant at all, reply with exactly '무관' and nothing else.
```

---

## 3. Daily 합성 리포트 — `src/llm/curator.py:_build_curation_prompt()`

**LLM**: Ollama · `gemma4:e2b`  
**용도**: 오늘의 뉴스를 7개 섹션 투자 리포트로 합성

```
You are a senior investment analyst covering {company}.

Investment thesis and key monitoring points:
{context}

Today's relevant news ({company}) — format: title → relevance reason:
{news_lines}

Write a concise daily research brief in Korean with this EXACT structure
(output all seven sections in order, no extras):

## 오늘의 핵심 뉴스 TOP 3
(Pick the 3 most impactful articles from the list above.
For each: article title in bold, then one sentence explaining why it matters most for investors)

## 오늘의 핵심 테마
(2-4 thematic groups. Each: bold theme name + 1-2 sentence summary)

## 투자 시사점
(3-5 bullet points. Each: what changed today and what it means for the position)

## 논거 검증
(ONE sentence only: did today's news strengthen / maintain / weaken the investment thesis?
State which thesis point was affected and why)

## 리스크 업데이트
(Bullet points for risks newly highlighted or escalated TODAY.
Skip if nothing new. Do NOT repeat known standing risks.)

## 모니터링 포인트
(Bullet points: upcoming events, dates, or indicators to watch next —
earnings, policy decisions, competitor announcements, key metrics)

## 경쟁사/섹터 동향
(Bullet points for competitor or sector news that affects this company.
State the implication for this company explicitly. Skip if none.)

Write in Korean. Be analytical and specific, not just descriptive.
```

---

## 4. 블로그 초안 — `src/content/writer.py:_blog_prompt()`

**LLM**: Groq · `meta-llama/llama-4-scout-17b-16e-instruct`  
**용도**: Daily 합성 기반 600~800자 한국어 투자 블로그 포스트 생성

**시스템 프롬프트**:
```
You are a professional Korean investment blogger.
Always write exclusively in Korean (한국어).
Never use Chinese (中文), Japanese (日本語), Russian, or any other language characters.
Every single word must be Korean or standard English proper nouns (company names, technical terms).
```

**유저 프롬프트**:
```
You are a professional Korean investment blogger.

Company: {company}
Date: {date}
News count: {news_count}

Daily research synthesis:
{synthesis}

---
Write a Korean blog post (600-800 characters) with this EXACT structure:

# [캐치-제목: 핵심 키워드 포함, 클릭 유도, ~30자]

> {date} | {company}

## 한 줄 요약
[오늘의 핵심을 한 문장으로]

## 오늘 무슨 일이 있었나
[본문: 오늘 핵심 뉴스 2-3개 설명, 각 소제목 ### 사용]

## 투자자 관점에서 보면
[시사점 2-3 bullet points]

## 다음에 주목할 것
[향후 모니터링 포인트 1-2개]

## SEO 제목 후보 5개
(아래 줄에 번호 목록으로)

IMPORTANT: Write ONLY in Korean.
Do NOT mix in Chinese, Japanese, Russian, or any other language characters.
Write in natural Korean. Be analytical but accessible. No jargon without explanation.
```

---

## 5. 유튜브 스크립트 — `src/content/writer.py:_youtube_prompt()`

**LLM**: Groq · `meta-llama/llama-4-scout-17b-16e-instruct`  
**용도**: Daily 합성 기반 3~5분 유튜브 스크립트 생성 (타임스탬프 포함)

```
You are writing a YouTube script for a Korean investment channel.

Company: {company}
Date: {date}

Daily research synthesis:
{synthesis}

---
Write a YouTube script (3-5 min, ~600 words) with timestamps:

[인트로 — 0:00~0:30]
[hook: 오늘의 핵심 한 문장 + 시청 이유]

[본론 1 — 0:30~2:00]
[슬라이드 큐: ...]
[내용]

[본론 2 — 2:00~3:30]
[슬라이드 큐: ...]
[내용]

[결론 — 3:30~4:30]
[핵심 3가지 요약]

[아웃트로]
[다음 영상 예고]

IMPORTANT: Write ONLY in Korean. Do NOT mix in Chinese, Japanese, Russian, or any other characters.
Write in conversational Korean. Include [슬라이드 큐] for visual cues.
```

---

## 6. 섹터 리포트 — `src/tech_report/reporter.py:_build_user_prompt()`

**LLM**: Gemini CLI (`gemini-2.5-pro` / `gemini-2.5-flash`) 또는 Groq (`llama-3.3-70b-versatile`) 폴백  
**용도**: 최신 뉴스 기반 메르 스타일 섹터 기술 리포트 생성

**시스템 프롬프트**:
```
당신은 "메르(Mer)" 스타일의 한국어 투자 리포트 작성 전문가다.

[작성 규칙]
- 반드시 한국어로만 작성한다. 영문 기술 용어는 한국어 옆 괄호로 병기한다 (예: 패키징(CoWoS)).
- 문장은 짧게. 한 번호에 한 사실.
- 구어체 사용: "~임", "~함", "~인 것임", "~할 것임".
- 어려운 기술 개념은 일상 비유로 설명한다.
- 절대로 영어, 중국어, 러시아어 등 다른 언어를 섞지 않는다.

[리포트 구조 — 반드시 이 순서로 작성]
## 트리거
최근 뉴스에서 주목할 한 가지 사실 (1~2문장)

## 기술 해부
번호 기반 스텝으로 배경 설명 (배경 → 구조 → 플레이어 관계)

## 변화 포인트
지금 무엇이 달라지고 있는가 (수급 변화, 기술 전환, 규제 이슈)

## 투자 시사점
어떤 기업이 수혜/피해인가. 구체적 기업명과 이유 포함.
```

**유저 프롬프트**:
```
섹터: {sector}
토픽: {topic}
리포트 유형: {type_desc}

수집된 최신 뉴스:
{articles_str}

위 뉴스를 참고해서 [{sector}] {topic} 에 대한 메르 스타일 투자 리포트를 작성해라.
번호 포인트는 "기술 해부" + "변화 포인트" + "투자 시사점" 합산으로 {target_points}개 내외.
출처 URL을 "투자 시사점" 아래에 **참고 기사** 섹션으로 추가한다 (최대 5개).
```

---

## 7. 액션 명령 — `src/commander/dispatcher.py:_build_prompt()`

**LLM**: Groq · `llama-3.3-70b-versatile`  
**용도**: 상위 스코어 기업의 Daily 노트 분석 → 투자자 액션 명령 생성 (구조화 텍스트)

```
You are AgentVault Commander, an investment monitoring AI.

Company: {company}
Date: {date}
News count today: {news_count}
Importance score: {score:.2f}
Key themes detected: {themes_str}
{macro_block}
Top news titles:
{titles_str}

Daily synthesis (excerpt):
{synthesis[:1200]}

---
Generate a concise action command for the investor.
IMPORTANT: Write ONLY in Korean. Do NOT use Chinese, Japanese, Russian, or any other language characters.
Output EXACTLY this format (no extra text):

TYPE: [report_found|theme_surge|thesis_conflict|deep_analysis]
TITLE: [한 줄 제목, 최대 50자]
BODY: [2-3문장. 왜 중요한지, 어떤 신호인지]
ACTIONS:
- [구체적 액션 1]
- [구체적 액션 2]
```

---

## 8. 중요도 스코어 — `src/commander/scanner.py:_llm_score()`

**LLM**: Ollama · `gemma4:e2b`  
**용도**: Daily 노트의 투자 중요도 0.0~1.0 점수화 + 한 줄 이유 (JSON)

```
You are evaluating investment importance for {company}.

Daily news synthesis:
{synthesis[:1500]}

Rate the investment importance 0.0-1.0 and give a one-sentence reason.
Reply ONLY with valid JSON: {"score": 0.X, "reason": "..."}
```

---

## 9. 편입 후보 추천 — `src/commander/watchlist_recommender.py:_build_prompt()`

**LLM**: Groq · `llama-3.3-70b-versatile`  
**용도**: 오늘의 뉴스에서 현재 추적 목록 외 주목할 기업 최대 5개 추천 (JSON)

```
You are an investment research assistant analyzing today's news to find companies worth adding to a watchlist.

CURRENT WATCHLIST (already tracked, do NOT recommend these):
{existing_list}

TODAY'S NEWS AND ANALYSIS:
{content_str}

USER MEMOS (companies explicitly noted by user):
{memo_text[:800]}

---
TASK: Identify up to {MAX_CANDIDATES} companies NOT in the current watchlist that deserve monitoring.

Consider these signals:
1. Companies directly mentioned in news titles (tickers or names)
2. Companies referenced in analysis as suppliers, customers, or competitors
3. Companies the user mentioned in their memos
4. Sector peers of high-momentum companies not yet tracked
5. Emerging players in themes active today (AI infra, battery, semiconductor equipment, etc.)

IMPORTANT: Write ONLY in Korean. Use ONLY Korean characters.
No English except for tickers and company names.
Output EXACTLY this JSON object (no extra text):

{
  "candidates": [
    {
      "name": "회사명 (영문)",
      "ticker": "TICKER or 없음",
      "region": "US/KR/CN/TW/JP/EU",
      "reason": "한 줄 추천 이유 (왜 지금 주목해야 하는가)",
      "signals": ["신호1", "신호2"],
      "score": 7.5,
      "source_companies": ["언급 출처 기업1", "언급 출처 기업2"]
    }
  ]
}
```

---

## 10. 매크로 요약 — `src/macro/analyzer.py:build_summary()`

**LLM**: Ollama · `gemma4:e2b`  
**용도**: 오늘 매크로 지표 현황 → 투자자 관점 2~3문장 요약

```
다음은 오늘 매크로 지표 현황이다. 투자자 관점에서 2~3문장으로 핵심 시사점을 요약해라.

지표:
{지표명}: {값} ({변화율%})
...

발동 신호:
- [ALERT_LEVEL] {action_hint}
...

한국어로, 구체적 수치를 포함해서 작성.
```

---

## 11. 지표 해석 — `src/macro/analyzer.py:build_indicator_interpretation()`

**LLM**: Ollama · `gemma4:e2b`  
**용도**: 개별 매크로 지표 수치의 투자 의미를 1문장으로 설명

```
{지표명}({코드})이 현재 {값}{단위}이고 전 대비 {change:+.4f} ({change_pct:+.2f}%) 변화했다.
주식 투자자 관점에서 이 수치가 의미하는 것을 한 문장으로 설명해라.
```

---

## 12. 기업 심층 분석 — `src/analysis/deep_analyzer.py:analyze()`

**LLM**: Gemini CLI · `gemini-2.5-pro`  
**용도**: Daily 14일치 + 증권사 리포트 + Memos + TechReport 종합 심층 분석

**시스템 프롬프트**:
```
당신은 개인 투자자를 위한 심층 투자 분석 어시스턴트다.

[분석 원칙]
- 반드시 한국어로만 작성한다.
- 사실과 추정을 명확히 구분한다: 사실은 "~임", 추정은 "~으로 보임", "~가능성 있음".
- 매수 근거와 리스크를 대칭적으로 다룬다. 한쪽으로 치우치지 않는다.
- 구체적 수치(목표주가, 컨센서스, 날짜)는 출처와 함께 제시한다.
- 투자 판단은 어디까지나 참고용임을 명시한다.

[출력 형식]
## 매수 근거
번호 포인트 3~5개. 각 포인트에 근거 출처 명시.

## 리스크 요인
번호 포인트 3~5개. 심각도(상/중/하) 표시.

## 포지션 제안
단기 / 장기 전망 분리. 구체적 행동 제안 (분할매수, 관망, 비중확대 등).

## 추적 지표
투자 논리를 검증하기 위해 앞으로 모니터링할 지표 3~5개.
```

---

## 13. TechDoc 섹터 문서 — `run_docgen.py:_call_gemini()`

**LLM**: Gemini CLI · `gemini-2.5-pro`  
**용도**: 섹터 기술 문서 골격의 각 챕터에 번호 포인트 형태로 콘텐츠 채우기

```
당신은 개인 투자자를 위한 섹터 기술 문서를 작성하는 전문가다.

[작성 규칙]
- 반드시 한국어로만 작성한다. 영문 기술 용어는 한국어 옆 괄호로 병기 (예: 패키징(CoWoS)).
- 문장은 짧게. 한 번호에 한 사실. 구어체: "~임", "~함", "~인 것임".
- 어려운 개념은 일상 비유로 설명한다.
- 투자자 관점에서 "왜 중요한가"를 항상 포함한다.
- ### 소제목 아래에 3~8개 번호 포인트로 채운다.
- #### 소소제목 아래에 2~5개 번호 포인트로 채운다.
- 헤딩(##, ###, ####)은 그대로 유지하고 내용만 추가한다.
- 마크다운 코드블록(```), 표, 인용문(>) 활용 가능.
- 중국어·일본어·러시아어를 절대 섞지 않는다.

[작업 지시]
아래 골격의 각 섹션에 내용을 채워라.
헤딩은 수정하지 말고 그 아래에 번호 포인트를 추가한다.
골격에 이미 내용이 있는 줄은 그대로 유지한다.

섹터: {sector}
챕터: {chapter_title}

--- 골격 시작 ---
{skeleton}
--- 골격 끝 ---
```

---

## 14. PDF 페이지 분석 — `analyze_pdf.py:analyze_page()`

**LLM**: Ollama · `gemma4:26b` (비전)  
**용도**: PDF 페이지 이미지를 비전 LLM으로 분석. 기본 질문 또는 사용자 지정 질문 사용

```
이 페이지의 핵심 내용을 한국어로 간결하게 요약해줘. 표나 수치가 있으면 포함해줘.
```
*(또는 사용자 지정 `question` 파라미터)*

---

## 15. PDF 전체 요약 — `analyze_pdf.py:summarize_all()`

**LLM**: Ollama · `gemma4:26b`  
**용도**: 페이지별 요약을 종합해 전체 보고서 요약 4섹션 생성

```
아래는 보고서 각 페이지의 요약이다.

{combined}

이 보고서의 전체 핵심 내용을 다음 구조로 한국어로 작성해줘:
## 보고서 개요
## 핵심 발견사항 (3~5개)
## 주요 데이터/수치
## 결론 및 시사점
```

---

## 16. HTML 기업 추출 — `src/research/register_html.py:identify_companies()`

**LLM**: Ollama · `gemma4:26b`  
**용도**: HTML 리포트 텍스트에서 관련 기업 최대 3개 추출 (companies.csv 목록 기준)

```
다음 텍스트(제목: {title})에서 가장 관련 있는 기업을 아래 목록에서 골라줘.
목록: {company_list}

텍스트:
{text[:3000]}

규칙:
- 목록에 있는 기업명만 정확히 사용
- 최대 3개까지
- 쉼표로 구분해서 기업명만 나열 (설명 없이)
- 관련 기업이 없으면 '없음' 출력
예: SK하이닉스, NVIDIA, 삼성전자
```

---

## LLM 사용 패턴

**로컬 Ollama** — 비용 없음, 프라이빗, 반복 호출에 적합
- `gemma4:e2b`: 빠른 단문 판단 (관련성 1문장, 스코어링, 매크로 요약)
- `gemma4:26b`: 품질 필요 작업 (PDF 비전, HTML 기업 추출)

**클라우드 Groq** — 빠른 추론, 긴 출력
- `llama-3.3-70b-versatile`: 구조화 출력 (액션 명령, 브리핑, 편입 후보 JSON)
- `llama-4-scout-17b`: 콘텐츠 생성 (블로그, 유튜브)

**Gemini CLI** — 최고 품질, 긴 컨텍스트
- `gemini-2.5-pro`: 심층 분석, 섹터 리포트, TechDoc
