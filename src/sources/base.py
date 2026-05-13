from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class NewsItem:
    title: str
    url: str
    snippet: str
    source: str       # 'duckduckgo' | 'naver'
    company: str
    query: str
    published: Optional[str] = None   # 'YYYY-MM-DD' or None


class BaseSource(ABC):
    @abstractmethod
    def search(self, query: str, company: str, days: int = 7) -> list[NewsItem]:
        ...
