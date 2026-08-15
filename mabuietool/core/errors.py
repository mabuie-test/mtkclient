"""Typed error hierarchy and friendly formatting."""

class MabuiEToolError(Exception):
    category = "ApplicationError"


class USBError(MabuiEToolError):
    category = "USBError"


class DeviceError(MabuiEToolError):
    category = "DeviceError"


class ProtocolError(MabuiEToolError):
    category = "ProtocolError"


class BackendError(MabuiEToolError):
    category = "BackendError"


class PermissionError(MabuiEToolError):
    category = "PermissionError"


class ConfigurationError(MabuiEToolError):
    category = "ConfigurationError"


class ErrorManager:
    @staticmethod
    def friendly(error: Exception, context: str = "") -> tuple[str, str]:
        title = "Não foi possível concluir a operação."
        details = f"Context: {context}\nError: {error}" if context else f"Error: {error}"
        if isinstance(error, MabuiEToolError):
            title = "Não foi possível estabelecer comunicação com o dispositivo."
            details = f"Category: {error.category}\n{details}"
        return title, details
