"""Data models for Reddit submissions."""

from typing import TypedDict, Optional


class SubmissionRecord(TypedDict):
    """
    TypedDict representing a Reddit submission record.
    
    This matches the data model specified in the PRD section 6.6.
    """
    
    id: str  # Reddit base36 ID
    created_utc: int  # Unix epoch
    subreddit: str  # lowercase
    title: str  # UTF-8
    selftext: str  # May be empty
    author: str  # [deleted] allowed
    score: int  # Up-votes minus down-votes
    upvote_ratio: float  # 0–1
    num_comments: int  # Snapshot at fetch
    url: str  # Submission URL
    flair_text: Optional[str]  # Nullable
    over_18: bool  # NSFW flag
