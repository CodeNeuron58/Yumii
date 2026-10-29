"""Built-in STT providers — importing this package registers them.

Import order IS menu order (dashboard choices). Adding an ear: write one
module here (register + build, plus present/provision if it keeps a local
model), then import it below. See yumii.core.providers.
"""

from yumii.audio.providers import nemotron  # noqa: F401
from yumii.audio.providers import moonshine  # noqa: F401
from yumii.audio.providers import whisper  # noqa: F401
from yumii.audio.providers import groq  # noqa: F401
from yumii.audio.providers import vosk  # noqa: F401
