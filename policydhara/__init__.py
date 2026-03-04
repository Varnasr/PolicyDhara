"""
PolicyDhara — Python library for tracking Indian development policies.

Search, filter, classify, and fetch policy data from 300+ Indian government,
regulatory, research, and news sources across 21 sectors.
"""

from policydhara.models import Policy
from policydhara.classifier import PolicyClassifier
from policydhara.store import PolicyStore

__version__ = "0.1.0"
__all__ = ["Policy", "PolicyClassifier", "PolicyStore", "__version__"]
