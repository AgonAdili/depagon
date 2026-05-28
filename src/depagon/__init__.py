"""depagon – Python import dependency analyzer.

Public API re-exported from sub-modules so callers can write::

    from depagon import Analyzer, DependencyGraph
"""

from depagon.analyzer import Analyzer, AnalysisResult, Finding
from depagon.graph import DependencyGraph
from depagon.scanner import ImportInfo, ModuleFile, Scanner

__version__ = "0.1.0"
__all__ = [
    "__version__",
    "Scanner",
    "ImportInfo",
    "ModuleFile",
    "DependencyGraph",
    "Analyzer",
    "AnalysisResult",
    "Finding",
]
