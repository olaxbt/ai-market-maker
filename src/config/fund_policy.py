"""Backwards-compatible policy import surface.

New code should import from:
- :mod:`config.policy_types` for :class:`FundPolicy`
- :mod:`config.policy_loader` for :func:`load_fund_policy`
"""

from __future__ import annotations

from .policy_loader import load_fund_policy
from .policy_types import FundPolicy

__all__ = ["FundPolicy", "load_fund_policy"]
