"""Safe public errors with optional private provider detail for compatibility adapters."""


class MealieApiError(RuntimeError):
    def __init__(self, status: int, safe_message: str, *, body: str = "") -> None:
        super().__init__(safe_message)
        self.status = status
        self.body = body


class MealieTransportError(RuntimeError):
    """Transport failed; a write may already have reached the upstream."""
