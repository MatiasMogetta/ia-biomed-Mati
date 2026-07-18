"""Componente 1 de OncoBridge AI."""

from .pipeline import ClinicalPipeline
from .local_reference_generator import LocalDiffusionReferenceGenerator

__all__ = ["ClinicalPipeline", "LocalDiffusionReferenceGenerator"]
