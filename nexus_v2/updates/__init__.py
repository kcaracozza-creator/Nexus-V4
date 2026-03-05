"""NEXUS Update System - LAN Auto-Update via Zultan"""
from .update_client import check_and_update, get_local_version, VERSION

__all__ = ['check_and_update', 'get_local_version', 'VERSION']
