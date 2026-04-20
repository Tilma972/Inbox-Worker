"""
Pydantic models for Inbox Worker
"""
from pydantic import BaseModel
from typing import Optional, List


class ThreadSummary(BaseModel):
    thread_id: str
    snippet: str = ""


class AttachmentInfo(BaseModel):
    attachment_id: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    size: int = 0


class AttachmentContent(BaseModel):
    message_id: str
    attachment_id: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    size: int = 0
    data_base64: str


class AttachmentStoreRequest(BaseModel):
    message_id: str
    attachment_id: str
    filename: str
    mime_type: Optional[str] = "application/octet-stream"
    bucket: str = "pj-recues"
    path_prefix: Optional[str] = None  # ex: "bdc-recus/2026-04"


class AttachmentStoreResponse(BaseModel):
    success: bool
    storage_path: Optional[str] = None
    storage_bucket: Optional[str] = None
    error: Optional[str] = None


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
    attachments: List[AttachmentInfo] = []


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
