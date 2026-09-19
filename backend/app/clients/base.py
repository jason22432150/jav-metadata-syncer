from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any


def attr_str(value: str | list[str] | None) -> str | None:
    """將 BeautifulSoup ``Tag.get()`` 的 AttributeValue 正規化為單一字串。

    bs4 型別定義回傳 ``str | list[str] | None``；多值屬性（如 class）為 list。
    """
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


@dataclass
class Actress:
    name: str
    image_url: str | None = None


@dataclass
class Movie:
    provider: str
    code: str
    title: str
    cover_url: str | None = None
    thumb_url: str | None = None
    release_date: str | None = None
    runtime_minutes: int | None = None
    studio: str | None = None
    label: str | None = None
    series: str | None = None
    director: str | None = None
    description: str | None = None
    actresses: list[Actress] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    sample_images: list[str] = field(default_factory=list)
    source_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProviderError(Exception):
    pass


class NotFoundError(ProviderError):
    pass


class BaseProvider(ABC):
    name: str = ""
    base_url: str = ""

    @abstractmethod
    async def search(self, code: str) -> Movie:
        """Fetch metadata for the given code. Raise NotFoundError if missing."""
        raise NotImplementedError
