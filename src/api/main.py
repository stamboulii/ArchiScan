"""
FastAPI REST API - Integration Externe
====================================

API REST pour integrer ArchiExtract dans d'autres applications.

Endpoints:
    POST /extract - Extraire les donnees d'une image/PDF
    POST /extract/batch - Traiter plusieurs fichiers
    GET /health - Health check
    GET /stats - Statistiques de l'API

Usage:
    uvicorn src.api.main:app --host 0.0.0.0 --port 8000
"""

import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

from ..core.config import (
    PROJECT_ROOT,
    TEMP_DIR,
    ensure_directories,
)
from ..core.pdf_utils import PDFProcessor, detect_file_format, get_page_count
from ..extractors.hybrid_extractor import HybridExtractor
from ..core.parcel import normalize_parcel_data, validate_parcel_data

logger = logging.getLogger(__name__)


# =============================================================================
# Models Pydantic
# =============================================================================

class ExtractionRequest(BaseModel):
    """Request model pour l'extraction."""
    method: str = Field(default="auto", description="Methode: auto, tesseract, claude, super")
    validate: bool = Field(default=True, description="Valider les donnees extraites")


class ParcelDataResponse(BaseModel):
    """Response model pour les donnees d'un lot."""
    parcelLabel: Optional[str] = None
    parcelTypeId: str = "appartment"
    parcelTypeLabel: str = "appartment"
    typology: Optional[str] = None
    floor: Optional[str] = None
    orientation: Optional[str] = None
    price: str = "N.C"
    living_space: Optional[str] = None
    surfaceDetail: dict = field(default_factory=dict)
    option: dict = field(default_factory=dict)
    tva: str = ""
    pinel: str = ""
    state: str = "available"
    confidence: float = 0.0


class ExtractionResponse(BaseModel):
    """Response model pour une extraction."""
    success: bool
    file_name: str
    file_type: str
    page: Optional[int] = None
    data: Optional[ParcelDataResponse] = None
    validation: Optional[dict] = None
    error: Optional[str] = None
    processing_time_ms: float = 0.0


class BatchExtractionResponse(BaseModel):
    """Response model pour une extraction batch."""
    total_files: int
    successful: int
    failed: int
    results: List[ExtractionResponse]
    processing_time_ms: float = 0.0


class HealthResponse(BaseModel):
    """Response model pour le health check."""
    status: str
    version: str
    extractor_available: bool


# =============================================================================
# Application FastAPI
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire du cycle de vie de l'application."""
    # Startup
    ensure_directories()
    logger.info("API ArchiExtract demarree")
    yield
    # Shutdown
    logger.info("API ArchiExtract arrete")


app = FastAPI(
    title="ArchiExtract API",
    description="API REST pour l'extraction de donnees depuis les plans d'architecture",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instance globale de l'extracteur
_extractor: Optional[HybridExtractor] = None
_pdf_processor: Optional[PDFProcessor] = None


def get_extractor() -> HybridExtractor:
    """Recupere (ou cree) l'extracteur hybride."""
    global _extractor
    if _extractor is None:
        _extractor = HybridExtractor()
    return _extractor


def get_pdf_processor() -> PDFProcessor:
    """Recupere (ou cree) le processuer PDF."""
    global _pdf_processor
    if _pdf_processor is None:
        _pdf_processor = PDFProcessor()
    return _pdf_processor


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    extractor = get_extractor()
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        extractor_available=extractor is not None
    )


@app.post("/extract", response_model=ExtractionResponse)
async def extract_single(
    file: UploadFile = File(...),
    method: str = Form(default="auto"),
    validate: bool = Form(default=True),
):
    """
    Extrait les donnees d'une image ou PDF unique.
    
    Args:
        file: Fichier a traiter (image ou PDF)
        method: Methode d'extraction (auto, tesseract, claude, super)
        - method=super retourne le format SuperExtractor directement
        validate: Valider les donnees extraites
        
    Returns:
        Si method=super: format SuperExtractor {"LOT_1": {...}}
        Sinon: ExtractionResponse standard
    """
    import time
    start_time = time.perf_counter()
    
    try:
        # Sauvegarder le fichier temporaire
        temp_path = TEMP_DIR / f"api_{int(time.time())}_{file.filename}"
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        
        content = await file.read()
        with open(temp_path, 'wb') as f:
            f.write(content)
        
        # Detecter le format
        file_type = detect_file_format(str(temp_path))
        
        if file_type == 'pdf':
            # PDF multi-pages: traiter la premiere page
            pdf_processor = get_pdf_processor()
            pages = pdf_processor.convert_pdf_to_images(str(temp_path))
            
            if not pages:
                return ExtractionResponse(
                    success=False,
                    file_name=file.filename,
                    file_type="pdf",
                    error="Impossible d'extraire les pages du PDF",
                    processing_time_ms=(time.perf_counter() - start_time) * 1000
                )
            
            # Traiter la premiere page
            image_path = pages[0].image_path
            page_num = pages[0].page_num
        else:
            # Image simple
            image_path = str(temp_path)
            file_type = "image"
            page_num = None
        
        # Extraction
        extractor = get_extractor()
        
        # Use SuperExtractor if method is 'super'
        if method == "super":
            from ..extractors.super_extractor.super_extractor import SuperExtractor
            super_extractor = SuperExtractor()
            result = super_extractor.extract(str(temp_path))
            # Always return legacy format for SuperExtractor
            result_dict = result.to_legacy_format()
            import json
            return JSONResponse(
                content=result_dict,
                media_type="application/json"
            )
        else:
            if method != "auto":
                from ..core.config import PHASE_TESSERACT, PHASE_CLAUDE
                method_map = {
                    'tesseract': PHASE_TESSERACT,
                    'claude': PHASE_CLAUDE,
                }
                extractor.force_method = method_map.get(method)
            
            result = extractor.extract(image_path)
            
            # Normalisation
            normalized = normalize_parcel_data(result)
        
        # Validation si demandee
        validation = None
        if validate:
            is_valid, errors = validate_parcel_data(normalized)
            validation = {
                'valid': is_valid,
                'errors': errors
            }
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        return ExtractionResponse(
            success=True,
            file_name=file.filename,
            file_type=file_type,
            page=page_num,
            data=ParcelDataResponse(**normalized),
            validation=validation,
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.error(f"Erreur d'extraction: {e}", exc_info=True)
        return ExtractionResponse(
            success=False,
            file_name=file.filename,
            file_type="unknown",
            error=str(e),
            processing_time_ms=(time.perf_counter() - start_time) * 1000
        )


@app.post("/extract/batch", response_model=BatchExtractionResponse)
async def extract_batch(
    files: List[UploadFile] = File(...),
    method: str = Form(default="auto"),
    validate: bool = Form(default=True),
):
    """
    Extrait les donnees de plusieurs fichiers.
    
    Args:
        files: Liste des fichiers a traiter
        method: Methode d'extraction
        validate: Valider les donnees extraites
        
    Returns:
        BatchExtractionResponse avec tous les resultats
    """
    import time
    start_time = time.perf_counter()
    
    results = []
    successful = 0
    failed = 0
    
    for file in files:
        response = await extract_single(
            file=file,
            method=method,
            validate=validate
        )
        
        if response.success:
            successful += 1
        else:
            failed += 1
        
        results.append(response)
    
    processing_time = (time.perf_counter() - start_time) * 1000
    
    return BatchExtractionResponse(
        total_files=len(files),
        successful=successful,
        failed=failed,
        results=results,
        processing_time_ms=processing_time
    )


@app.post("/extract/pdf/{pdf_path:path}")
async def extract_pdf_full(
    pdf_path: str,
    method: str = Query(default="auto"),
    validate: bool = Query(default=True),
):
    """
    Extrait les donnees de toutes les pages d'un PDF.
    Le PDF doit etre accessible via le systeme de fichiers.
    
    Args:
        pdf_path: Chemin vers le PDF (sur le serveur)
        method: Methode d'extraction
        validate: Valider les donnees extraites
        
    Returns:
        Liste des resultats pour chaque page
    """
    import time
    from pathlib import Path
    
    start_time = time.perf_counter()
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise HTTPException(status_code=404, detail="PDF introuvable")
    
    # Compter les pages
    page_count = get_page_count(str(pdf_file))
    if page_count == 0:
        raise HTTPException(status_code=400, detail="Impossible de lire le PDF")
    
    # Traiter toutes les pages
    pdf_processor = get_pdf_processor()
    
    results = []
    successful = 0
    failed = 0
    
    pages = pdf_processor.convert_pdf_to_images(str(pdf_file))
    
    extractor = get_extractor()
    if method != "auto":
        from ..core.config import PHASE_TESSERACT, PHASE_CLAUDE
        method_map = {
            'tesseract': PHASE_TESSERACT,
            'claude': PHASE_CLAUDE,
        }
        extractor.force_method = method_map.get(method)
    
    for page in pages:
        try:
            result = extractor.extract(page.image_path)
            normalized = normalize_parcel_data(result)
            
            if validate:
                is_valid, errors = validate_parcel_data(normalized)
                validation = {'valid': is_valid, 'errors': errors}
            else:
                validation = None
            
            results.append(ExtractionResponse(
                success=True,
                file_name=pdf_file.name,
                file_type="pdf",
                page=page.page_num,
                data=ParcelDataResponse(**normalized),
                validation=validation,
                processing_time_ms=0
            ))
            successful += 1
        except Exception as e:
            results.append(ExtractionResponse(
                success=False,
                file_name=pdf_file.name,
                file_type="pdf",
                page=page.page_num,
                error=str(e)
            ))
            failed += 1
    
    processing_time = (time.perf_counter() - start_time) * 1000
    
    return {
        "pdf_file": str(pdf_file),
        "total_pages": page_count,
        "successful": successful,
        "failed": failed,
        "results": results,
        "processing_time_ms": processing_time
    }


@app.get("/stats")
async def get_stats():
    """Retourne les statistiques de l'extracteur."""
    extractor = get_extractor()
    return {
        "extractor_type": "hybrid",
        "available_methods": ["auto", "tesseract", "claude"],
        "config": {
            "temp_dir": str(TEMP_DIR),
            "project_root": str(PROJECT_ROOT),
        }
    }


# =============================================================================
# Main
# =============================================================================

def run(host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
    """Lance le serveur FastAPI."""
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Lance l'API ArchiExtract")
    parser.add_argument("--host", default="0.0.0.0", help="Adresse d'ecoute")
    parser.add_argument("--port", type=int, default=8000, help="Port")
    parser.add_argument("--debug", action="store_true", help="Mode debug")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    run(args.host, args.port, args.debug)
