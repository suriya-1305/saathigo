"""Fetch product metadata (title, image, price) from a store URL to pre-fill a request."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Domain suffix -> (ISO country, currency). Order matters: most specific first.
TLD_COUNTRY = [
    (".co.uk", "GB", "GBP"), (".com.au", "AU", "AUD"), (".co.jp", "JP", "JPY"), (".com.sg", "SG", "SGD"),
    (".ae", "AE", "AED"), (".sa", "SA", "SAR"), (".qa", "QA", "QAR"), (".sg", "SG", "SGD"),
    (".de", "DE", "EUR"), (".fr", "FR", "EUR"), (".it", "IT", "EUR"), (".es", "ES", "EUR"), (".nl", "NL", "EUR"),
    (".ca", "CA", "CAD"), (".au", "AU", "AUD"), (".jp", "JP", "JPY"), (".uk", "GB", "GBP"),
    (".com", "US", "USD"),
]


class LinkPreviewError(ValueError):
    pass


def guess_country(url: str) -> tuple[str | None, str | None]:
    host = (urlparse(url).hostname or "").lower()
    for suffix, country, currency in TLD_COUNTRY:
        if host.endswith(suffix):
            return country, currency
    return None, None


def _assert_public_host(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise LinkPreviewError("Only http(s) URLs are allowed")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise LinkPreviewError("Could not resolve host") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise LinkPreviewError("URL resolves to a non-public address")


def fetch_preview(url: str) -> dict:
    country, currency = guess_country(url)
    result: dict = {
        "url": url, "title": None, "description": None, "image_url": None, "price": None,
        "currency": currency, "store_name": urlparse(url).hostname, "source_country": country,
    }
    html = _fetch_html(url)
    if html:
        result.update({k: v for k, v in _parse_html(html, url).items() if v})
    return result


def _fetch_html(url: str) -> str | None:
    current = url
    with httpx.Client(timeout=8.0, follow_redirects=False, headers={"User-Agent": USER_AGENT,
                                                                       "Accept-Language": "en"}) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _assert_public_host(current)
            try:
                with client.stream("GET", current) as resp:
                    if resp.is_redirect:
                        current = urljoin(current, resp.headers.get("location", ""))
                        continue
                    if resp.status_code >= 400 or "html" not in resp.headers.get("content-type", ""):
                        return None
                    body = b""
                    for chunk in resp.iter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            break
                    return body.decode(resp.encoding or "utf-8", errors="replace")
            except httpx.HTTPError:
                return None
    return None


def _parse_html(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    def meta(*names: str) -> str | None:
        for n in names:
            tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None

    out: dict = {
        "title": meta("og:title", "twitter:title") or (soup.title.string.strip() if soup.title and soup.title.string else None),
        "description": meta("og:description", "description"),
        "image_url": meta("og:image", "twitter:image"),
        "price": _to_float(meta("product:price:amount", "og:price:amount")),
        "currency": meta("product:price:currency", "og:price:currency"),
        "store_name": meta("og:site_name"),
    }

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        product = _find_product(data)
        if product:
            out["title"] = out["title"] or product.get("name")
            img = product.get("image")
            out["image_url"] = out["image_url"] or (img[0] if isinstance(img, list) and img else img if isinstance(img, str) else None)
            offers = product.get("offers")
            offer = offers[0] if isinstance(offers, list) and offers else offers
            if isinstance(offer, dict):
                out["price"] = out["price"] or _to_float(offer.get("price") or offer.get("lowPrice"))
                out["currency"] = out["currency"] or offer.get("priceCurrency")
            break

    if out["image_url"]:
        out["image_url"] = urljoin(base_url, out["image_url"])
    if out["description"]:
        out["description"] = out["description"][:1000]
    return out


def _find_product(data) -> dict | None:
    if isinstance(data, list):
        for item in data:
            found = _find_product(item)
            if found:
                return found
    elif isinstance(data, dict):
        t = data.get("@type")
        if t == "Product" or (isinstance(t, list) and "Product" in t):
            return data
        if "@graph" in data:
            return _find_product(data["@graph"])
    return None


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(re.sub(r"[^\d.]", "", str(value).replace(",", "")) or "x")
    except ValueError:
        return None
