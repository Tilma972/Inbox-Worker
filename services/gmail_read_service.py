"""
Gmail Read Service — gmail.readonly + gmail.compose
Même architecture que GmailService (email-worker), scopes différents.
"""
import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, List, Dict, Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import settings

logger = logging.getLogger(__name__)

# Mots-clés détectant une réponse automatique dans le sujet
_AUTO_REPLY_SUBJECTS = (
    "absent", "absence", "automatique", "automatic reply",
    "out of office", "on vacation", "vacation", "hors du bureau",
    "réponse automatique", "autoreply",
)


def _headers_to_dict(headers: List[Dict[str, str]]) -> Dict[str, str]:
    return {h["name"]: h["value"] for h in headers}


def _is_auto_reply(headers: Dict[str, str]) -> bool:
    """
    Détecte les réponses automatiques via headers RFC et mots-clés sujet.
    Centralisé ici pour éviter la duplication côté skills.
    """
    auto_submitted = headers.get("Auto-Submitted", "no").lower()
    if auto_submitted and auto_submitted != "no":
        return True

    if headers.get("Precedence", "").lower() in ("bulk", "junk", "list"):
        return True

    if headers.get("X-Autoresponder") or headers.get("X-Autoreply"):
        return True

    subject = headers.get("Subject", "").lower()
    return any(kw in subject for kw in _AUTO_REPLY_SUBJECTS)


def _extract_body(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Extrait text/plain et text/html d'un payload Gmail (récursif multipart)."""
    plain: Optional[str] = None
    html: Optional[str] = None

    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            plain = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    elif mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    elif "parts" in payload:
        for part in payload["parts"]:
            sub = _extract_body(part)
            if sub["plain"] and plain is None:
                plain = sub["plain"]
            if sub["html"] and html is None:
                html = sub["html"]

    return {"plain": plain, "html": html}


def _parse_message(msg: Dict[str, Any], include_body: bool = True) -> Dict[str, Any]:
    """Transforme un objet message Gmail API en dict normalisé."""
    payload = msg.get("payload", {})
    headers = _headers_to_dict(payload.get("headers", []))

    entry: Dict[str, Any] = {
        "id": msg["id"],
        "thread_id": msg["threadId"],
        "subject": headers.get("Subject"),
        "sender": headers.get("From"),
        "to": headers.get("To"),
        "date": headers.get("Date"),
        "snippet": msg.get("snippet"),
        "label_ids": msg.get("labelIds", []),
        "is_auto_reply": _is_auto_reply(headers),
        "internal_date": msg.get("internalDate"),
        "message_id_header": headers.get("Message-ID"),
    }

    if include_body:
        body = _extract_body(payload)
        entry["body_plain"] = body["plain"]
        entry["body_html"] = body["html"]
    else:
        entry["body_plain"] = None
        entry["body_html"] = None

    return entry


class GmailReadService:
    _SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
    ]

    def __init__(self) -> None:
        self._service = None
        self.account: str = settings.gmail_account

    def _get_service(self):
        if self._service is None:
            credentials = Credentials(
                token=None,
                refresh_token=settings.gmail_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.gmail_client_id,
                client_secret=settings.gmail_client_secret,
                scopes=self._SCOPES,
            )
            self._service = build(
                "gmail", "v1",
                credentials=credentials,
                cache_discovery=False,
            )
            logger.debug("Gmail read client initialized for %s", self.account)
        return self._service

    def search(self, q: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """Recherche par threads. Retourne thread_id + snippet."""
        service = self._get_service()
        result = (
            service.users()
            .threads()
            .list(userId="me", q=q, maxResults=max_results)
            .execute()
        )
        threads = result.get("threads", [])
        return [{"thread_id": t["id"], "snippet": t.get("snippet", "")} for t in threads]

    def get_message(self, message_id: str) -> Dict[str, Any]:
        """Retourne un message complet (headers + body)."""
        service = self._get_service()
        msg = service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()
        return _parse_message(msg, include_body=True)

    def get_thread(self, thread_id: str, full: bool = False) -> Dict[str, Any]:
        """
        Retourne un thread avec tous ses messages.
        full=True : inclut les corps de messages (coûteux — utiliser avec parcimonie).
        """
        service = self._get_service()
        fmt = "full" if full else "metadata"
        thread = service.users().threads().get(
            userId="me", id=thread_id, format=fmt
        ).execute()

        messages = [
            _parse_message(msg, include_body=full)
            for msg in thread.get("messages", [])
        ]

        return {
            "thread_id": thread["id"],
            "snippet": thread.get("snippet"),
            "message_count": len(messages),
            "messages": messages,
        }

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        reply_to_message_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Crée un brouillon Gmail.
        reply_to_message_id : RFC 2822 Message-ID du message original (In-Reply-To).
        thread_id : Gmail threadId pour rattacher le brouillon au thread.
        """
        service = self._get_service()

        msg = MIMEMultipart("alternative")
        msg["To"] = to
        msg["From"] = self.account
        msg["Subject"] = subject
        if reply_to_message_id:
            msg["In-Reply-To"] = reply_to_message_id
            msg["References"] = reply_to_message_id
        msg.attach(MIMEText(body, "html", "utf-8"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        draft_body: Dict[str, Any] = {"message": {"raw": raw}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        result = service.users().drafts().create(userId="me", body=draft_body).execute()

        return {
            "draft_id": result["id"],
            "message_id": result.get("message", {}).get("id"),
            "thread_id": result.get("message", {}).get("threadId"),
        }

    def list_labels(self) -> List[Dict[str, Any]]:
        service = self._get_service()
        result = service.users().labels().list(userId="me").execute()
        return [
            {"id": lbl["id"], "name": lbl["name"], "type": lbl.get("type")}
            for lbl in result.get("labels", [])
        ]


gmail_read_service = GmailReadService()
