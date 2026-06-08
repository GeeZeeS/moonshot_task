class ProxyError(Exception):
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int,
        details: list[str] | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)


class UpstreamServiceError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
