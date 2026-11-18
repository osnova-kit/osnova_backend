import hashlib
import hmac
import ipaddress
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import AfterValidator, Field
from pydantic_core import PydanticCustomError

from app.config import config
from app.core.entities import EntityType, entity_type
from app.core.mail import EmailMessage, deliver, render_html
from app.core.settings import Email, Secret

GROUP = "lead_channels"
TIMEOUT = 10
TELEGRAM_LIMIT = 4096


class DeliveryRejected(Exception):
    """The receiver refused the message: retrying will not help."""


@dataclass(frozen=True)
class LeadMessage:
    id: str
    form: str
    title: str
    language: str
    created_at: str
    fields: list[tuple[str, str]]
    data: dict[str, Any]

    @property
    def body(self) -> str:
        return "\n".join(f"{label}: {value}" for label, value in self.fields)

    @property
    def text(self) -> str:
        return f"{self.title}\n\n{self.body}"


def _json(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs) -> None:
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _check_public(url: str) -> None:
    """Refuse an address in the private network (the app's own services, cloud metadata)
    unless WEBHOOK_ALLOW_PRIVATE is set; redirects are not followed, for the same reason."""
    if config.WEBHOOK_ALLOW_PRIVATE:
        return
    host = urllib.parse.urlsplit(url).hostname or ""
    for *_, address in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP):
        if not ipaddress.ip_address(address[0]).is_global:
            raise DeliveryRejected(f"{host} is in a private network (WEBHOOK_ALLOW_PRIVATE)")


def _post_json(url: str, body: bytes, headers: dict[str, str] | None = None) -> None:
    _check_public(url)
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "Osnova", **(headers or {})},
    )
    try:
        with _opener.open(request, timeout=TIMEOUT):
            pass
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode(errors="replace")
        if exc.code < 500 and exc.code != 429:
            raise DeliveryRejected(f"HTTP {exc.code}: {detail}") from exc
        raise


def _http_url(value: str) -> str:
    if not value.startswith(("https://", "http://")):
        raise PydanticCustomError("url_invalid", "The address must start with https://")
    return value


@entity_type
class EmailChannel(EntityType):
    type = "lead_email"
    group = GROUP

    to: Email

    def send(self, message: LeadMessage) -> None:
        html = render_html(message.body, message.title, language=message.language)
        deliver(EmailMessage(to=self.to, subject=message.title, text=message.text, html=html))


@entity_type
class TelegramChannel(EntityType):
    type = "lead_telegram"
    group = GROUP

    bot_token: Annotated[Secret, Field(min_length=1)]
    chat_id: str = Field(min_length=1, max_length=64)

    def send(self, message: LeadMessage) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        _post_json(url, _json({"chat_id": self.chat_id, "text": message.text[:TELEGRAM_LIMIT]}))


@entity_type
class WebhookChannel(EntityType):
    type = "lead_webhook"
    group = GROUP

    url: Annotated[str, Field(min_length=1, max_length=500), AfterValidator(_http_url)]
    secret: Secret = ""

    def send(self, message: LeadMessage) -> None:
        payload = {
            "id": message.id,
            "form": message.form,
            "language": message.language,
            "created_at": message.created_at,
            "data": message.data,
        }
        body = _json(payload)
        headers = {}
        if self.secret:
            digest = hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()
            headers["X-Osnova-Signature"] = f"sha256={digest}"
        _post_json(self.url, body, headers)
