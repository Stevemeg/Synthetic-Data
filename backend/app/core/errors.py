class AppError(Exception):
    """An intentional, consumer-safe failure."""

    def __init__(self, message: str, code: str = "invalid_request", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


class UnavailableError(AppError):
    def __init__(self, message: str):
        super().__init__(message, "unavailable", 501)
