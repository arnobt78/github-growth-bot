import httpx


class EmailClient:
    """Thin wrapper around Resend's REST API, mirroring GitHubClient's
    httpx.Client-based shape. Unlike GitHubClient (which raises
    GitHubAuthError on a rejected token), send() never raises — a Resend
    outage must degrade to "no email sent for this one alert," never crash
    the scheduled job that's calling it."""

    def __init__(self, api_key: str, from_address: str, http_client: httpx.Client | None = None):
        self._from = from_address
        self._http = http_client or httpx.Client(
            base_url="https://api.resend.com",
            timeout=10.0,
        )
        self._http.headers["Authorization"] = f"Bearer {api_key}"

    def send(self, to: str, subject: str, html: str) -> bool:
        try:
            resp = self._http.post(
                "/emails",
                json={"from": self._from, "to": [to], "subject": subject, "html": html},
            )
            resp.raise_for_status()
            return True
        except httpx.HTTPError:
            return False
