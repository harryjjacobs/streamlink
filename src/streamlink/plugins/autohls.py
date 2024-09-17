"""
$description Automatically detect and play HLS streams from any website.
$url .*
$type live
$region global
"""

import logging
import re
import subprocess
import time

from streamlink.plugin import Plugin, pluginmatcher
from streamlink.plugin.plugin import LOW_PRIORITY, pluginargument
from streamlink.stream.hls import HLSStream


log = logging.getLogger(__name__)


class NetworkRequestsListener:
    def __init__(self, page):
        self.requests = []
        self.page = page

    def __enter__(self):
        self.page.on("requestfinished", self.on_requestfinished)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.page.remove_listener("requestfinished", self.on_requestfinished)

    def on_requestfinished(self, request):
        # print(request.url)
        if self.page.is_closed():
            return
        if self.is_m3u8_request(request):
            self.requests.append(request)

    def is_m3u8_request(self, request):
        if "m3u8" in request.url:
            return True
        try:
            return "#EXT-X-MEDIA-SEQUENCE" in request.response().text()
        except UnicodeDecodeError:
            return False
        except Exception as e:
            log.error(f"Failed to check if request is m3u8: {e}")
            return False

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
            self.logger.warn(
                "Playwright is not installed. Installing it by running 'pip install playwright'."
            )
            return []

        subprocess.run(["playwright", "install"])

        from playwright.sync_api import sync_playwright

        self.logger.info("Loading page in browser")
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=not self.options.get("show-browser"))
            try:
                context = browser.new_context()
                page = context.new_page()
                with NetworkRequestsListener(page) as listener:
                    page.goto(self.url, wait_until="domcontentloaded")
                    page.wait_for_load_state("load")
                    # listen to network requests for m3u8 files
                    # activate video player if present
                    self._activate_video_player(browser, context, page)
                    # wait for a while to capture all requests
                    self.logger.info("Auto-detecting HLS streams...")
                    time.sleep(5)
                    return listener.requests
            except Exception as e:
                log.error(f"Failed to load page: {e}")
            finally:
                browser.close()

    def _activate_video_player(self, browser, context, page):
        # if the page has a video player element, activate it
        # by clicking on it
        video_player = page.query_selector("video")
        if video_player:
            try:
                video_player.click()
            except Exception as e:
                log.error(f"Failed to click on video player: {e}")
            return True
        return False

    # TODO: some of these sites hide the m3u8 URL with a css file extension
    # We could look at the content of the css file to detect if it's a m3u8 file

__plugin__ = AutoHLSPlugin
