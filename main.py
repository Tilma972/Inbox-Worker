"""
Inbox Worker — FastAPI service
Lecture Gmail (search, message, thread, draft, labels) pour FlowChat.
Remplace les appels gog CLI dans les skills.
"""
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
import logging
from googleapiclient.errors import HttpError

from config import settings
from models import (
    ThreadSummary,
    MessageDetail,
    ThreadDetail,
    DraftRequest,
    DraftResponse,
    LabelItem,
)
from services import gmail_read_service

logging.basicConfig(level=logging.INFO if settings.debug else logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Worker de lecture inbox Gmail pour FlowChat",
    version="1.0.0",
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "healthy", "services": {"gmail_read": "ready"}}


@app.get("/inbox/search", response_model=list[ThreadSummary])
async def search_inbox(
    q: str = Query(default="is:unread", description="Gmail search query"),
    max: int = Query(default=20, ge=1, le=100, description="Max results"),
):
    try:
        logger.info("🔍 inbox search q=%r max=%d", q, max)
        return gmail_read_service.search(q=q, max_results=max)
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error("inbox search failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/inbox/message/{message_id}", response_model=MessageDetail)
async def get_message(message_id: str):
    try:
        logger.info("📨 get message %s", message_id)
        return gmail_read_service.get_message(message_id)
    except HttpError as e:
        if e.resp.status == 404:
            raise HTTPException(status_code=404, detail="Message not found")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error("get message failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/inbox/thread/{thread_id}", response_model=ThreadDetail)
async def get_thread(
    thread_id: str,
    full: bool = Query(default=False, description="Include full message body (coûteux)"),
):
    try:
        logger.info("🧵 get thread %s full=%s", thread_id, full)
        return gmail_read_service.get_thread(thread_id, full=full)
    except HttpError as e:
        if e.resp.status == 404:
            raise HTTPException(status_code=404, detail="Thread not found")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error("get thread failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/drafts", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
async def create_draft(request: DraftRequest):
    try:
        logger.info("📝 create draft to=%s subject=%r", request.to, request.subject)
        return gmail_read_service.create_draft(
            to=request.to,
            subject=request.subject,
            body=request.body,
            reply_to_message_id=request.reply_to_message_id,
            thread_id=request.thread_id,
        )
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error("create draft failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/inbox/labels", response_model=list[LabelItem])
async def list_labels():
    try:
        return gmail_read_service.list_labels()
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error("list labels failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)
