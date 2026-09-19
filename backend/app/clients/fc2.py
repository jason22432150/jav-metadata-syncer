from __future__ import annotations

import json
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .base import BaseProvider, Movie, NotFoundError, ProviderError, attr_str


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    # 日文介面標籤較穩定（販売日 / 商品タグ）；繁中亦可解析
    "Accept-Language": "ja,zh-TW;q=0.9,en;q=0.8",
}

# 接受 FC2-PPV-123 / FC2PPV123 / FC2-123 / 純數字（比對前已 upper）
_CODE_RE = re.compile(r"^(?:FC2[-_]?(?:PPV[-_]?)?)?(\d{4,10})$")


class FC2Provider(BaseProvider):
    """FC2 電子市場（adult.contents.fc2.com）商品頁爬蟲。

    番號格式：``FC2-PPV-{id}``（亦接受純數字 id）。
    頁面 URL：``https://adult.contents.fc2.com/article/{id}/``
    """

    name = "fc2"
    base_url = "https://adult.contents.fc2.com"

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        if base_url:
            self.base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def search(self, code: str) -> Movie:
        article_id = self._normalize_id(code)
        if not article_id:
            raise NotFoundError(f"fc2: invalid code {code!r}")
        canonical = f"FC2-PPV-{article_id}"
        url = f"{self.base_url}/article/{article_id}/"

        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=self._timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                raise NotFoundError(f"fc2: {canonical} not found")
            if resp.status_code >= 400:
                raise ProviderError(f"fc2: HTTP {resp.status_code}")
            # 下架 / 不存在時常仍回 200，但沒有商品 header
            if "items_article_headerInfo" not in resp.text:
                raise NotFoundError(f"fc2: {canonical} not found")
            return self._parse(canonical, url, resp.text)

    # ── parsing ─────────────────────────────────────────────────────────

    def _parse(self, code: str, source_url: str, html: str) -> Movie:
        soup = BeautifulSoup(html, "lxml")
        ld = self._ld_json(soup)
        og = self._og(soup)

        title = self._title(soup, code, ld, og)
        cover = og.get("og:image") or self._ld_image(ld)
        cover = self._abs_url(cover) if cover else None

        release_date = self._release_date(soup)
        runtime = self._runtime(soup)
        studio = self._seller(soup, ld)
        genres = self._genres(soup)
        samples = self._samples(soup)
        description = og.get("og:description") or ld.get("description")

        movie = Movie(
            provider=self.name,
            code=code,
            title=title,
            cover_url=cover,
            thumb_url=cover,
            release_date=release_date,
            runtime_minutes=runtime,
            studio=studio,
            label=None,
            series=None,
            director=None,
            description=self._clean_text(description) if description else None,
            actresses=[],  # FC2 素人商品通常不標出演者
            genres=genres,
            sample_images=samples,
            source_url=source_url,
        )
        if not movie.title:
            raise NotFoundError(f"fc2: empty page for {code}")
        return movie

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_id(code: str) -> str | None:
        """``FC2-PPV-4863907`` / ``4863907`` → ``4863907``。"""
        raw = (code or "").strip().upper().replace(" ", "")
        m = _CODE_RE.match(raw)
        return m.group(1) if m else None

    def _abs_url(self, url: str | None) -> str | None:
        if not url:
            return None
        if url.startswith("//"):
            return "https:" + url
        return urljoin(self.base_url + "/", url)

    @staticmethod
    def _clean_text(text: str | None) -> str:
        if not text:
            return ""
        # 去掉防爬隱藏字元與多餘空白
        text = re.sub(r"\*{3}\w+", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def _title(
        self,
        soup: BeautifulSoup,
        code: str,
        ld: dict,
        og: dict[str, str],
    ) -> str:
        # h3 內有防爬 span，先移除再取文字
        h3 = soup.select_one(".items_article_headerInfo > h3")
        if h3:
            for span in h3.select(
                'span[style*="zoom:0.01"], '
                'span[style*="overflow:hidden"], '
                'span[style*="display:none"], '
                'span[style*="font-size:0"], '
                'span[style*="visibility:hidden"]'
            ):
                span.decompose()
            title = h3.get_text(" ", strip=True)
            if title:
                return self._clean_text(title)

        for candidate in (ld.get("name"), og.get("og:title")):
            if not candidate:
                continue
            title = re.sub(
                rf"^{re.escape(code)}\s*",
                "",
                candidate,
                flags=re.IGNORECASE,
            )
            title = re.sub(r"\s*\|\s*FC2.*$", "", title).strip()
            if title:
                return self._clean_text(title)
        return ""

    @staticmethod
    def _og(soup: BeautifulSoup) -> dict[str, str]:
        out: dict[str, str] = {}
        for m in soup.find_all("meta", property=True):
            prop = attr_str(m.get("property")) or ""
            content = attr_str(m.get("content")) or ""
            if prop.startswith("og:") and content:
                out[prop] = content
        return out

    @staticmethod
    def _ld_json(soup: BeautifulSoup) -> dict:
        for script in soup.select('script[type="application/ld+json"]'):
            raw = script.string or script.get_text() or ""
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                return data
        return {}

    @staticmethod
    def _ld_image(ld: dict) -> str | None:
        image = ld.get("image")
        if isinstance(image, str):
            return image
        if isinstance(image, dict):
            return image.get("url")
        return None

    def _release_date(self, soup: BeautifulSoup) -> str | None:
        # <p>販売日 : 2026/03/14</p> 或 銷售日期
        for p in soup.select(".items_article_softDevice p, .items_article_headerInfo p"):
            text = p.get_text(" ", strip=True)
            if re.search(r"販売日|銷售日期|销售日期", text):
                m = re.search(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", text)
                if m:
                    y, mo, d = m.groups()
                    return f"{y}-{int(mo):02d}-{int(d):02d}"
        return None

    @staticmethod
    def _runtime(soup: BeautifulSoup) -> int | None:
        # <p class="items_article_info">01:16:19</p>
        node = soup.select_one("p.items_article_info")
        if not node:
            return None
        text = node.get_text(strip=True)
        m = re.match(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$", text)
        if not m:
            return None
        hours = int(m.group(1) or 0)
        minutes = int(m.group(2))
        seconds = int(m.group(3))
        total = hours * 60 + minutes + (1 if seconds >= 30 else 0)
        return total or None

    def _seller(self, soup: BeautifulSoup, ld: dict) -> str | None:
        a = soup.select_one(
            ".items_article_writer a[data-article-seller-name], "
            ".items_article_writer a"
        )
        if a:
            name = a.get_text(strip=True)
            if name:
                return name
        brand = ld.get("brand") or {}
        if isinstance(brand, dict):
            return brand.get("name") or None
        return None

    @staticmethod
    def _genres(soup: BeautifulSoup) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for a in soup.select(
            ".items_article_TagArea a.tagTag, "
            ".items_article_TagArea a.tag.tagTag[data-tag]"
        ):
            name = (attr_str(a.get("data-tag")) or a.get_text() or "").strip()
            if name and name not in seen:
                seen.add(name)
                out.append(name)
        return out

    def _samples(self, soup: BeautifulSoup) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for a in soup.select(".items_article_SampleImagesArea a[href]"):
            href = self._abs_url(attr_str(a.get("href")))
            if href and href not in seen:
                seen.add(href)
                urls.append(href)
        return urls
