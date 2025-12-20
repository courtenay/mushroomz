"""Scene modules for lighting effects."""

from .base import Scene
from .state import is_manual_active
from .pastel_fade import PastelFadeScene
from .audio_pulse import AudioPulseScene
from .bio_glow import BioGlowScene
from .manual import ManualScene

__all__ = ["Scene", "PastelFadeScene", "AudioPulseScene", "BioGlowScene", "ManualScene", "is_manual_active"]
