class ClipSelectionError(Exception):
    """Base class for all clip selection pipeline errors."""
    def __init__(self, message, context=None):
        super().__init__(message)
        self.context = context or {}

class TransientLLMError(ClipSelectionError):
    """Network timeouts, rate limits, or 5xx from the model provider. Safe to retry."""
    pass

class InvalidModelOutput(ClipSelectionError):
    """Model returned unparseable JSON or schema violations. Usually not retried unless varying temperature."""
    pass

class NoCandidates(ClipSelectionError):
    """No viable clips were found in the source material. Terminal."""
    pass

class DependencyError(ClipSelectionError):
    """Missing API keys, missing binaries, or unmet local dependencies. Terminal."""
    pass
