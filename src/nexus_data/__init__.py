"""Nexus Data (Skills API) client.

Implements a small, safe client for the two-domain Nexus API described in
`repo-improvement/nexus-data-skill.md`.
"""

from nexus_data.client import NexusDataClient, NexusDataConfig
from nexus_data.feeds import nexus_feeds_enabled

__all__ = ["NexusDataClient", "NexusDataConfig", "nexus_feeds_enabled"]
