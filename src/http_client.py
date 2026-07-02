import random
import threading
import time
from urllib.parse import urlsplit

import requests

from config import USER_AGENT

try:
    import cloudscraper

    _HAS_CLOUDSCRAPER = True
except ImportError:
    _HAS_CLOUDSCRAPER = False


class RateLimiter:
    def __init__(self, rate: float):
        self.min_interval = 1.0 / rate if rate > 0 else 0.0
        self._lock = threading.Lock()
        self._next = 0.0

    def acquire(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._next - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next = now + self.min_interval


def _build_session():
    if _HAS_CLOUDSCRAPER:
        session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
    else:
        session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "vi,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return session


class Fetcher:
    RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    def __init__(
        self,
        retries: int = 4,
        backoff: float = 2.0,
        max_backoff: float = 60.0,
        network_timeout: float = 300.0,
        probe_interval: float = 10.0,
        rate_limiter: RateLimiter | None = None,
    ):
        self.session = _build_session()
        self.retries = retries
        self.backoff = backoff
        self.max_backoff = max_backoff
        self.network_timeout = network_timeout
        self.probe_interval = probe_interval
        self.rate_limiter = rate_limiter

    def _sleep_backoff(self, attempt: int) -> None:
        delay = min(self.max_backoff, self.backoff * (2 ** (attempt - 1)))
        time.sleep(delay + random.uniform(0, delay * 0.25))

    @staticmethod
    def _retry_after(response) -> float | None:
        value = response.headers.get("Retry-After")
        if value and value.strip().isdigit():
            return float(value.strip())
        return None

    def _online(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        try:
            self.session.get(origin, timeout=10)
            return True
        except requests.RequestException:
            return False

    def _wait_for_network(self, url: str) -> bool:
        waited = 0.0
        while waited < self.network_timeout:
            time.sleep(self.probe_interval)
            waited += self.probe_interval
            if self._online(url):
                return True
        return False

    def get(self, url: str) -> str:
        while True:
            connection_failed = False
            last_error = None
            for attempt in range(1, self.retries + 1):
                if self.rate_limiter:
                    self.rate_limiter.acquire()
                try:
                    response = self.session.get(url, timeout=30)
                    if response.status_code in self.RETRYABLE_STATUS:
                        last_error = f"HTTP {response.status_code}"
                        if attempt < self.retries:
                            wait = self._retry_after(response)
                            if wait is not None:
                                time.sleep(wait)
                            else:
                                self._sleep_backoff(attempt)
                        continue
                    response.raise_for_status()
                    return response.text
                except requests.HTTPError as error:
                    raise RuntimeError(f"Lỗi không thể thử lại {url}: {error}")
                except requests.RequestException as error:
                    last_error = error
                    connection_failed = True
                    if attempt < self.retries:
                        self._sleep_backoff(attempt)
            if connection_failed and not self._online(url) and self._wait_for_network(url):
                continue
            raise RuntimeError(f"Không tải được {url} sau {self.retries} lần: {last_error}")
