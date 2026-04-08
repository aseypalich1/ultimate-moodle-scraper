"""
Playwright-based async MHTML page capture for Moodle-DL.

Provides authenticated full-page MHTML snapshots of Moodle pages (books,
assignments, forum threads, etc.) that cannot be downloaded as plain files.
Videos embedded via pluginfile.php are downloaded separately and the MHTML
is patched to use local relative paths.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote, urlparse

_VIDEO_EXTENSIONS = frozenset({".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"})

# Matches pluginfile.php / draftfile.php URLs inside MHTML text
_PLUGINFILE_URL_RE = re.compile(
    r'https?://[^\s\'"<>]+?/(?:pluginfile|draftfile)\.php/[^\s\'"<>]+',
    re.IGNORECASE,
)

log = logging.getLogger(__name__)


def load_cookies_from_netscape(cookies_text: str) -> List[Dict[str, Any]]:
    """
    Parse a Netscape cookie jar text into a list of Playwright cookie dicts.

    The Netscape format (used by MoodleDLCookieJar) looks like::

        # Netscape HTTP Cookie File
        .example.com\tTRUE\t/\tFALSE\t0\tname\tvalue

    Returns an empty list if *cookies_text* is None or unparseable.
    """
    result: List[Dict[str, Any]] = []
    if not cookies_text:
        return result

    for line in cookies_text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) < 7:
            continue
        domain, _tail_match, path, secure_str, expires_str, name, value = parts[:7]
        cookie: Dict[str, Any] = {
            'name': name,
            'value': value,
            'domain': domain,
            'path': path or '/',
            'secure': secure_str.upper() == 'TRUE',
        }
        try:
            exp = int(expires_str)
            if exp > 0:
                cookie['expires'] = float(exp)
        except (ValueError, TypeError):
            pass
        result.append(cookie)

    return result


class MhtmlCapture:
    """
    Wraps a headless Chromium browser for authenticated async MHTML capture.

    Lifecycle::

        async with MhtmlCapture(cookies_text, token) as cap:
            mhtml = await cap.save_mhtml(url)
            mhtml = await cap.rewrite_videos(mhtml, output_dir, session)

    Alternatively use :meth:`open` / :meth:`close` for explicit management.
    """

    def __init__(self, cookies_text: str, token: str) -> None:
        self._cookies_text = cookies_text
        self._token = token
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None

    async def open(self) -> None:
        """Launch headless Chromium and inject Moodle session cookies."""
        from playwright.async_api import async_playwright  # type: ignore[import]

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/135.0 Safari/537.36 MoodleDownloader/2.0'
            )
        )
        cookies = load_cookies_from_netscape(self._cookies_text)
        if cookies:
            # Filter out entries with empty domain – Playwright rejects them
            valid = [c for c in cookies if c.get('domain')]
            if valid:
                try:
                    await self._context.add_cookies(valid)
                except Exception as exc:
                    log.warning('Could not inject all cookies: %s', exc)

    async def close(self) -> None:
        """Shut down the browser and stop Playwright."""
        for attr in ('_context', '_browser', '_playwright'):
            obj = getattr(self, attr, None)
            if obj is not None:
                try:
                    await obj.close()
                except Exception:
                    pass
                setattr(self, attr, None)

    async def __aenter__(self) -> 'MhtmlCapture':
        await self.open()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def save_mhtml(self, url: str) -> str:
        """
        Navigate to *url* and return the full-page MHTML snapshot as a string.

        The URL is loaded with Moodle token appended for pluginfile.php URLs.
        Uses Chrome DevTools Protocol ``Page.captureSnapshot``.
        """
        if self._context is None:
            raise RuntimeError('MhtmlCapture.open() must be called before save_mhtml().')

        # Append token so that embedded pluginfile.php resources load properly
        full_url = self._add_token(url)

        page = await self._context.new_page()
        try:
            await page.goto(full_url, wait_until='networkidle', timeout=60_000)
            cdp = await self._context.new_cdp_session(page)
            result = await cdp.send('Page.captureSnapshot', {'format': 'mhtml'})
            return result['data']
        finally:
            await page.close()

    async def rewrite_videos(
        self,
        mhtml_text: str,
        output_dir: Path,
        http_get: Any,
    ) -> str:
        """
        Find video pluginfile.php URLs in *mhtml_text*, download each to
        ``output_dir/page_assets/``, and replace with a relative path.

        Non-video assets (images, CSS, fonts) are already embedded in the
        MHTML by Chromium and are left untouched.

        :param http_get: An async callable ``(url) -> bytes`` for downloading.
                         Typically a wrapper around aiohttp or requests with
                         the Moodle token pre-added.
        """
        assets_dir = output_dir / 'page_assets'
        assets_dir.mkdir(parents=True, exist_ok=True)
        used_names: set[str] = set()

        # Collect all video URLs first (synchronous regex scan)
        video_urls: dict[str, str] = {}  # raw_url -> local_relative_path
        for match in _PLUGINFILE_URL_RE.finditer(mhtml_text):
            raw_url = match.group(0)
            if raw_url in video_urls:
                continue
            ext = Path(urlparse(unquote(raw_url)).path).suffix.lower()
            if ext not in _VIDEO_EXTENSIONS:
                continue

            base_name = Path(urlparse(unquote(raw_url)).path).name or 'video'
            filename = _unique_name(_safe_filename(base_name), used_names)
            used_names.add(filename)
            target = assets_dir / filename
            try:
                data = await http_get(self._add_token(raw_url))
                target.write_bytes(data)
                video_urls[raw_url] = f'page_assets/{filename}'
                log.debug('MHTML video saved: %s → %s', raw_url, filename)
            except Exception as exc:
                log.warning('Could not download MHTML video %s: %s', raw_url, exc)

        if not video_urls:
            return mhtml_text

        def _replace(m: re.Match) -> str:  # type: ignore[type-arg]
            return video_urls.get(m.group(0), m.group(0))

        return _PLUGINFILE_URL_RE.sub(_replace, mhtml_text)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _add_token(self, url: str) -> str:
        """Append ``?token=`` to pluginfile.php / webservice URLs."""
        if self._token and 'pluginfile.php' in url and 'token=' not in url:
            sep = '&' if '?' in url else '?'
            return f'{url}{sep}token={self._token}'
        return url


def _safe_filename(name: str) -> str:
    """Strip characters forbidden in Windows filenames."""
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def _unique_name(name: str, used: set) -> str:
    """Return *name* (or *name_N*) that is not in *used*."""
    candidate = name
    i = 1
    while candidate in used:
        stem = Path(name).stem
        suffix = Path(name).suffix
        candidate = f'{stem}_{i}{suffix}'
        i += 1
    return candidate
