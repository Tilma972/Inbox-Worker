"""
Pydantic models for Inbox Worker
"""
from pydantic import BaseModel
from typing import Optional, List


class ThreadSummary(BaseModel):
    thread_id: str
    snippet: str = ""


class MessageDetail(BaseModel):
    id: str
    thread_id: str
    subject: Optional[str] = None
    sender: Optional[str] = None       # From header
    to: Optional[str] = None
    date: Optional[str] = None
    snippet: Optional[str] = None
    label_ids: List[str] = []
    body_plain: Optional[str] = None
    body_html: Optional[str] = None
    is_auto_reply: bool = False
    internal_date: Optional[str] = None
    message_id_header: Optional[str] = None  # RFC 2822 Message-ID (for In-Reply-To)


class ThreadDetail(BaseModel):
    thread_id: str
    snippet: Optional[str] = None
    message_count: int
    messages: List[MessageDetail]


class DraftRequest(BaseModel):
    to: str
    subject: str
    body: str                                # HTML content
    reply_to_message_id: Optional[str] = None  # RFC 2822 Message-ID of original message
    thread_id: Optional[str] = None           # Gmail threadId to attach draft to


class DraftResponse(BaseModel):
    draft_id: str
    message_id: Optional[str] = None
    thread_id: Optional[str] = None


class LabelItem(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
