"""
ChromaDB 증분 임베딩

볼트 마크다운 파일을 nomic-embed-text(Ollama)로 임베딩하여 ChromaDB에 저장한다.
변경된 파일만 재임베딩한다.
"""

from pathlib import Path

import chromadb
import ollama

_CHROMA_PATH = "data/chroma"
_COLLECTION = "vault_docs"
_EMBED_MODEL = "nomic-embed-text"
_CHUNK_CHARS = 1200   # 한 청크 최대 문자 수
_CHUNK_OVERLAP = 200


def _chunk(text: str) -> list[str]:
    """긴 문서를 겹침 있는 청크로 분할"""
    if len(text) <= _CHUNK_CHARS:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + _CHUNK_CHARS
        chunks.append(text[start:end])
        start += _CHUNK_CHARS - _CHUNK_OVERLAP
    return chunks


def _embed(texts: list[str]) -> list[list[float]]:
    result = ollama.embed(model=_EMBED_MODEL, input=texts)
    return result.embeddings


def _get_collection(chroma_path: str = _CHROMA_PATH):
    client = chromadb.PersistentClient(path=chroma_path)
    return client.get_or_create_collection(_COLLECTION)


def index_files(
    changed_files: list[Path],
    chroma_path: str = _CHROMA_PATH,
) -> int:
    """
    변경된 파일을 청크 단위로 임베딩하여 ChromaDB에 upsert한다.

    Returns:
        임베딩된 청크 수
    """
    if not changed_files:
        return 0

    col = _get_collection(chroma_path)
    total = 0

    for md_file in changed_files:
        text = md_file.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue

        chunks = _chunk(text)
        embeddings = _embed(chunks)

        ids = [f"{md_file}::{i}" for i in range(len(chunks))]
        metas = [{"source": str(md_file), "chunk": i} for i in range(len(chunks))]

        # 기존 청크 삭제 후 재삽입 (파일 수정 시 청크 수가 달라질 수 있음)
        existing = col.get(where={"source": str(md_file)}, include=[])
        if existing["ids"]:
            col.delete(ids=existing["ids"])

        col.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metas)
        total += len(chunks)
        print(f"  [embed] {md_file.name} → {len(chunks)}청크")

    return total


def query_similar(
    text: str,
    n_results: int = 5,
    chroma_path: str = _CHROMA_PATH,
) -> list[dict]:
    """
    쿼리 텍스트와 가장 유사한 볼트 문서 청크를 반환한다.

    Returns:
        [{"document": str, "source": str, "distance": float}, ...]
    """
    col = _get_collection(chroma_path)
    if col.count() == 0:
        return []

    embedding = _embed([text])[0]
    results = col.query(query_embeddings=[embedding], n_results=min(n_results, col.count()))

    out = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        out.append({"document": doc, "source": meta["source"], "distance": dist})
    return out
