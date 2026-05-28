"""depgraph – Python import dependency analyzer.

Public API re-exported from sub-modules so callers can write::

    from depgraph import Analyzer, DependencyGraph
"""

from depgraph.analyzer import Analyzer, AnalysisResult, Finding
from depgraph.graph import DependencyGraph
from depgraph.scanner import ImportInfo, ModuleFile, Scanner

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
