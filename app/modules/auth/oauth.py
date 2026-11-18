from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.exceptions import GetIdEmailError
from httpx_oauth.oauth2 import BaseOAuth2

from app.config import config

GOOGLE_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOpenID(GoogleOAuth2):
    """Google through the OpenID Connect userinfo endpoint.

    The stock client asks the People API, which has to be enabled in Google Cloud
    separately; userinfo works with just the OAuth client and also says whether
    Google has confirmed the email.
    """

    def __init__(self, client_id: str, client_secret: str):
        super().__init__(client_id, client_secret, scopes=["openid", "email"])

    async def get_id_email(self, token: str) -> tuple[str, str | None]:
        async with self.get_httpx_client() as client:
            response = await client.get(
                GOOGLE_USERINFO,
                headers={**self.request_headers, "Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            raise GetIdEmailError(response=response)
        data = response.json()
        # An unconfirmed email must not open (or be linked to) an account
        email = data.get("email") if data.get("email_verified") else None
        return data["sub"], email


def oauth_clients() -> dict[str, BaseOAuth2]:
    clients: dict[str, BaseOAuth2] = {}
    if "google" in config.oauth_providers:
        clients["google"] = GoogleOpenID(config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET)  # type: ignore[arg-type]
    return clients


def redirect_url(provider: str) -> str:
    return f"{config.FRONTEND_URL.rstrip('/')}/oauth/{provider}/callback"
