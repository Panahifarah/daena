from __future__ import annotations


class DaenaError(Exception):
    """Base exception for all daena errors."""


class ConfigurationError(DaenaError):
    """Configuration loading or validation failed."""


class BackendError(DaenaError):
    """Persistence backend operation failed."""


class PipelineError(DaenaError):
    """Pipeline processing error."""


class SinkError(DaenaError):
    """Sink delivery failed."""


class SinkPermanentError(SinkError):
    """Non-retryable sink failure."""


class SourceError(DaenaError):
    """Source collection error."""


class PluginError(DaenaError):
    """Plugin loading or registration error."""


class RecordInvalidError(DaenaError):
    """Record validation failed."""
