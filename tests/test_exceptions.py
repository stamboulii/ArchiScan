"""
Tests pour les exceptions personalisees
"""

import pytest
from unittest.mock import patch, MagicMock


class TestConfigurationErrors:
    """Tests des erreurs de configuration."""
    
    def test_missing_api_key_error(self):
        """Test MissingAPIKeyError."""
        from src.core.exceptions import MissingAPIKeyError
        
        error = MissingAPIKeyError("Claude")
        assert "Claude" in str(error)
        assert "ARCHI_CLAUDE_API_KEY" in str(error)
        assert error.api_name == "Claude"
    
    def test_missing_api_key_with_suggestion(self):
        """Test MissingAPIKeyError avec suggestion personalisee."""
        from src.core.exceptions import MissingAPIKeyError
        
        error = MissingAPIKeyError("Test", suggestion="Utilisez .env")
        assert "Utilisez .env" in str(error)


class TestExtractionErrors:
    """Tests des erreurs d'extraction."""
    
    def test_image_load_error(self):
        """Test ImageLoadError."""
        from src.core.exceptions import ImageLoadError
        
        error = ImageLoadError("/path/to/image.png")
        assert "image.png" in str(error)
        assert error.image_path == "/path/to/image.png"
    
    def test_pdf_conversion_error(self):
        """Test PDFConversionError."""
        from src.core.exceptions import PDFConversionError
        
        error = PDFConversionError("/path/to/file.pdf", reason="Locked")
        assert "file.pdf" in str(error)
        assert "Locked" in str(error)


class TestAPIErrors:
    """Tests des erreurs API."""
    
    def test_claude_api_error(self):
        """Test ClaudeAPIError."""
        from src.core.exceptions import ClaudeAPIError
        
        error = ClaudeAPIError("Rate limit exceeded", status_code=429)
        assert "Rate limit exceeded" in str(error)
        assert error.status_code == 429
    
    def test_api_response_error(self):
        """Test APIResponseError."""
        from src.core.exceptions import APIResponseError
        
        error = APIResponseError('{"invalid": json}')
        assert "invalid" in str(error)
    
    def test_no_json_found_error(self):
        """Test NoJSONFoundError."""
        from src.core.exceptions import NoJSONFoundError
        
        error = NoJSONFoundError("no json here")
        assert "no json here" in str(error)


class TestMLErrors:
    """Tests des erreurs ML."""
    
    def test_missing_ml_dependency_error(self):
        """Test MissingMLDependencyError."""
        from src.core.exceptions import MissingMLDependencyError
        
        error = MissingMLDependencyError("torch", install_cmd="pip install torch")
        assert "torch" in str(error)
        assert "pip install torch" in str(error)
    
    def test_no_trained_model_error(self):
        """Test NoTrainedModelError."""
        from src.core.exceptions import NoTrainedModelError
        
        error = NoTrainedModelError("/models/my-model")
        assert "my-model" in str(error)
        assert error.model_dir == "/models/my-model"


class TestExceptionHierarchy:
    """Tests de la hierarchie des exceptions."""
    
    def test_archi_extract_error_is_base(self):
        """Test que ArchiExtractError est la classe de base."""
        from src.core.exceptions import ArchiExtractError
        
        error = ArchiExtractError("Test message", details="Details")
        assert str(error) == "Test message: Details"
        assert error.message == "Test message"
        assert error.details == "Details"
    
    def test_configuration_error_inheritance(self):
        """Test heritage ConfigurationError."""
        from src.core.exceptions import ConfigurationError, ArchiExtractError
        
        error = ConfigurationError("Config error")
        assert isinstance(error, ArchiExtractError)
    
    def test_extraction_error_inheritance(self):
        """Test heritage ExtractionError."""
        from src.core.exceptions import ExtractionError, ArchiExtractError
        
        error = ExtractionError("Extraction error")
        assert isinstance(error, ArchiExtractError)
    
    def test_api_error_inheritance(self):
        """Test heritage APIError."""
        from src.core.exceptions import APIError, ArchiExtractError
        
        error = APIError("API error")
        assert isinstance(error, ArchiExtractError)
    
    def test_ml_error_inheritance(self):
        """Test heritage MLError."""
        from src.core.exceptions import MLError, ArchiExtractError
        
        error = MLError("ML error")
        assert isinstance(error, ArchiExtractError)


class TestExceptionWrapping:
    """Tests du wrapping d'exceptions."""
    
    def test_wrap_extraction_error(self):
        """Test wrap_extraction_error."""
        from src.core.exceptions import wrap_extraction_error, ExtractionError
        
        original = ValueError("Original error")
        wrapped = wrap_extraction_error(original, context="Test context")
        
        assert isinstance(wrapped, ExtractionError)
        assert "Original error" in str(wrapped)
    
    def test_wrap_already_wrapped(self):
        """Test qu'une exception deja formatee n'est pas re-wrap."""
        from src.core.exceptions import ExtractionError, wrap_extraction_error
        
        original = ExtractionError("Already wrapped")
        wrapped = wrap_extraction_error(original)
        
        assert wrapped is original
