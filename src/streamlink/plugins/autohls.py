"""
$description Automatically detect and play HLS streams from any website.
$url .*
$type live
$region global
"""

import logging
import re
import time

from streamlink.plugin import Plugin, pluginmatcher
from streamlink.plugin.plugin import LOW_PRIORITY, pluginargument
from streamlink.stream.hls import HLSStream


log = logging.getLogger(__name__)


class NetworkRequestsListener:
    def __init__(self, page):
        self.requests = []
        page.on("request", self.on_request)

    def on_request(self, request):
        if "m3u8" in request.url:
            self.requests.append(request)


@pluginargument(
    "show-browser",
    action="store_true",
    default=False,
    help="Show the browser window for the site",
)
@pluginmatcher(
    priority=LOW_PRIORITY,
    pattern=re.compile(
        r".*",
    ),
)
class AutoHLSPlugin(Plugin):
    def _get_streams(self):
        requests = self._load_page_and_listen_for_requests()

        if not requests:
            return {}

        request = requests[-1]

        self.session.http.headers.clear()
        self.session.http.headers.update(request.headers)

        return {"live": HLSStream(self.session, request.url)}

    def _load_page_and_listen_for_requests(self):
        try:
            import playwright
        except ImportError:
            self.logger.error(
                "Playwright is not installed. Please install it by running 'pip install playwright'."
            )
            return []

        from playwright.sync_api import sync_playwright

        self.logger.info("Loading page in browser")
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=not self.options.get("show-browser"))
            try:
                context = browser.new_context()
                page = context.new_page()
                page.goto(self.url, wait_until="domcontentloaded")
                page.wait_for_load_state("load")
                # listen to network requests for m3u8 files
                listener = NetworkRequestsListener(page)
                # wait for a while to capture all requests
                self.logger.info("Auto-detecting HLS streams...")
                time.sleep(5)
                return listener.requests
            except Exception as e:
                log.error(f"Failed to load page: {e}")
            finally:
                browser.close()


__plugin__ = AutoHLSPlugin
