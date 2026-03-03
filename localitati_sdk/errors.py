class LocalitatiSDKError(RuntimeError):
    """Base error for SDK."""


class AuthError(LocalitatiSDKError):
    """Authentication/refresh-token related errors."""


class APIError(LocalitatiSDKError):
    """HTTP errors from API."""

    def __init__(self, status_code: int, body: str):
        super().__init__(f"API error {status_code}: {body}")
        self.status_code = status_code
        self.body = body
