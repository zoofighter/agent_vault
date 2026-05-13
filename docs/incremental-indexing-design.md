# 설계 결정: 볼트 규모 확장 대비 증분 인덱싱

## 문제 정의

Obsidian 볼트가 커질수록 매 실행 시 전체 파일을 읽고 임베딩을 재생성하면 처리 시간이 파일 수에 비례해 늘어난다.

| 볼트 파일 수 | 매번 전체 처리 | 증분 처리 (변경 5개) |
|------------|-------------|-------------------|
| 100개 | ~100초 | ~5초 |
| 500개 | ~500초 | ~5초 |
| 2,000개 | ~2,000초 | ~5초 |

> 로컬 임베딩 모델 기준 파일당 약 1초 소요.

---

## 해결책: 두 단계 분리

볼트 인덱스 빌드와 일일 뉴스 검색을 분리한다.

### Phase A — 인덱스 빌드 (변경 파일만)

```
볼트 스캔 → 파일별 (mtime + MD5) 계산
    → index_state.json 과 비교
        신규/변경 파일 → 임베딩 생성 → ChromaDB upsert → state 갱신
        삭제된 파일   → ChromaDB delete → state에서 제거
        미변경 파일   → 스킵 (0ms)
```

### Phase B — 일일 뉴스 검색

```
ChromaDB 로드 (즉시)
    → 뉴스 수집
    → 벡터 유사도 검색 (< 0.5초)
    → 유사도 threshold 미만 사전 필터링
    → 통과 기사만 LLM 근거 생성
    → Obsidian 노트 저장
```

---

## 기능 요건 (F-5x)

| ID | 요건 | 우선순위 |
|----|------|---------|
| F-50 | 파일별 mtime + MD5 해시로 변경 감지 | 필수 |
| F-51 | 변경된 파일만 임베딩 재생성 (전체 재빌드 없음) | 필수 |
| F-52 | ChromaDB `persistent_directory` 설정으로 영구 저장 | 필수 |
| F-53 | `data/index_state.json`에 파일별 `{mtime, hash, embedded_at}` 기록 | 필수 |
| F-54 | 볼트 파일 삭제 시 ChromaDB에서 해당 임베딩도 제거 | 필수 |
| F-55 | 강제 전체 재인덱스 옵션 (`--reindex-all` 플래그) | 선택 |

---

## index_state.json 구조

```json
{
  "Companies/삼성전자.md": {
    "mtime": 1747036800.0,
    "hash": "a3f2c1...",
    "embedded_at": "2026-05-12T08:00:00"
  },
  "Research/반도체업황.md": {
    "mtime": 1747036500.0,
    "hash": "b9e4d2...",
    "embedded_at": "2026-05-12T08:00:01"
  }
}
```

---

## 임베딩 모델 옵션

| 옵션 | 모델 | 비용 | 속도 |
|------|------|------|------|
| 로컬 (기본값) | `nomic-embed-text` via Ollama | 무료 | ~100ms/doc |
| OpenAI API | `text-embedding-3-small` | $0.02/1M tokens | 빠름 |
| Gemini | `embedding-001` | 무료 티어 있음 | - |

`config.yaml` 설정:
```yaml
embedding:
  backend: "ollama"                 # ollama | openai | gemini
  model: "nomic-embed-text"
  # model: "text-embedding-3-small" # OpenAI 사용 시
  batch_size: 20
```

---

## 비기능 요건

| ID | 요건 | 기준 |
|----|------|------|
| NF-10 | 초기 인덱스 빌드 시간 | 100개 파일 기준 3분 이내 |
| NF-11 | 일일 인덱스 업데이트 시간 | 변경 파일 10개 이하 기준 10초 이내 |
| NF-12 | ChromaDB 벡터 유사도 검색 | 10,000 문서 기준 0.5초 이내 |

---

## 파일/폴더 구조

```
project/
├── src/
│   └── obsidian/
│       ├── indexer.py   # 파일 변경 감지 + index_state.json 관리
│       └── embedder.py  # ChromaDB 증분 임베딩 업데이트
└── data/
    ├── chroma/          # ChromaDB 영구 저장소
    └── index_state.json
```

---

## 구현 단계

| Phase | 내용 | 산출물 |
|-------|------|--------|
| Phase 1-A | 볼트 파일 읽기 + 변경 감지 | `obsidian/reader.py`, `obsidian/indexer.py` |
| Phase 1-B | ChromaDB 증분 임베딩 빌드 | `obsidian/embedder.py`, `data/chroma/` |

---

## 검증 방법

1. 100개 더미 `.md` 파일로 초기 인덱스 빌드 시간 측정
2. 파일 1개 수정 후 재실행 → 1개만 재임베딩 확인 (`logs/` 확인)
3. ChromaDB 쿼리로 유사 문서 top-5 반환 확인
4. `index_state.json` 내 hash 값이 변경 파일만 갱신됐는지 확인
