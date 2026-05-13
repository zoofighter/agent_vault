from datetime import date


def company_note(company: dict) -> str:
    name = company["name"]
    ticker = company.get("ticker", "")
    exchange = company.get("exchange", "")
    sector = company.get("sector", "")
    industry = company.get("industry", "")
    keywords = company.get("keywords", [])
    today = date.today().isoformat()

    tags_yaml = "\n".join(f"  - {kw}" for kw in [name, sector] + keywords)

    return f"""---
type: company
company: "{name}"
ticker: {ticker}
exchange: {exchange}
sector: {sector}
industry: {industry}
tags:
{tags_yaml}
updated: {today}
---

# {name}

## 사업 구조

| 부문 | 주요 제품 | 매출 비중 |
|------|---------|---------|
|  |  |  |

## 핵심 관심 사항

<!-- 주요 모니터링 포인트를 작성하세요 -->

## 주요 경쟁사

-

## 투자 포인트

1.

## 리스크

-

## 관련 노트

<!-- 리서치/메모 파일을 링크하세요 -->
"""
