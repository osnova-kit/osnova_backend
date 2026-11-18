from dataclasses import asdict, dataclass

from app.core.i18n import translate, translate_optional
from app.core.mail.layout import render_html


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


def render_mail(name: str, to: str, language: str | None = None, **params) -> EmailMessage:
    """A message from the "mail" translations: "<name>.subject" and "<name>.body".

    The HTML version is built from the same text; with a ``link`` parameter the line
    holding it becomes a button labelled "<name>.button".
    """
    subject = translate(f"mail.{name}.subject", language, **params)
    text = translate(f"mail.{name}.body", language, **params)
    return EmailMessage(
        to=to,
        subject=subject,
        text=text,
        html=render_html(
            text,
            subject,
            link=params.get("link"),
            button=translate_optional(f"mail.{name}.button", language),
            language=language,
        ),
    )
