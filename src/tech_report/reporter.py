"""
TechReport Reporter — Groq LLM으로 메르 스타일 리포트 생성·저장·알림
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

_MODEL = "llama-3.3-70b-versatile"
_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_REPORT_TYPE_POINTS = {
    "issue":      12,
    "onboarding": 25,
    "weekly":      6,
}

_SYSTEM_PROMPT = """당신은 "메르(Mer)" 스타일의 한국어 투자 리포트 작성 전문가다.

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
"""


def _build_user_prompt(
    sector: str,
    topic: str,
    articles: list[dict],
    report_type: str,
) -> str:
    target_points = _REPORT_TYPE_POINTS.get(report_type, 12)

    article_lines = []
    for i, a in enumerate(articles[:15], 1):
        pub = f" ({a['published']})" if a.get("published") else ""
        snippet = a.get("snippet", "")[:150]
        article_lines.append(f"{i}. [{a['source']}]{pub} {a['title']}\n   {snippet}")
    articles_str = "\n".join(article_lines) if article_lines else "수집된 기사 없음"

    type_desc = {
        "issue":      f"특정 이슈 심층 분석 리포트 (번호 포인트 {target_points}개 내외)",
        "onboarding": f"섹터 기초 입문 리포트 (번호 포인트 {target_points}개 내외)",
        "weekly":     f"주간 업데이트 리포트 (번호 포인트 {target_points}개 내외)",
    }.get(report_type, f"리포트 (번호 포인트 {target_points}개 내외)")

    return f"""섹터: {sector}
토픽: {topic}
리포트 유형: {type_desc}

수집된 최신 뉴스:
{articles_str}

위 뉴스를 참고해서 [{sector}] {topic} 에 대한 메르 스타일 투자 리포트를 작성해라.
번호 포인트는 "기술 해부" + "변화 포인트" + "투자 시사점" 합산으로 {target_points}개 내외.
출처 URL을 "투자 시사점" 아래에 **참고 기사** 섹션으로 추가한다 (최대 5개).
"""


def _sanitize(text: str) -> str:
    """CJK(중국어·일본어)와 키릴 문자 제거 (한국어·영문·숫자 유지)."""
    # 알려진 중국어→한국어 치환
    _CJK_REPLACE = {
        "増加": "증가", "需要": "수요", "技術": "기술", "市場": "시장",
        "供給": "공급", "生産": "생산", "投資": "투자", "企業": "기업",
    }
    for zh, ko in _CJK_REPLACE.items():
        text = text.replace(zh, ko)
    # 나머지 CJK 제거 (한글 범위 AC00-D7A3, 자모 1100-11FF, 호환자모 3130-318F 유지)
    text = re.sub(r"[一-鿿぀-ヿ　-〿]", "", text)
    # 키릴 문자 제거
    text = re.sub(r"[Ѐ-ӿ]", "", text)
    return text


def generate_report(
    sector: str,
    topic: str,
    articles: list[dict],
    report_type: str = "issue",
) -> str:
    """Groq LLM으로 메르 스타일 리포트 생성. 실패 시 빈 문자열 반환."""
    try:
        from openai import OpenAI
    except ImportError:
        print("  [reporter] openai 패키지 필요: pip install openai")
        return ""

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("  [reporter] GROQ_API_KEY 미설정")
        return ""

    user_prompt = _build_user_prompt(sector, topic, articles, report_type)
    target_tokens = {"issue": 2000, "onboarding": 3500, "weekly": 800}.get(report_type, 2000)

    try:
        client = OpenAI(api_key=api_key, base_url=_GROQ_BASE_URL)
        resp = client.chat.completions.create(
            model=_MODEL,
            max_tokens=target_tokens,
            temperature=0.4,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
        )
        content = (resp.choices[0].message.content or "").strip()
        return _sanitize(content)
    except Exception as e:
        print(f"  [reporter] Groq 호출 실패: {e}")
        return ""


def save_report(
    vault: Path,
    sector: str,
    topic: str,
    content: str,
    date_str: str,
    report_type: str = "issue",
) -> Path:
    """agent_vault/Reports/{섹터}/{date}_{topic}.md 저장. 폴더 자동 생성."""
    reports_dir = vault / "Reports" / sector
    reports_dir.mkdir(parents=True, exist_ok=True)

    safe_topic = re.sub(r"[^\w가-힣\-]", "_", topic)
    filename = f"{date_str}_{safe_topic}.md"
    path = reports_dir / filename

    frontmatter = (
        f"---\n"
        f"type: tech-report\n"
        f"sector: {sector}\n"
        f"topic: {topic}\n"
        f"date: {date_str}\n"
        f"report_type: {report_type}\n"
        f"created: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"tags:\n"
        f"  - tech-report\n"
        f"  - {sector}\n"
        f"---\n\n"
        f"# [{sector}] {topic} 기술 리포트\n\n"
    )

    path.write_text(frontmatter + content + "\n", encoding="utf-8")
    return path


def notify(
    vault: Path,
    sector: str,
    topic: str,
    report_path: Path,
    content: str,
    date_str: str,
) -> None:
    """Telegram 알림 + Digest 기록."""
    _notify_telegram(sector, topic, content, report_path)
    _notify_digest(vault, sector, topic, report_path, date_str)


def _notify_telegram(
    sector: str,
    topic: str,
    content: str,
    report_path: Path,
) -> None:
    try:
        from src.telegram.sender import send
    except ImportError:
        return

    # 트리거 ~ 기술해부 첫 3줄 미리보기
    lines = [ln for ln in content.splitlines() if ln.strip() and not ln.startswith("#")]
    preview = "\n".join(lines[:5])

    rel_path = "/".join(report_path.parts[-3:])  # Reports/반도체/2026-05-14_CoWoS.md
    msg = (
        f"*[{sector}] {topic} 기술 리포트*\n\n"
        f"{preview}\n\n"
        f"...\n\n"
        f"📄 전체 리포트: `{rel_path}`"
    )
    send(msg)


def _notify_digest(
    vault: Path,
    sector: str,
    topic: str,
    report_path: Path,
    date_str: str,
) -> None:
    try:
        from src.obsidian.digest import append_record
    except ImportError:
        return

    rel_path = "/".join(report_path.parts[-3:])
    body = f"섹터: **{sector}** | 토픽: **{topic}**\n파일: `{rel_path}`"
    append_record(vault, f"TechReport — {sector}/{topic}", body, level="info", date=date_str)
