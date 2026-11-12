"""Shared checks for the Django click-through tests (no browser needed).

- every form control has an accessible label
- every button and link has a name
- the page has a viewport meta tag
- internal links on the page resolve (no 404/500)
"""

from html.parser import HTMLParser
from urllib.parse import urlparse


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.controls, self.labels_for, self.buttons, self.links = [], set(), [], []
        self.viewport = False
        self._button = None
        self._link = None
        self._label_depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name") == "viewport":
            self.viewport = True
        if tag == "label":
            self._label_depth += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        if tag in ("input", "select", "textarea") and a.get("type") not in ("hidden", "submit"):
            self.controls.append({**a, "_tag": tag, "_wrapped": self._label_depth > 0})
        if tag == "button":
            self._button = {**a, "_text": ""}
        if tag == "a":
            self._link = {**a, "_text": ""}
        if tag in ("img", "svg") and self._link is not None and (a.get("alt") or a.get("aria-label")):
            self._link["_text"] += a.get("alt") or a.get("aria-label")

    def handle_endtag(self, tag):
        if tag == "label":
            self._label_depth = max(0, self._label_depth - 1)
        if tag == "button" and self._button is not None:
            self.buttons.append(self._button)
            self._button = None
        if tag == "a" and self._link is not None:
            self.links.append(self._link)
            self._link = None

    def handle_data(self, data):
        if self._button is not None:
            self._button["_text"] += data.strip()
        if self._link is not None:
            self._link["_text"] += data.strip()


class ClickThroughMixin:
    def assertAccessiblePage(self, resp):
        p = _Collector()
        p.feed(resp.content.decode())
        if resp.get("Content-Type", "").startswith("text/html") and b"<html" in resp.content:
            self.assertTrue(p.viewport, "page is missing a viewport meta tag")
        for c in p.controls:
            labelled = c.get("aria-label") or c.get("aria-labelledby") or c["_wrapped"] or c.get("id") in p.labels_for
            self.assertTrue(labelled, f"unlabelled {c['_tag']} name={c.get('name')!r}")
        for b in p.buttons:
            self.assertTrue(b["_text"] or b.get("aria-label"), f"button without a name: {b}")
        for link in p.links:
            self.assertTrue(link["_text"] or link.get("aria-label"), f"link without a name: {link.get('href')}")
        return p

    def assertLinksResolve(self, resp, skip=("/accounts/logout/",)):
        p = _Collector()
        p.feed(resp.content.decode())
        seen = set()
        for link in p.links:
            href = link.get("href", "")
            url = urlparse(href)
            if url.scheme or url.netloc or not href.startswith("/") or href in seen or href.startswith(skip):
                continue
            seen.add(href)
            status = self.client.get(href).status_code
            self.assertIn(status, (200, 302), f"{href} returned {status}")
        return seen
