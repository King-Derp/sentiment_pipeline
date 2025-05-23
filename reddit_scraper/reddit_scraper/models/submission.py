"""Data models for Reddit submissions."""

from typing import TypedDict, Optional
from sqlalchemy import Column, String, Integer, BigInteger, Float, Boolean, Text, Index, PrimaryKeyConstraint
from sqlalchemy.orm import mapped_column, Mapped
from .base import Base


class SubmissionORM(Base):
    """
    SQLAlchemy ORM model for Reddit submissions.
    This table will store raw submission data scraped from Reddit.
    """
    __tablename__ = "raw_submissions"

    id: Mapped[str] = mapped_column(String, primary_key=False, comment="Reddit base36 ID")
    created_utc: Mapped[int] = mapped_column(BigInteger, primary_key=False, comment="Unix epoch timestamp of creation")
    subreddit: Mapped[str] = mapped_column(String, index=True, comment="Subreddit name, lowercase")
    title: Mapped[str] = mapped_column(Text, comment="Submission title, UTF-8")
    selftext: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Submission self-text, may be empty")
    author: Mapped[str] = mapped_column(String, comment="Reddit username of the author, or '[deleted]'")
    score: Mapped[int] = mapped_column(Integer, comment="Submission score (upvotes - downvotes)")
    upvote_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Upvote ratio (0.0 to 1.0)")
    num_comments: Mapped[int] = mapped_column(Integer, comment="Number of comments at the time of scrape")
    url: Mapped[str] = mapped_column(String, comment="URL of the submission")
    flair_text: Mapped[Optional[str]] = mapped_column(String, nullable=True, comment="Flair text, if any")
    over_18: Mapped[bool] = mapped_column(Boolean, default=False, comment="NSFW (Not Safe For Work) flag")

    __table_args__ = (
        PrimaryKeyConstraint('id', 'created_utc', name='pk_submission_id_created_utc'),
        Index("ix_raw_submissions_subreddit_created_utc", "subreddit", "created_utc"),
        {'comment': 'Stores raw Reddit submission data before processing. Partitioned by created_utc.'}
    )

    def __repr__(self) -> str:
        return f"<SubmissionORM(id='{self.id}', subreddit='{self.subreddit}', created_utc='{self.created_utc}')>"


class SubmissionRecord(TypedDict):
    """
    TypedDict representing a Reddit submission record.
    This can be used for type hinting data before it's mapped to SubmissionORM.
    """
    id: str
    created_utc: int
    subreddit: str
    title: str
    selftext: Optional[str] 
    author: str
    score: int
    upvote_ratio: Optional[float] 
    num_comments: int
    url: str
    flair_text: Optional[str]
    over_18: bool
