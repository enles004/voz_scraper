from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ThreadMeta:
    url: str
    title: str
    author: str | None = None
    published_at: datetime | None = None
    latest_at: datetime | None = None

    def marker(self, by: str) -> datetime | None:
        return self.latest_at if by == "active" else self.published_at


@dataclass
class Comment:
    author: str | None
    content: str
    posted_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "author": self.author,
            "content": self.content,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
        }


@dataclass
class ThreadRecord:
    id: int
    title: str
    url: str
    content: str
    author: str | None = None
    published_at: datetime | None = None
    tags: list[str] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)

    def to_dict(self) -> dict:
        record = {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "author": self.author,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "comments": [comment.to_dict() for comment in self.comments],
        }
        if self.tags:
            record["tags"] = self.tags
        return record
