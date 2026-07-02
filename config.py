from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

DEFAULT_FORUM_URL = "https://voz.vn/f/chuyen-tro-linh-tinh%E2%84%A2.17/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass
class ScrapeSettings:
    forum_url: str = DEFAULT_FORUM_URL
    hours: float = 6.0
    output: str = "voz_posts.zip"
    max_pages: int = 50
    workers: int = 6
    rate: float = 5.0
    retries: int = 4
    fresh: bool = False
    by: str = "active"

    @property
    def work_dir(self) -> str:
        return self.output + ".work"

    def cutoff(self, now: datetime | None = None) -> datetime:
        now = now or datetime.now(timezone.utc)
        return now - timedelta(hours=self.hours)
