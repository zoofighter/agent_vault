"""
블로그 초안 / 유튜브 스크립트 생성 (Claude API)

Daily 노트의 synthesis를 원료로 읽기 쉬운 콘텐츠로 변환한다.
"""

import os

from src.content.curator import ContentCandidate

_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_DISCLAIMER = (
    "\n\n---\n"
    "> **면책 고지**: 이 글은 정보 제공 목적이며 투자 권유가 아닙니다. "
    "AI 보조 작성 콘텐츠로, 최종 투자 결정은 본인 판단에 따릅니다.\n"
)


def _blog_prompt(candidate: ContentCandidate) -> str:
    return f"""You are a professional Korean investment blogger.

Company: {candidate.company}
Date: {candidate.date}
News count: {candidate.news_count}

Daily research synthesis:
{candidate.synthesis}

---
Write a Korean blog post (600-800 characters) with this EXACT structure:

# [캐치-제목: 핵심 키워드 포함, 클릭 유도, ~30자]

> {candidate.date} | {candidate.company}

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

IMPORTANT: Write ONLY in Korean. Do NOT mix in Chinese, Japanese, Russian, or any other language characters.
Write in natural Korean. Be analytical but accessible. No jargon without explanation."""


def _youtube_prompt(candidate: ContentCandidate) -> str:
    return f"""You are writing a YouTube script for a Korean investment channel.

Company: {candidate.company}
Date: {candidate.date}

Daily research synthesis:
{candidate.synthesis}

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
Write in conversational Korean. Include [슬라이드 큐] for visual cues."""


_SYSTEM = (
    "You are a professional Korean investment blogger. "
    "Always write exclusively in Korean (한국어). "
    "Never use Chinese (中文), Japanese (日本語), Russian, or any other language characters. "
    "Every single word must be Korean or standard English proper nouns (company names, technical terms)."
)


def _call_groq(prompt: str, max_tokens: int = 1500) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.environ.get("GROQ_API_KEY", ""),
            base_url=_GROQ_BASE_URL,
        )
        resp = client.chat.completions.create(
            model=_MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"<!-- Groq API 오류: {e} -->"


def generate_blog(candidate: ContentCandidate) -> str:
    """블로그 초안 마크다운 반환."""
    content = _call_groq(_blog_prompt(candidate))
    return content + _DISCLAIMER


def generate_youtube_script(candidate: ContentCandidate) -> str:
    """유튜브 스크립트 마크다운 반환."""
    content = _call_groq(_youtube_prompt(candidate))
    return content + _DISCLAIMER
