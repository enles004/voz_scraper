import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .models import Comment, ThreadMeta

_PARSER = "lxml"


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, _PARSER)


def parse_datetime(tag) -> datetime | None:
    if tag is None:
        return None
    raw = tag.get("datetime")
    if not raw:
        return None
    raw = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_pinned(item) -> bool:
    classes = item.get("class", [])
    if any("sticky" in cls for cls in classes):
        return True
    label = item.select_one(".structItem-status--sticky, .label--accent")
    if label and re.search(r"ghim|sticky|dính", label.get_text(strip=True), re.IGNORECASE):
        return True
    return False


def parse_thread_items(soup: BeautifulSoup, base_url: str) -> list[ThreadMeta]:
    items: list[ThreadMeta] = []
    for item in soup.select(".structItem--thread"):
        if is_pinned(item):
            continue
        title_tag = item.select_one(".structItem-title a[href*='/t/'], .structItem-title a")
        if title_tag is None:
            continue
        url = urljoin(base_url, title_tag.get("href", ""))
        title = title_tag.get_text(strip=True)
        author = item.get("data-author")
        if not author:
            author_tag = item.select_one(".structItem-parts .username, .structItem-minor .username")
            author = author_tag.get_text(strip=True) if author_tag else None
        start_time = parse_datetime(item.select_one(".structItem-startDate time"))
        latest_time = parse_datetime(
            item.select_one(".structItem-latestDate, .structItem-latestDate time")
        )
        if latest_time is None:
            times = item.select("time.u-dt")
            if times:
                latest_time = parse_datetime(times[-1])
        items.append(
            ThreadMeta(
                url=url,
                title=title,
                author=author,
                published_at=start_time,
                latest_at=latest_time,
            )
        )
    return items


def next_page_url(soup: BeautifulSoup, base_url: str) -> str | None:
    link = soup.select_one("a.pageNav-jump--next")
    if link and link.get("href"):
        return urljoin(base_url, link["href"])
    return None


def last_page_number(soup: BeautifulSoup) -> int:
    numbers = [
        int(text)
        for link in soup.select(".pageNav-main a")
        if (text := link.get_text(strip=True)).isdigit()
    ]
    return max(numbers) if numbers else 1


def parse_message(article) -> Comment:
    author = article.get("data-author")
    if not author:
        name = article.select_one(".message-name .username, .message-name")
        author = name.get_text(strip=True) if name else None
    body = article.select_one(".message-body .bbWrapper, .bbWrapper")
    content = body.get_text("\n", strip=True) if body else ""
    posted_at = parse_datetime(article.select_one("time.u-dt"))
    return Comment(author=author, content=content, posted_at=posted_at)


def parse_messages(soup: BeautifulSoup) -> list[Comment]:
    return [parse_message(article) for article in soup.select("article.message--post, article.message")]


def parse_tags(soup: BeautifulSoup) -> list[str]:
    return [tag.get_text(strip=True) for tag in soup.select(".tagList a.tagItem, .js-tagList a")]
