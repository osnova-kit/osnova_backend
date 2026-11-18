from html import escape
from pathlib import Path
from string import Template

from app.core.i18n import get_language, translate
from app.core.settings import settings

_DIR = Path(__file__).parent
LAYOUT = Template((_DIR / "layout.html").read_text(encoding="utf-8"))
BUTTON = Template((_DIR / "button.html").read_text(encoding="utf-8"))
PARAGRAPH = '<p style="margin:0 0 16px;">{}</p>'


def render_html(
    text: str,
    subject: str,
    *,
    link: str | None = None,
    button: str | None = None,
    language: str | None = None,
) -> str:
    language = language or get_language()
    if link and not link.startswith(("https://", "http://")):
        link = None
    button_html = link and BUTTON.substitute(
        link=escape(link),
        label=escape(button or translate("mail.open", language)),
        fallback=escape(translate("mail.link_fallback", language)),
    )
    blocks: list[str] = []
    for paragraph in text.strip().split("\n\n"):
        lines: list[str] = []
        for line in paragraph.split("\n"):
            if line != link:
                lines.append(escape(line))
                continue
            if lines:
                blocks.append(PARAGRAPH.format("<br>".join(lines)))
                lines = []
            blocks.append(button_html)
        if lines:
            blocks.append(PARAGRAPH.format("<br>".join(lines)))
    # Imported here: app.settings lists the mail settings of this package
    from app.settings import SiteSettings

    site = settings.get(SiteSettings).name
    return LAYOUT.substitute(
        language=escape(language),
        subject=escape(subject),
        site=escape(site),
        content="\n".join(blocks),
        footer=escape(translate("mail.footer", language, site=site)),
    )
