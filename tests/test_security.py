"""
Tests de securite pour la gestion des cles API
"""

import pytest
import os
from unittest.mock import patch, MagicMock
import tempfile


class TestSecretsManager:
    """Tests du gestionnaire de secrets."""
    
    def test_get_claude_api_key_missing(self):
        """Test erreur quand la cle API est manquante."""
        from src.core.config import SecretsManager
        
        with patch('config._config') as mock_config:
            mock_config.claude_api_key = ""
            
            manager = SecretsManager()
            
            with pytest.raises(ValueError, match="n'est pas configuree"):
                manager.get_claude_api_key()
    
    def test_get_claude_api_key_success(self):
        """Test succes quand la cle API est presente."""
        from src.core.config import SecretsManager
        
        with patch('config._config') as mock_config:
            mock_config.claude_api_key = "sk-ant-test123"
            
            manager = SecretsManager()
            key = manager.get_claude_api_key()
            
            assert key == "sk-ant-test123"
            assert len(manager.get_audit_log()) == 1
    
    def test_mask_secret(self):
        """Test du masquage des secrets."""
        from src.core.config import SecretsManager
        
        manager = SecretsManager()
        
        # Secret normal
        masked = manager._mask_secret("sk-ant-api-key-12345")
        assert masked.startswith("sk-a")  # 4 premiers caracteres
        assert "****" in masked
        assert "12345" not in masked
    
    def test_mask_short_secret(self):
        """Test masquage d'un secret court."""
        from src.core.config import SecretsManager
        
        manager = SecretsManager()
        
        masked = manager._mask_secret("abc")
        assert masked == "****"
    
    def test_validate_all_secrets_success(self):
        """Test validation reussie des secrets."""
        from src.core.config import SecretsManager
        
        with patch('config._config') as mock_config:
            mock_config.claude_api_key = "sk-ant-test"
            
            manager = SecretsManager()
            
            # Ne doit pas lever d'erreur
            result = manager.validate_all_secrets('tesseract')
            assert result is True
    
    def test_validate_all_secrets_missing(self):
        """Test validation echouee quand secrets manquants."""
        from src.core.config import SecretsManager
        
        with patch('config._config') as mock_config:
            mock_config.claude_api_key = ""
            
            manager = SecretsManager()
            
            with pytest.raises(ValueError, match="Secrets manquants"):
                manager.validate_all_secrets('claude')
    
    def test_audit_log(self):
        """Test de l'audit log."""
        from src.core.config import SecretsManager
        
        with patch('config._config') as mock_config:
            mock_config.claude_api_key = "sk-ant-test"
            
            manager = SecretsManager()
            manager.get_claude_api_key()
            manager.get_claude_api_key()
            
            logs = manager.get_audit_log()
            assert len(logs) == 2
            
            manager.clear_audit_log()
            assert len(manager.get_audit_log()) == 0


class TestConfigValidation:
    """Tests de la validation de configuration."""
    
    def test_api_key_required_validation(self):
        """Test que la cle API est requise."""
        from src.core.config import AppConfig
        
        # Cle vide doit lever une erreur
        with pytest.raises(ValueError):
            AppConfig(claude_api_key="")
    
    def test_api_key_stripped(self):
        """Test que les espaces sont retires de la cle API."""
        from src.core.config import AppConfig
        
        config = AppConfig(claude_api_key="  sk-ant-test  ")
        assert config.claude_api_key == "sk-ant-test"
    
    def test_confidence_range_validation(self):
        """Test validation du range de confiance."""
        from src.core.config import AppConfig
        
        # Confiance invalide
        with pytest.raises(ValueError):
            AppConfig(claude_api_key="sk-test", min_confidence=1.5)
        
        with pytest.raises(ValueError):
            AppConfig(claude_api_key="sk-test", min_confidence=-0.1)
    
    def test_max_tokens_validation(self):
        """Test validation max tokens."""
        from src.core.config import AppConfig
        
        with pytest.raises(ValueError):
            AppConfig(claude_api_key="sk-test", claude_max_tokens=0)
    
    def test_min_samples_validation(self):
        """Test validation min samples."""
        from src.core.config import AppConfig
        
        with pytest.raises(ValueError):
            AppConfig(claude_api_key="sk-test", min_validated_samples=-1)


class TestEnvVars:
    """Tests des variables d'environnement."""
    
    def test_env_var_loading(self):
        """Test chargement des variables d'environnement."""
        from src.core.config import _load_config
        
        with patch.dict(os.environ, {'ARCHI_CLAUDE_API_KEY': 'env-test-key'}):
            config = _load_config()
            assert config.claude_api_key == "env-test-key"
    
    def test_env_var_prefix(self):
        """Test du prefixe ARCHI_."""
        from src.core.config import _load_config
        
        with patch.dict(os.environ, {
            'ARCHI_CLAUDE_MODEL': 'test-model',
            'ARCHI_MIN_CONFIDENCE': '0.9'
        }):
            config = _load_config()
            assert config.claude_model == "test-model"
            assert config.min_confidence == 0.9


class TestSecretsInLogs:
    """Tests que les secrets ne sont pas dans les logs."""
    
    def test_audit_log_masks_key(self):
        """Test que l'audit log ne contient pas la cle complete."""
        from src.core.config import SecretsManager
        
        with patch('config._config') as mock_config:
            mock_config.claude_api_key = "sk-ant-very-long-secret-key-12345"
            
            manager = SecretsManager()
            manager.get_claude_api_key()
            
            logs = manager.get_audit_log()
            log_entry = logs[0]
            
            # La cle complete ne doit pas etre dans le log
            assert "very-long-secret" not in str(log_entry)
            assert "12345" not in str(log_entry)
            
            # Mais la cle masquee doit etre presente
            assert "sk-a" in str(log_entry.get('masked_key', ''))


class TestSecureFileOperations:
    """Tests des operations securisees sur fichiers."""
    
    def test_gitignore_exists(self):
        """Test que .gitignore existe et protege .env."""
        from pathlib import Path
        
        root = Path(__file__).parent.parent
        gitignore = root / ".gitignore"
        
        assert gitignore.exists()
        
        content = gitignore.read_text()
        
        # Verifier les entrees importantes
        assert '.env' in content or '*.env' in content
        assert '*.db' in content
        assert 'training_data.db' in content or '*.db' in content
    
    def test_env_example_exists(self):
        """Test que .env.example existe."""
        from pathlib import Path
        
        root = Path(__file__).parent.parent
        env_example = root / ".env.example"
        
        assert env_example.exists()
        
        content = env_example.read_text()
        
        # Verifier que c'est un template
        assert 'ARCHI_CLAUDE_API_KEY' in content
        assert 'example' in content.lower() or 'votre' in content.lower()
