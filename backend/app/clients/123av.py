from __future__ import annotations

import re
from urllib.parse import unquote, urljoin

import httpx
from bs4 import BeautifulSoup

from .base import Actress, BaseProvider, Movie, NotFoundError, ProviderError, attr_str


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    # 日文介面標籤較穩定；繁中／簡中／英文亦一併支援
    "Accept-Language": "ja,zh-TW;q=0.9,zh;q=0.8,en;q=0.7",
}

# <dt> 標籤 → Movie 欄位（含多語系）
_LABEL_MAP = {
    # code
    "コード": "code",
    "代碼": "code",
    "代码": "code",
    "Code": "code",
    # release_date
    "発売日": "release_date",
    "發布日期": "release_date",
    "发布日期": "release_date",
    "Release date": "release_date",
    # runtime
    "再生時間": "runtime",
    "時長": "runtime",
    "时长": "runtime",
    "片長": "runtime",
    "Duration": "runtime",
    "Runtime": "runtime",
    # actresses
    "出演者": "actresses",
    "演員": "actresses",
    "演员": "actresses",
    "Cast": "actresses",
    # studio
    "メーカー": "studio",
    "製作商": "studio",
    "制作商": "studio",
    "Maker": "studio",
    # series
    "シリーズ": "series",
    "系列": "series",
    "Series": "series",
    # genres
    "ジャンル": "genres",
    "類別": "genres",
    "类别": "genres",
    "Genres": "genres",
    # tags → 併入 genres
    "タグ": "tags",
    "標籤": "tags",
    "标签": "tags",
    "Tags": "tags",
}

_COVER_RE = re.compile(
    r"background-image\s*:\s*url\(\s*['\"]?([^'\")\s]+)",
    re.IGNORECASE,
)
_POSTER_RE = re.compile(r"[?&]poster=([^&\"'\s]+)", re.IGNORECASE)


class Av123Provider(BaseProvider):
    """123AV（123av.com）影片頁爬蟲。

    番號 URL：``https://123av.com/ja/v/{slug}``
    （例如 ``FC2-PPV-4977924`` → ``/ja/v/fc2-ppv-4977924``）。
    """

    name = "123av"
    base_url = "https://123av.com"
    locale = "ja"

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 15.0,
        locale: str = "ja",
    ):
        if base_url:
            self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self.locale = (locale or "ja").strip().lower()

    async def search(self, code: str) -> Movie:
        slug = self._to_slug(code)
        if not slug:
            raise NotFoundError(f"123av: invalid code {code!r}")
        url = f"{self.base_url}/{self.locale}/v/{slug}"

        try:
            async with httpx.AsyncClient(
                headers=_HEADERS,
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
        except httpx.HTTPError as e:
            raise ProviderError(f"123av: request failed: {e}") from e

        if resp.status_code == 404:
            raise NotFoundError(f"123av: {code} not found")
        if resp.status_code >= 400:
            raise ProviderError(f"123av: HTTP {resp.status_code}")

        # 404 頁標題為「404 — 123AV」；正常頁有 watch__title
        if "watch__title" not in resp.text or "errpage__code" in resp.text:
            raise NotFoundError(f"123av: {code} not found")

        return self._parse(code, str(resp.url), resp.text)

    # ── parsing ─────────────────────────────────────────────────────────

    def _parse(self, code: str, source_url: str, html: str) -> Movie:
        soup = BeautifulSoup(html, "lxml")
        fields = self._info_fields(soup)

        page_code = (fields.get("code") or code).strip().upper()
        title = self._title(soup, page_code)
        cover = self._cover(soup, html)
        actresses = self._chip_actresses(soup)
        genres: list[str] = []
        seen_genres: set[str] = set()
        for g in self._chip_list(soup, "genres") + self._chip_list(soup, "tags"):
            if g not in seen_genres:
                seen_genres.add(g)
                genres.append(g)

        movie = Movie(
            provider=self.name,
            code=page_code,
            title=title,
            cover_url=cover,
            thumb_url=cover,
            release_date=self._normalize_date(fields.get("release_date")),
            runtime_minutes=self._parse_runtime(fields.get("runtime")),
            studio=fields.get("studio"),
            label=None,
            series=fields.get("series"),
            director=None,
            description=None,  # og:description 為站台通用文案，非劇情
            actresses=actresses,
            genres=genres,
            sample_images=[],  # 無獨立樣本圖區塊
            source_url=source_url,
        )
        if not movie.title:
            raise NotFoundError(f"123av: empty page for {code}")
        return movie

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _to_slug(code: str) -> str:
        """``FC2-PPV-4977924`` / ``SNOS-399`` → URL slug（小寫、連字號）。"""
        raw = (code or "").strip().lower().replace("_", "-").replace(" ", "-")
        raw = re.sub(r"-+", "-", raw).strip("-")
        if not raw:
            return ""
        # FC2PPV123 / fc2-123 → fc2-ppv-123
        m = re.match(r"^fc2-?ppv-?(\d{4,10})$", raw)
        if m:
            return f"fc2-ppv-{m.group(1)}"
        m = re.match(r"^fc2-?(\d{4,10})$", raw)
        if m:
            return f"fc2-ppv-{m.group(1)}"
        return raw

    def _abs_url(self, url: str | None) -> str | None:
        if not url:
            return None
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        return urljoin(self.base_url + "/", url)

    def _title(self, soup: BeautifulSoup, code: str) -> str:
        h1 = soup.select_one("h1.watch__title")
        if not h1:
            return ""
        title = h1.get_text(" ", strip=True)
        # 「CODE — 標題」或「CODE - 標題」
        title = re.sub(
            rf"^{re.escape(code)}\s*[—–-]\s*",
            "",
            title,
            flags=re.IGNORECASE,
        )
        title = re.sub(r"\s*[—–-]\s*123AV\s*$", "", title, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", title).strip()

    def _cover(self, soup: BeautifulSoup, html: str) -> str | None:
        """封面在 ``.player`` 的 ``background-image``，或 iframe poster 參數。"""
        player = soup.select_one("div.player")
        if player:
            style = attr_str(player.get("style")) or ""
            m = _COVER_RE.search(style)
            if m:
                return self._abs_url(m.group(1))

        # 優先 DOM 上帶 background-image 的節點，避免誤抓全域 CSS
        for tag in soup.select("[style*='background-image']"):
            style = attr_str(tag.get("style")) or ""
            m = _COVER_RE.search(style)
            if m and "cover" in m.group(1):
                return self._abs_url(m.group(1))

        m = _POSTER_RE.search(html)
        if m:
            return self._abs_url(unquote(m.group(1)))
        return None

    def _info_fields(self, soup: BeautifulSoup) -> dict[str, str]:
        """解析 ``dl.watch__info`` 的 ``dt/dd`` 純文字欄位。"""
        out: dict[str, str] = {}
        for row in soup.select("dl.watch__info .watch__info-row"):
            dt = row.select_one("dt")
            dd = row.select_one("dd")
            if not dt or not dd:
                continue
            label = dt.get_text(strip=True)
            key = _LABEL_MAP.get(label)
            # chip 列（出演者／メーカー／ジャンル）另處理，此處只取純文字
            if key in ("actresses", "genres", "tags", "studio", "series"):
                # studio / series 可能只有單一 chip
                if key in ("studio", "series"):
                    text = dd.get_text(" ", strip=True)
                    if text:
                        out[key] = text
                continue
            if not key:
                continue
            text = dd.get_text(" ", strip=True)
            if text:
                out[key] = text
        return out

    def _chip_list(self, soup: BeautifulSoup, field: str) -> list[str]:
        """從對應 ``dt`` 列的 ``a.chip`` 取出名稱。"""
        out: list[str] = []
        seen: set[str] = set()
        for row in soup.select("dl.watch__info .watch__info-row"):
            dt = row.select_one("dt")
            if not dt:
                continue
            if _LABEL_MAP.get(dt.get_text(strip=True)) != field:
                continue
            for a in row.select("a.chip, dd.chips a"):
                name = a.get_text(strip=True)
                if name and name not in seen:
                    seen.add(name)
                    out.append(name)
        return out

    def _chip_actresses(self, soup: BeautifulSoup) -> list[Actress]:
        names = self._chip_list(soup, "actresses")
        return [Actress(name=n) for n in names]

    @staticmethod
    def _normalize_date(raw: str | None) -> str | None:
        if not raw:
            return None
        m = re.search(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", raw)
        if not m:
            return None
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    @staticmethod
    def _parse_runtime(raw: str | None) -> int | None:
        """``40:17`` / ``1:09:15`` → 分鐘（秒數 ≥30 進位）。"""
        if not raw:
            return None
        text = raw.strip()
        m = re.match(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$", text)
        if m:
            hours = int(m.group(1) or 0)
            minutes = int(m.group(2))
            seconds = int(m.group(3))
            total = hours * 60 + minutes + (1 if seconds >= 30 else 0)
            return total or None
        m = re.search(r"(\d+)", text)
        return int(m.group(1)) if m else None
