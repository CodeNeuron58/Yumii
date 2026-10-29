"""Built-in TTS providers — importing this package registers them.

Import order IS menu order (dashboard choices). Adding a voice: write one
module here (register + build, plus present/provision if it keeps a local
model), then import it below. See yumii.core.providers.
"""

from yumii.tts.providers import kokoro  # noqa: F401
from yumii.tts.providers import elevenlabs  # noqa: F401
from yumii.tts.providers import camb  # noqa: F401
