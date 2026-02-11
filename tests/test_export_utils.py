"""
Tests pour les utilitaires d'export (CSV, Excel, etc.)
"""

import pytest
import json
import tempfile
from pathlib import Path


class TestFlattenDict:
    """Tests de la fonction flatten_dict."""
    
    def test_flatten_simple_dict(self):
        """Test aplanissement d'un dict simple."""
        from src.core.export_utils import flatten_dict
        
        data = {"a": 1, "b": 2}
        result = flatten_dict(data)
        assert result == {"a": 1, "b": 2}
    
    def test_flatten_nested_dict(self):
        """Test aplanissement d'un dict imbrique."""
        from src.core.export_utils import flatten_dict
        
        data = {
            "surfaceDetail": {"terrasse": 7.5, "balcon": 4.2}
        }
        result = flatten_dict(data)
        assert result == {"surfaceDetail_terrasse": 7.5, "surfaceDetail_balcon": 4.2}
    
    def test_flatten_with_list(self):
        """Test aplanissement avec liste."""
        from src.core.export_utils import flatten_dict
        
        data = {"options": ["terrasse", "parking"]}
        result = flatten_dict(data)
        assert result == {"options": "terrasse, parking"}


class TestExportCSV:
    """Tests pour l'export CSV."""
    
    def test_export_csv_basic(self, tmp_path):
        """Test export CSV basique."""
        from src.core.export_utils import export_to_csv
        
        data = {
            "A001": {
                "parcelLabel": "A001",
                "typology": "T2",
                "living_space": "41.72"
            },
            "B002": {
                "parcelLabel": "B002",
                "typology": "T3",
                "living_space": "65.50"
            }
        }
        
        output_path = tmp_path / "test.csv"
        result = export_to_csv(data, str(output_path))
        
        assert output_path.exists()
        content = output_path.read_text()
        assert "lot_id" in content
        assert "A001" in content
        assert "B002" in content
    
    def test_export_csv_with_nested(self, tmp_path):
        """Test export CSV avec donnees imbriquees."""
        from src.core.export_utils import export_to_csv
        
        data = {
            "A001": {
                "parcelLabel": "A001",
                "surfaceDetail": {"terrasse": 7.5}
            }
        }
        
        output_path = tmp_path / "test_nested.csv"
        result = export_to_csv(data, str(output_path))
        
        content = output_path.read_text()
        assert "surfaceDetail_terrasse" in content
        assert "7.5" in content


class TestExportExcel:
    """Tests pour l'export Excel."""
    
    def test_export_excel_basic(self, tmp_path):
        """Test export Excel basique."""
        pytest.importorskip("openpyxl")
        
        from src.core.export_utils import export_to_excel
        
        data = {
            "A001": {
                "parcelLabel": "A001",
                "typology": "T2"
            }
        }
        
        output_path = tmp_path / "test.xlsx"
        result = export_to_excel(data, str(output_path))
        
        assert output_path.exists()
    
    def test_export_multi_sheet(self, tmp_path):
        """Test export multi-feuilles."""
        pytest.importorskip("openpyxl")
        
        from src.core.export_utils import export_multi_sheet
        
        data = {
            "A001": {"parcelLabel": "A001", "typology": "T2"},
            "B002": {"parcelLabel": "B002", "typology": "T3"}
        }
        
        output_path = tmp_path / "test_multi.xlsx"
        result = export_multi_sheet(data, str(output_path))
        
        assert output_path.exists()


class TestAutoExport:
    """Tests pour l'export automatique selon format."""
    
    def test_auto_detect_csv(self, tmp_path):
        """Test detection automatique CSV."""
        from src.core.export_utils import detect_export_format
        
        assert detect_export_format("file.csv") == "csv"
        assert detect_export_format("file.CSV") == "csv"
    
    def test_auto_detect_excel(self, tmp_path):
        """Test detection automatique Excel."""
        from src.core.export_utils import detect_export_format
        
        assert detect_export_format("file.xlsx") == "excel"
        assert detect_export_format("file.xls") == "excel"
    
    def test_auto_detect_json(self, tmp_path):
        """Test detection automatique JSON."""
        from src.core.export_utils import detect_export_format
        
        assert detect_export_format("file.json") == "json"
    
    def test_auto_detect_summary(self, tmp_path):
        """Test detection automatique Summary."""
        from src.core.export_utils import detect_export_format
        
        assert detect_export_format("file.md") == "summary"
        assert detect_export_format("file.txt") == "summary"


class TestExportSummary:
    """Tests pour l'export de resume."""
    
    def test_export_summary_md(self, tmp_path):
        """Test export resume Markdown."""
        from src.core.export_utils import export_summary
        
        data = {
            "A001": {
                "parcelLabel": "A001",
                "typology": "T2",
                "floor": "RDC",
                "living_space": "41.72",
                "price": "185000",
                "state": "available"
            }
        }
        
        output_path = tmp_path / "test.md"
        result = export_summary(data, str(output_path), format="md")
        
        content = output_path.read_text()
        assert "# Resume des Lots" in content
        assert "| Lot |" in content
        assert "A001" in content
    
    def test_export_summary_empty(self, tmp_path):
        """Test export resume avec donnees vides."""
        from src.core.export_utils import export_summary
        
        result = export_summary({}, "test.md")
        assert result == ""
