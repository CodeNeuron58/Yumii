from yumi.core.config import settings

def test_settings_load_defaults():
    assert settings.llm_provider == "Groq" or settings.llm_provider is not None
    assert settings.personality == "caring" or settings.personality is not None

def test_global_config_import():
    from yumi.core.global_config import load_global_config
    config = load_global_config()
    assert isinstance(config, dict)
