"""
Zero Touch Provisioning (ZTP) Package

This package provides automated network device provisioning capabilities,
integrating NetBox as source of truth, FTP-based configuration delivery,
and console-based device configuration.

Modules:
    netbox_client: NetBox API client for retrieving device configurations
    ssh_manager: SSH connection management for jump hosts and terminal servers
    orchestrator: Main provisioning workflow orchestration
"""

__version__ = "1.0.0"
__author__ = "Network Automation Team"

from .netbox_client import NetBoxClient
from .ssh_manager import SSHManager, ConsoleManager
from .orchestrator import ProvisioningOrchestrator

__all__ = [
    "NetBoxClient",
    "SSHManager",
    "ConsoleManager",
    "ProvisioningOrchestrator",
]
