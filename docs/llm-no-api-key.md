---
title: API 키 없이 LLM 실행하는 방법
type: system-doc
created: 2026-05-15
related:
  - tech-report-implementation.md
  - rag-architecture.md
---

# API 키 없이 LLM 실행하는 방법

> AgentVault에서 실제로 쓰는 방법과 선택 기준 정리.

---

## 현재 시스템에서 사용 중인 방법

| 용도 | 방법 | 모델 | 비용 |
|------|------|------|------|
| 뉴스 유사도 필터 + 근거 생성 | Ollama | gemma4:e2b | 무료 |
| ChromaDB 임베딩 | Ollama | nomic-embed-text | 무료 |
| 종합 분석 합성 | Ollama | llama3.2 | 무료 |
| TechReport 리포트 생성 | **Gemini CLI** | gemini-2.5-pro/flash | 무료\* |
| Commander 액션 명령 | Groq API | llama-3.3-70b | 무료 (한도) |
| Briefing 브리핑 | Groq API | llama-3.3-70b | 무료 (한도) |

\* Google 계정 인증 기반, 일정 사용량 무료

---

## 방법 1 — Ollama (로컬 실행)

**이미 설치·운영 중**

로컬 머신에서 모델을 직접 실행. 인터넷 연결·API 키 불필요.

```bash
# 설치 (Mac)
brew install ollama

# 모델 다운로드
ollama pull gemma4:e2b          # Commander 스코어링용
ollama pull nomic-embed-text    # 임베딩용
ollama pull llama3.2            # 종합 분석용

# 실행
ollama run gemma4:e2b "반도체 CoWoS 기술을 설명해라"
```

**Python 호출 (AgentVault 패턴):**

```python
import ollama

# 텍스트 생성 (스트리밍)
for chunk in ollama.generate(
    model="gemma4:e2b",
    prompt="프롬프트",
    options={"num_predict": 500},
    think=False,
    stream=True,
):
    print(chunk.response, end="")

# 임베딩
result = ollama.embed(model="nomic-embed-text", input=["텍스트"])
vectors = result.embeddings
```

**장점**: 완전 오프라인, 무제한 실행, 데이터 외부 유출 없음
**단점**: GPU/RAM 필요 (gemma4:e2b ≈ 4GB VRAM), 대형 모델은 품질 한계

---

## 방법 2 — Gemini CLI (TechReport에 적용)

**Google 계정 인증만으로 사용. API 키 불필요.**

```bash
# 설치
npm install -g @google/gemini-cli   # 이미 설치됨 (v0.20.2)

# 초기 인증 (최초 1회)
gemini   # 브라우저에서 Google 로그인

# 비대화형 실행 (파이프라인에서 사용)
gemini --model gemini-2.5-pro "프롬프트 내용"
gemini --model gemini-2.5-flash "빠른 요약 요청"

# stdin 파이프
cat prompt.txt | gemini --model gemini-2.5-pro
```

**Python에서 subprocess 호출 (AgentVault 패턴):**

```python
import subprocess, shutil

def call_gemini(prompt: str, model: str = "gemini-2.5-pro", timeout: int = 120) -> str:
    if not shutil.which("gemini"):
        return ""
    result = subprocess.run(
        ["gemini", "--model", model, prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()

# 사용
report = call_gemini("메르 스타일로 CoWoS 리포트 작성", model="gemini-2.5-pro")
```

**모델 선택:**

| 모델 | 특성 | 적합 용도 |
|------|------|---------|
| `gemini-2.5-pro` | 최고 품질, 느림 | 심층 리포트, 긴 문서 |
| `gemini-2.5-flash` | 빠름, 충분한 품질 | 주간 업데이트, 요약 |

**장점**: API 키 불필요, gemini-2.5-pro 품질 (Groq llama 대비 월등), 무료 한도 넉넉함
**단점**: 인터넷 연결 필요, Google 계정 필요, CLI 콜드 스타트 ~1초

---

## 방법 3 — Groq API (무료 한도)

**API 키 필요하지만 무료 티어가 상당히 넉넉함.**

```bash
# .env에 추가
GROQ_API_KEY=gsk_xxxx
```

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)
resp = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    max_tokens=1000,
    messages=[{"role": "user", "content": "프롬프트"}],
)
```

**무료 한도 (2026-05-15 기준):**
- `llama-3.3-70b-versatile`: 30 req/min, 131,072 tokens/day
- `meta-llama/llama-4-scout-17b-16e-instruct`: 30 req/min

**장점**: 빠름 (추론 속도 업계 최고), JSON 모드 지원, 한국어 충분
**단점**: API 키 필요, 일일 토큰 한도 있음

---

## 방법 4 — LM Studio (로컬 GUI + API)

**Ollama와 비슷하지만 GUI 제공. OpenAI 호환 로컬 서버 실행.**

```bash
# brew로 설치
brew install --cask lm-studio

# 실행 후 모델 다운로드 (GUI), 로컬 서버 시작 → localhost:1234
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
resp = client.chat.completions.create(
    model="...",  # LM Studio에서 로드한 모델명
    messages=[{"role": "user", "content": "프롬프트"}],
)
```

**장점**: GUI로 모델 관리 편함, OpenAI API 완전 호환
**단점**: 별도 앱 실행 필요, Ollama와 역할 중복

---

## 방법 5 — llama.cpp (경량 직접 실행)

**가장 가볍고 빠른 로컬 추론. GGUF 포맷 모델 직접 실행.**

```bash
# 설치
brew install llama.cpp

# 실행
llama-cli -m /path/to/model.gguf -p "프롬프트" -n 500
```

```python
import subprocess

result = subprocess.run(
    ["llama-cli", "-m", "model.gguf", "-p", prompt, "-n", "500", "--no-display-prompt"],
    capture_output=True, text=True
)
output = result.stdout.strip()
```

**장점**: 가장 가벼움, CPU만으로도 동작
**단점**: 모델 직접 관리 필요 (GGUF 다운로드), Ollama가 이미 있으면 중복

---

## AgentVault 선택 기준

```
짧은 텍스트 분류·근거 생성 (뉴스 필터)
    → Ollama gemma4:e2b (로컬, 빠름)

임베딩
    → Ollama nomic-embed-text (로컬, 무료)

긴 리포트 생성 (TechReport)
    → Gemini CLI gemini-2.5-pro (API 키 불필요, 최고 품질)

JSON 구조화 출력 (Commander, Watchlist)
    → Groq llama-3.3-70b (JSON mode 안정적)

대화형·실험적 작업
    → Gemini CLI 대화 모드 or Ollama
```

---

## 실패 시 fallback 체인 (TechReport)

```
Gemini CLI (gemini-2.5-pro)
    │ 실패 (네트워크 없음, 타임아웃)
    ▼
Groq API (llama-3.3-70b)
    │ 실패 (API 키 없음, 한도 초과)
    ▼
빈 문자열 반환 → 오류 출력
```

`src/tech_report/reporter.py`에 이 순서로 구현되어 있음.
