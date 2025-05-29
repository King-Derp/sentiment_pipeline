"""Mapping functions to convert Reddit API objects to our data models."""

import logging
from typing import Dict, Any, List, Optional

from asyncpraw.models import Submission

from reddit_scraper.models.submission import SubmissionRecord

logger = logging.getLogger(__name__)


def submission_to_record(submission: Submission) -> SubmissionRecord:
    """
    Convert an asyncpraw Submission object to a SubmissionRecord.
    
    Args:
        submission: The Reddit submission object from asyncpraw
        
    Returns:
        A SubmissionRecord TypedDict with the submission data
    """
    # Handle potentially missing author (deleted accounts)
    author_name = "[deleted]"
    if submission.author:
        author_name = submission.author.name
    
    # Handle potentially missing flair text
    flair_text: Optional[str] = None
    if hasattr(submission, "link_flair_text") and submission.link_flair_text:
        flair_text = submission.link_flair_text
    
    # Create the record
    record: SubmissionRecord = {
        "id": submission.id,
        "created_utc": submission.created_utc,
        "subreddit": submission.subreddit.display_name.lower(),
        "title": submission.title,
        "selftext": submission.selftext,
        "author": author_name,
        "score": submission.score,
        "upvote_ratio": submission.upvote_ratio,
        "num_comments": submission.num_comments,
        "url": submission.url,
        "flair_text": flair_text,
        "over_18": submission.over_18
    }
    
    return record


def submissions_to_records(submissions: List[Submission]) -> List[SubmissionRecord]:
    """
    Convert a list of asyncpraw Submission objects to SubmissionRecords.
    
    Args:
        submissions: List of Reddit submission objects from asyncpraw
        
    Returns:
        List of SubmissionRecord TypedDicts
    """
    records = []
    
    for submission in submissions:
        try:
            record = submission_to_record(submission)
            records.append(record)
        except Exception as e:
            logger.warning(f"Failed to convert submission {submission.id}: {str(e)}")
            
    return records
