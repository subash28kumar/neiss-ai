"""neissai: AI-assisted national injury estimates from NEISS emergency department narratives.

Quick start::

    import neissai
    df = neissai.read_neiss("data", years="2019-2025")      # CPSC annual files
    labeled = neissai.label_devices(df)                       # rules + text classifier
    labeled = neissai.add_outcomes(labeled)
    est = neissai.national_estimates(labeled, by=["year", "device"],
                                     where=labeled["device"].isin(neissai.DEVICES))
"""
from .classifier import EbikeMopedClassifier
from . import circumstances
from .devices import DEVICES, add_outcomes, label_devices, micromobility
from .estimate import national_estimates, proportion, shares, total
from .io import download, parse_years, read_neiss, read_neiss_file, standardize

__version__ = "1.4.0"

__all__ = ["DEVICES", "circumstances", "EbikeMopedClassifier", "add_outcomes", "download", "label_devices",
           "micromobility", "national_estimates", "parse_years", "proportion", "read_neiss",
           "read_neiss_file", "shares", "standardize", "total", "__version__"]
