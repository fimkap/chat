class ChatAPIError(Exception):
    """An error occurred while interacting with the Policy API."""

    def __init__(self, message, original_exception=None):
        super().__init__(message)
        self.original_exception = original_exception

    def __str__(self):
        if self.original_exception:
            return (
                f"{super().__str__()} (Original Exception: {self.original_exception})"
            )
        return super().__str__()
