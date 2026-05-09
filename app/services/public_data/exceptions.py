class PublicDataError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class PublicDataUnavailableError(PublicDataError):
    pass


class PublicDataMalformedResponseError(PublicDataError):
    pass
