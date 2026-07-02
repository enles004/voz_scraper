import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urljoin

from . import parsers
from config import ScrapeSettings
from .http_client import Fetcher, RateLimiter
from .models import ThreadMeta, ThreadRecord
from .store import CheckpointStore

_MAX_SWEEPS = 2


class VozCrawler:
    def __init__(self, settings: ScrapeSettings):
        self.settings = settings
        self.rate_limiter = RateLimiter(settings.rate)
        self.store = CheckpointStore(settings.work_dir)
        self._local = threading.local()

    def _fetcher(self) -> Fetcher:
        fetcher = getattr(self._local, "fetcher", None)
        if fetcher is None:
            fetcher = Fetcher(retries=self.settings.retries, rate_limiter=self.rate_limiter)
            self._local.fetcher = fetcher
        return fetcher

    def _get(self, url: str) -> str:
        return self._fetcher().get(url)

    def collect(self, cutoff: datetime) -> list[ThreadMeta]:
        collected: list[ThreadMeta] = []
        current_url = self.settings.forum_url
        for _ in range(self.settings.max_pages):
            soup = parsers.make_soup(self._get(current_url))
            items = parsers.parse_thread_items(soup, self.settings.forum_url)
            for item in items:
                marker = item.marker(self.settings.by)
                if marker is not None and marker >= cutoff:
                    collected.append(item)
            latest_times = [it.latest_at for it in items if it.latest_at is not None]
            if latest_times and all(t < cutoff for t in latest_times):
                break
            current_url = parsers.next_page_url(soup, self.settings.forum_url)
            if not current_url:
                break
        return collected

    def _fetch_thread(self, thread: ThreadMeta):
        try:
            soup = parsers.make_soup(self._get(thread.url))
        except RuntimeError as error:
            print(f"Lỗi trang đầu {thread.url}: {error}", file=sys.stderr)
            return None, [{"thread": thread.url, "url": thread.url, "reason": str(error)}]

        tags = parsers.parse_tags(soup)
        messages = parsers.parse_messages(soup)
        last_page = parsers.last_page_number(soup)
        failed: list[dict] = []
        for page in range(2, last_page + 1):
            url = urljoin(thread.url, f"page-{page}")
            try:
                messages.extend(parsers.parse_messages(parsers.make_soup(self._get(url))))
            except RuntimeError as error:
                print(f"Bỏ qua {url}: {error}", file=sys.stderr)
                failed.append({"thread": thread.url, "url": url, "reason": str(error)})

        record = ThreadRecord(
            id=0,
            title=thread.title,
            url=thread.url,
            content=messages[0].content if messages else "",
            author=thread.author,
            published_at=thread.published_at,
            tags=tags,
            comments=messages[1:],
        )
        return record, failed

    def _run_passes(self, threads: list[ThreadMeta]) -> None:
        for attempt in range(_MAX_SWEEPS + 1):
            pending = [t for t in threads if not self.store.is_complete(t.url)]
            if not pending:
                break
            if attempt > 0:
                print(f"Quét lại {len(pending)} thread còn thiếu (lượt {attempt}) ...", file=sys.stderr)
            with ThreadPoolExecutor(max_workers=self.settings.workers) as executor:
                for thread, result in zip(pending, executor.map(self._fetch_thread, pending)):
                    record, failed = result
                    if record is None:
                        continue
                    self.store.save(thread.url, record.to_dict(), failed)

    def enrich(self, threads: list[ThreadMeta]):
        if self.settings.fresh:
            self.store.clear()
        self._run_passes(threads)

        records: list[dict] = []
        failures: list[dict] = []
        for index, thread in enumerate(threads, start=1):
            data = self.store.load(thread.url)
            if data is None:
                failures.append({"thread": thread.url, "url": thread.url, "reason": "không lấy được"})
                continue
            record = data["record"]
            record["id"] = index
            records.append(record)
            failures.extend(data.get("failed", []))
        return records, failures

    def run(self):
        cutoff = self.settings.cutoff()
        print(
            f"Đang thu thập thread ({self.settings.by}) sau {cutoff.isoformat()} ...",
            file=sys.stderr,
        )
        threads = self.collect(cutoff)
        print(
            f"Tìm thấy {len(threads)} thread phù hợp, đang lấy nội dung ...",
            file=sys.stderr,
        )
        records, failures = self.enrich(threads)
        if failures:
            print(
                f"⚠ Còn {len(failures)} mục lỗi — giữ checkpoint tại {self.store.work_dir}, "
                f"chạy lại cùng lệnh để lấy tiếp phần còn thiếu.",
                file=sys.stderr,
            )
        else:
            self.store.clear()
        return records, failures
