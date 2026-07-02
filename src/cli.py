import argparse
import sys

from . import exporters
from config import DEFAULT_FORUM_URL, ScrapeSettings
from .crawler import VozCrawler


def parse_args(argv: list[str] | None = None) -> ScrapeSettings:
    parser = argparse.ArgumentParser(
        description="Thu thập các bài viết mới trên forum voz.vn, bỏ bài ghim, xuất ra zip chứa JSON."
    )
    parser.add_argument("--url", default=DEFAULT_FORUM_URL)
    parser.add_argument("--hours", type=float, default=6.0)
    parser.add_argument("--output", default="voz_posts.zip")
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--rate", type=float, default=5.0)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--fresh", action="store_true", help="Bỏ checkpoint cũ, chạy lại từ đầu")
    parser.add_argument("--by", choices=["active", "created"], default="active")
    args = parser.parse_args(argv)
    return ScrapeSettings(
        forum_url=args.url,
        hours=args.hours,
        output=args.output,
        max_pages=args.max_pages,
        workers=args.workers,
        rate=args.rate,
        retries=args.retries,
        fresh=args.fresh,
        by=args.by,
    )


def run(argv: list[str] | None = None) -> None:
    settings = parse_args(argv)
    crawler = VozCrawler(settings)
    records, failures = crawler.run()
    exporters.write_zip(records, settings.output, failures=failures)
    message = f"Đã ghi {len(records)} bài viết vào {settings.output}"
    if failures:
        message += f" (kèm failures.json: {len(failures)} mục lỗi)"
    print(message, file=sys.stderr)
