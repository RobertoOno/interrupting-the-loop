"""creative-machine: fertile-error decoding for LLMs.

Anti-probable, entropy-adaptive sampling with a coherence guard. See
docs/PLANO.md for the thesis and architecture.
"""

from .config import SamplerConfig
from .sampler import AntiprobableSampler
from .telemetry import StepRecord, Telemetry

__version__ = "0.1.0"

__all__ = ["SamplerConfig", "AntiprobableSampler", "Telemetry", "StepRecord"]
