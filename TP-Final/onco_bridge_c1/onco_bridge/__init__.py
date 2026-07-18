"""Componente 1 de OncoBridge AI."""

from .pipeline import ClinicalPipeline
from .component2 import RadiologyAssistant
from .reference_generator import SyntheticReferenceGenerator
from .local_reference_generator import LocalDiffusionReferenceGenerator

__all__ = ["ClinicalPipeline", "RadiologyAssistant", "SyntheticReferenceGenerator", "LocalDiffusionReferenceGenerator"]
