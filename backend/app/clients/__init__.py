from __future__ import annotations

from importlib import import_module

from .base import BaseProvider, Movie, Actress, ProviderError, NotFoundError
from .fc2 import FC2Provider
from .jav321 import Jav321Provider
from .javbus import JavBusProvider
from .javtrailers import JavTrailersProvider
from .missav import MissAVProvider

# 模組檔名以數字開頭，無法用一般 from .123av import
try:
    Av123Provider = import_module(".123av", __name__).Av123Provider
except AttributeError as e:
    raise ImportError("123av 模組必須匯出 Av123Provider") from e

PROVIDERS: dict[str, type[BaseProvider]] = {
    JavBusProvider.name: JavBusProvider,
    JavTrailersProvider.name: JavTrailersProvider,
    MissAVProvider.name: MissAVProvider,
    FC2Provider.name: FC2Provider,
    Jav321Provider.name: Jav321Provider,
    Av123Provider.name: Av123Provider,
}


def get_provider(name: str) -> BaseProvider:
    cls = PROVIDERS.get(name.lower())
    if cls is None:
        raise KeyError(f"unknown provider: {name}")
    return cls()


def list_providers() -> list[str]:
    return sorted(PROVIDERS.keys())


__all__ = [
    "BaseProvider",
    "Movie",
    "Actress",
    "ProviderError",
    "NotFoundError",
    "PROVIDERS",
    "get_provider",
    "list_providers",
    "Av123Provider",
]
