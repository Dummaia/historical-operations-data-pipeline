"""Domain-specific exceptions."""


class PipelineError(Exception):
    """Base exception for the pipeline."""


class ConfigurationError(PipelineError):
    """Raised when a pipeline configuration is invalid."""


class DataQualityError(PipelineError):
    """Raised when an input violates a blocking quality rule."""


class SnapshotDateError(PipelineError):
    """Raised when a snapshot date cannot be inferred from a filename."""
