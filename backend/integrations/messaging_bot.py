"""Outbound messaging (WhatsApp / SMS) — provider-agnostic.

    NO REAL PROVIDER IS WIRED UP. Everything here runs against StubSender, which
    LOGS the message it would have sent and returns a synthetic id. No third-party
    account has been created, no SDK is imported, and no credentials exist in this
    repo. See the TODO blocks in TwilioSender / GupshupSender / WhatsAppCloudSender
    for exactly where the real calls go.

Why an interface instead of provider calls at the call sites:

The rest of the codebase only ever touches `get_sender().send(...)` and the
`MessageSender` protocol. Swapping Twilio for Gupshup — or running the stub in
staging and a real provider in production — is a config change plus one subclass,
with nothing to hunt down across routers. Provider SDKs also disagree about
everything (auth, payload shape, response format, error taxonomy), so keeping that
mess behind one boundary is what stops it leaking into request handlers.

Delivery is best-effort and must never be load-bearing: a failed send returns a
failed MessageResult, it does not raise into the caller's request.
"""
import logging
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger("ksp-messaging")

# Channels a message can go out on.
CHANNEL_WHATSAPP = "whatsapp"
CHANNEL_SMS = "sms"
CHANNELS = (CHANNEL_WHATSAPP, CHANNEL_SMS)


def mask_phone(phone: str) -> str:
    """`+919845012345` -> `+91*******345`.

    Never log a full number: these logs are operational telemetry, not a place for
    complainant contact details to accumulate.
    """
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 4:
        return "***"
    keep = digits[-3:]
    prefix = phone[:3] if phone.startswith("+") else ""
    return f"{prefix}{'*' * max(0, len(digits) - 3 - len(prefix.lstrip('+')))}{keep}"


@dataclass
class MessageResult:
    """Uniform result shape, whichever provider ran."""
    success: bool
    provider: str
    channel: str
    to_masked: str
    message_id: str | None = None
    error: str | None = None
    simulated: bool = False        # True whenever nothing actually left the building
    sent_at: datetime = field(default_factory=datetime.utcnow)

    def as_dict(self) -> dict:
        return {
            "success": self.success,
            "provider": self.provider,
            "channel": self.channel,
            "to": self.to_masked,
            "message_id": self.message_id,
            "error": self.error,
            "simulated": self.simulated,
            "sent_at": self.sent_at,
        }


class MessageSender(Protocol):
    """The whole contract. A provider implements exactly this."""

    name: str

    def send(self, to: str, body: str, channel: str = CHANNEL_SMS) -> MessageResult: ...


class StubSender:
    """Logs the message instead of sending it. The only sender wired up today.

    `simulated=True` on every result, so a caller can never mistake a logged
    message for a delivered one.
    """

    name = "stub"

    def __init__(self, sink: list | None = None):
        # An optional in-memory sink makes the outbox assertable in tests without
        # scraping log output.
        self.sink = sink if sink is not None else []

    def send(self, to: str, body: str, channel: str = CHANNEL_SMS) -> MessageResult:
        if channel not in CHANNELS:
            return MessageResult(False, self.name, channel, mask_phone(to),
                                 error=f"Unknown channel {channel!r}", simulated=True)

        masked = mask_phone(to)
        message_id = f"stub-{uuid.uuid4().hex[:12]}"
        logger.info(
            "SIMULATED %s to %s (id=%s): %s",
            channel.upper(), masked, message_id, body.replace("\n", " | ")
        )
        result = MessageResult(True, self.name, channel, masked,
                               message_id=message_id, simulated=True)
        self.sink.append({"to": masked, "body": body, "channel": channel, "id": message_id})
        return result


class TwilioSender:
    """Twilio — NOT IMPLEMENTED.

    TODO(provider): to enable
      1. pip install twilio                      (deliberately absent from requirements)
      2. set TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER
      3. replace the body of send() with:
             from twilio.rest import Client
             client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
             to_addr = f"whatsapp:{to}" if channel == CHANNEL_WHATSAPP else to
             frm     = f"whatsapp:{settings.TWILIO_FROM_NUMBER}" if channel == CHANNEL_WHATSAPP \\
                       else settings.TWILIO_FROM_NUMBER
             msg = client.messages.create(body=body, from_=frm, to=to_addr)
             return MessageResult(True, self.name, channel, mask_phone(to), message_id=msg.sid)
      4. wrap that in try/except and return a failed MessageResult on error --
         never raise into the request.
    """

    name = "twilio"

    def send(self, to: str, body: str, channel: str = CHANNEL_SMS) -> MessageResult:
        return MessageResult(
            False, self.name, channel, mask_phone(to),
            error="Twilio sender is not implemented; no credentials are configured. "
                  "See the TODO in integrations/messaging_bot.py.",
            simulated=True,
        )


class GupshupSender:
    """Gupshup — NOT IMPLEMENTED.

    TODO(provider): set GUPSHUP_API_KEY / GUPSHUP_SOURCE / GUPSHUP_APP_NAME and POST
    to https://api.gupshup.io/wa/api/v1/msg with `apikey` in the headers. Gupshup is
    a plain HTTP API, so `requests` (already a dependency) is enough -- no SDK needed.
    """

    name = "gupshup"

    def send(self, to: str, body: str, channel: str = CHANNEL_SMS) -> MessageResult:
        return MessageResult(
            False, self.name, channel, mask_phone(to),
            error="Gupshup sender is not implemented; no credentials are configured.",
            simulated=True,
        )


class WhatsAppCloudSender:
    """WhatsApp Business Cloud API — NOT IMPLEMENTED.

    TODO(provider): set WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN and POST to
    https://graph.facebook.com/v20.0/{phone_number_id}/messages.

    NOTE for whoever wires this up: outside a 24-hour customer-service window Meta
    only permits pre-approved message TEMPLATES, not free text. An FIR-status reply
    sent proactively will need an approved template, so `body` cannot simply be
    forwarded -- that is a product/compliance step, not a code one.
    """

    name = "whatsapp_cloud"

    def send(self, to: str, body: str, channel: str = CHANNEL_WHATSAPP) -> MessageResult:
        return MessageResult(
            False, self.name, channel, mask_phone(to),
            error="WhatsApp Cloud sender is not implemented; no credentials are configured.",
            simulated=True,
        )


_PROVIDERS = {
    "stub": StubSender,
    "twilio": TwilioSender,
    "gupshup": GupshupSender,
    "whatsapp_cloud": WhatsAppCloudSender,
}

_sender: MessageSender | None = None


def get_sender() -> MessageSender:
    """The one entry point the rest of the app uses.

    Defaults to the stub. An unknown provider name falls back to the stub with a
    warning rather than raising: a misconfigured provider should degrade to "nothing
    was sent, and we said so", not take the API down.
    """
    global _sender
    if _sender is None:
        from app.config import settings
        name = (getattr(settings, "MESSAGING_PROVIDER", "stub") or "stub").lower()
        cls = _PROVIDERS.get(name)
        if cls is None:
            logger.warning("Unknown MESSAGING_PROVIDER %r; falling back to the stub sender.", name)
            cls = StubSender
        _sender = cls()
        if name != "stub":
            logger.warning(
                "MESSAGING_PROVIDER=%r is selected but not implemented -- sends will fail "
                "with simulated=True until its TODO block is completed.", name
            )
    return _sender


def reset_sender() -> None:
    """Drops the cached sender (used by tests and after a config change)."""
    global _sender
    _sender = None


def build_status_message(fir_number: str, status_label: str) -> str:
    """The exact text a complainant receives.

    Carries the status and nothing else -- no officer name, no station, no accused,
    no dates. Anyone holding the FIR number and phone gets progress, not case detail.
    """
    return (
        f"KSP Sentinel: FIR {fir_number} is currently '{status_label}'. "
        f"For details please contact the police station where the complaint was filed. "
        f"Emergency: 112. Do not reply to this message."
    )
