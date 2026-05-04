from raatverse_agent.config import get_settings


def test_config_loading_from_environment(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("CHANNEL_NAME", "TestVerse")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("STORY_CATEGORIES_CSV", "horror,mystery")
    monkeypatch.setenv("HUMAN_APPROVAL_REQUIRED", "true")

    settings = get_settings()

    assert settings.channel_name == "TestVerse"
    assert settings.database_url == "sqlite:///:memory:"
    assert settings.story_categories == ("horror", "mystery")
    assert settings.human_approval_required is True
    get_settings.cache_clear()
