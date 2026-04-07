"""
This module defines custom exceptions for handling errors in the application.
"""
class APIException(Exception):
    def __init__(self, error_msg, status_code, *args: object) -> None:
        super().__init__(error_msg, status_code, *args)
        self.error_msg = error_msg
        self.status_code = status_code

