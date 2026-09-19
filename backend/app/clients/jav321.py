from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from .base import Actress, BaseProvider, Movie, NotFoundError, ProviderError, attr_str


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    # 日文標籤較完整（出演者 / メーカー / ジャンル）
    "Accept-Language": "ja,zh-TW;q=0.9,en;q=0.8",
}

# <b>標籤</b> → Movie 欄位（含中文語系別名）
_LABEL_MAP = {
    "品番": "code",
    "番號": "code",
    "番号": "code",
    "配信開始日": "release_date",
    "発売日": "release_date",
    "發行日期": "release_date",
    "发行日期": "release_date",
    "収録時間": "runtime",
    "片長": "runtime",
    "时长": "runtime",
    "メーカー": "studio",
    "製作商": "studio",
    "制作商": "studio",
    "レーベル": "label",
    "發行商": "label",
    "系列": "series",
    "シリーズ": "series",
    "監督": "director",
    "導演": "director",
    "导演": "director",
}


class Jav321Provider(BaseProvider):
    """JAV321（www.jav321.com）商品頁爬蟲。

    以 ``POST /search``（欄位 ``sn``）查番號；成功會導向
    ``/video/{dmm_id}``（例如 ``SNOS-367`` → ``/video/snos00367``）。
    """

    name = "jav321"
    base_url = "https://www.jav321.com"

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        if base_url:
            self.base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def search(self, code: str) -> Movie:
        code = (code or "").strip()
        if not code:
            raise NotFoundError("jav321: empty code")

        search_url = f"{self.base_url}/search"
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS,
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                resp = await client.post(search_url, data={"sn": code})
        except httpx.HTTPError as e:
            raise ProviderError(f"jav321: request failed: {e}") from e

        if resp.status_code >= 400:
            raise ProviderError(f"jav321: HTTP {resp.status_code}")

        # 找不到時停留在 /search，並顯示「AVが見つかりませんでした。」
        final = str(resp.url)
        if "/video/" not in final or "AVが見つかりませんでした" in resp.text:
            raise NotFoundError(f"jav321: {code} not found")

        return self._parse(code, final, resp.text)

    # ── parsing ─────────────────────────────────────────────────────────

    def _parse(self, code: str, source_url: str, html: str) -> Movie:
        soup = BeautifulSoup(html, "lxml")
        panel = soup.select_one("div.panel.panel-info")
        if not panel:
            raise NotFoundError(f"jav321: {code} not found")

        info = panel.select_one("div.col-md-9")
        fields = self._info_fields(info) if info else {}
        page_code = (fields.get("code") or code).strip().upper()

        title = self._title(panel, page_code)
        cover, thumb = self._covers(panel)
        actresses = self._actresses(info, soup) if info else []
        genres = self._genres(info) if info else []
        # 樣本圖在 panel 外的獨立 row，需用整頁 soup
        samples = self._samples(soup)
        description = self._description(panel)

        movie = Movie(
            provider=self.name,
            code=page_code,
            title=title,
            cover_url=cover,
            thumb_url=thumb or cover,
            release_date=self._normalize_date(fields.get("release_date")),
            runtime_minutes=self._parse_runtime(fields.get("runtime")),
            studio=fields.get("studio"),
            label=fields.get("label"),
            series=fields.get("series"),
            director=fields.get("director"),
            description=description,
            actresses=actresses,
            genres=genres,
            sample_images=samples,
            source_url=source_url,
        )
        if not movie.title:
            raise NotFoundError(f"jav321: empty page for {code}")
        return movie

    # ── helpers ─────────────────────────────────────────────────────────

    def _abs_url(self, url: str | None) -> str | None:
        if not url:
            return None
        url = url.strip()
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("http://"):
            # DMM / JAV321 圖常回 http；統一成 https
            url = "https://" + url[len("http://") :]
        else:
            url = urljoin(self.base_url + "/", url)
        # poster 有時寫成 pics.dmm.co.jp//digital/...
        return re.sub(r"(https?://[^/]+)//+", r"\1/", url)

    def _title(self, panel: Tag, code: str) -> str:
        h3 = panel.select_one(".panel-heading h3")
        if not h3:
            return ""
        # <small> 內通常是「品番 女優」；先移除避免重複
        for small in h3.select("small"):
            small.decompose()
        title = h3.get_text(" ", strip=True)
        title = re.sub(rf"\b{re.escape(code)}\b", "", title, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", title).strip(" -–—")

    def _covers(self, panel: Tag) -> tuple[str | None, str | None]:
        """回傳 (cover_pl, thumb_ps)。"""
        thumb = None
        img = panel.select_one("div.col-md-3 img")
        if img:
            thumb = self._abs_url(
                attr_str(img.get("src")) or attr_str(img.get("data-src"))
            )

        cover = None
        poster = panel.select_one("video[poster]")
        if poster:
            cover = self._abs_url(attr_str(poster.get("poster")))

        # 沒有 trailer poster 時，把 ps.jpg 換成 pl.jpg
        if not cover and thumb and thumb.endswith("ps.jpg"):
            cover = thumb[:-6] + "pl.jpg"
        if not cover:
            cover = thumb
        return cover, thumb

    def _info_fields(self, info: Tag) -> dict[str, str]:
        """解析 ``<b>標籤</b>: 值<br>`` 結構。"""
        out: dict[str, str] = {}
        current_key: str | None = None
        buf: list[str] = []

        def flush() -> None:
            nonlocal current_key, buf
            if current_key and current_key not in out:
                value = " ".join(buf).strip()
                if value:
                    out[current_key] = value
            current_key = None
            buf = []

        for child in info.children:
            if isinstance(child, Tag) and child.name == "b":
                flush()
                label = child.get_text(strip=True).rstrip(":：")
                current_key = _LABEL_MAP.get(label)
            elif isinstance(child, Tag) and child.name == "br":
                flush()
            elif current_key is None:
                continue
            elif isinstance(child, Tag) and child.name == "a":
                text = child.get_text(strip=True)
                if text:
                    buf.append(text)
            elif isinstance(child, NavigableString):
                text = str(child).strip().lstrip(":：").strip()
                if text:
                    buf.append(text)
        flush()
        return out

    def _actresses(self, info: Tag, soup: BeautifulSoup) -> list[Actress]:
        # 相關區塊可能有女優大頭照，先建 href → image map
        avatars: dict[str, str] = {}
        for a in soup.select('a[href*="/star/"]'):
            href = attr_str(a.get("href"))
            img = a.select_one("img")
            if not href or not img:
                continue
            src = self._abs_url(attr_str(img.get("src")) or attr_str(img.get("data-src")))
            if src:
                avatars.setdefault(href, src)

        out: list[Actress] = []
        seen: set[str] = set()
        for a in info.select('a[href*="/star/"]'):
            name = a.get_text(strip=True)
            if not name or name in seen:
                continue
            seen.add(name)
            href = attr_str(a.get("href")) or ""
            out.append(Actress(name=name, image_url=avatars.get(href)))
        return out

    @staticmethod
    def _genres(info: Tag) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for a in info.select('a[href*="/genre/"]'):
            name = a.get_text(strip=True)
            if name and name not in seen:
                seen.add(name)
                out.append(name)
        return out

    def _samples(self, soup: BeautifulSoup) -> list[str]:
        """樣本圖為 ``...jp-N.jpg``；略過封面 ``pl.jpg``（snapshot index 0）。

        連結形如 ``/snapshot/{id}/1/N``，實際圖在子 ``<img src>``；
        區塊位於主 panel 外，故必須對整頁搜尋。
        """
        urls: list[str] = []
        seen: set[str] = set()
        for img in soup.select('a[href*="/snapshot/"] img'):
            src = self._abs_url(attr_str(img.get("src")) or attr_str(img.get("data-src")))
            if not src or src in seen:
                continue
            if "jp-" not in src:
                continue
            seen.add(src)
            urls.append(src)
        return urls

    @staticmethod
    def _description(panel: Tag) -> str | None:
        body = panel.select_one("div.panel-body")
        if not body:
            return None
        # 最後一個純文字 row（無 video / 無欄位標籤）即劇情簡介
        for row in reversed(body.select(":scope > div.row")):
            if row.select_one("video, b, img"):
                continue
            text = row.get_text(" ", strip=True)
            if text and len(text) > 20:
                return text
        return None

    @staticmethod
    def _normalize_date(raw: str | None) -> str | None:
        if not raw:
            return None
        m = re.search(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", raw)
        if not m:
            return raw.strip() or None
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    @staticmethod
    def _parse_runtime(raw: str | None) -> int | None:
        if not raw:
            return None
        m = re.search(r"(\d+)", raw)
        return int(m.group(1)) if m else None
