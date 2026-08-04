import os
import pytest
from backend.config import settings, Settings

@pytest.mark.unit
def test_config_settings_initialization():
    """Verify that backend settings load default configuration properties."""
    assert settings.APP_ENV in ["development", "production", "testing", "test"]
    assert settings.API_PORT > 0
    assert isinstance(settings.ENABLE_KAFKA, bool)
    assert settings.UPLOAD_DIR is not None

@pytest.mark.unit
def test_upload_dir_creation():
    """Verify that the upload directory exists on filesystem."""
    assert os.path.exists(settings.UPLOAD_DIR)

@pytest.mark.unit
def test_custom_settings_override():
    """Verify custom settings overrides work as expected."""
    custom = Settings(API_PORT=9999, APP_ENV="testing")
    assert custom.API_PORT == 9999
    assert custom.APP_ENV == "testing"
