"""
NetBox API Client

This module provides a client for interacting with NetBox API to retrieve
device configurations and metadata required for zero-touch provisioning.
"""

import logging
import pynetbox
from typing import Optional, Dict, Any
from pynetbox.core.query import RequestError


logger = logging.getLogger(__name__)


class NetBoxClientError(Exception):
    """Base exception for NetBox client errors."""
    pass


class DeviceNotFoundError(NetBoxClientError):
    """Raised when a device is not found in NetBox."""
    pass


class ConfigurationNotFoundError(NetBoxClientError):
    """Raised when device configuration is not available in NetBox."""
    pass


class NetBoxClient:
    """
    Client for interacting with NetBox API.

    This class handles authentication and retrieval of device configurations
    and metadata from NetBox, which serves as the source of truth for
    network infrastructure.

    Attributes:
        url (str): NetBox API URL
        token (str): NetBox API authentication token
        nb (pynetbox.api): NetBox API client instance
    """

    def __init__(self, url: str, token: str, verify_ssl: bool = True):
        """
        Initialize NetBox client.

        Args:
            url: NetBox server URL (e.g., 'https://netbox.example.com')
            token: NetBox API authentication token
            verify_ssl: Whether to verify SSL certificates (default: True)

        Raises:
            NetBoxClientError: If connection to NetBox fails
        """
        self.url = url.rstrip('/')
        self.token = token
        self.verify_ssl = verify_ssl

        logger.info(f"Initializing NetBox client for {self.url}")

        try:
            self.nb = pynetbox.api(
                url=self.url,
                token=self.token
            )
            # Disable SSL verification if requested (for self-signed certs)
            if not verify_ssl:
                import requests
                from requests.packages.urllib3.exceptions import InsecureRequestWarning
                requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
                self.nb.http_session.verify = False

            # Test connection
            logger.debug("Testing NetBox API connection...")
            self.nb.status()
            logger.info("Successfully connected to NetBox API")

        except Exception as e:
            logger.error(f"Failed to initialize NetBox client: {e}")
            raise NetBoxClientError(f"Failed to connect to NetBox: {e}")

    def get_device(self, device_name: str) -> Any:
        """
        Retrieve device object from NetBox.

        Args:
            device_name: Name of the device to retrieve

        Returns:
            Device object from NetBox

        Raises:
            DeviceNotFoundError: If device is not found
            NetBoxClientError: If API request fails
        """
        logger.info(f"Retrieving device '{device_name}' from NetBox")

        try:
            device = self.nb.dcim.devices.get(name=device_name)

            if not device:
                logger.error(f"Device '{device_name}' not found in NetBox")
                raise DeviceNotFoundError(
                    f"Device '{device_name}' not found in NetBox"
                )

            logger.info(f"Found device: {device.name} (ID: {device.id})")
            # Handle both NetBox v3 (device_role) and v4 (role) attribute names
            role = getattr(device, 'role', None) or getattr(device, 'device_role', None)
            logger.debug(f"Device details - Role: {role}, "
                        f"Site: {device.site}, Status: {device.status}")

            return device

        except DeviceNotFoundError:
            raise
        except RequestError as e:
            logger.error(f"NetBox API request error: {e}")
            raise NetBoxClientError(f"API request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error retrieving device: {e}")
            raise NetBoxClientError(f"Failed to retrieve device: {e}")

    def get_device_config(self, device_name: str) -> str:
        """
        Retrieve configuration for a device from NetBox.

        This method retrieves the device's configuration from NetBox's
        config context or custom field, depending on how configurations
        are stored in your NetBox instance.

        Args:
            device_name: Name of the device

        Returns:
            Device configuration as string

        Raises:
            DeviceNotFoundError: If device is not found
            ConfigurationNotFoundError: If configuration is not available
            NetBoxClientError: If API request fails
        """
        logger.info(f"Retrieving configuration for device '{device_name}'")

        device = self.get_device(device_name)

        # Try to get configuration from config context first
        config = None

        # Option 1: Configuration stored in config context
        if hasattr(device, 'config_context') and device.config_context:
            if 'startup_config' in device.config_context:
                config = device.config_context['startup_config']
                logger.info(f"Retrieved config from config_context for {device_name}")
            elif 'configuration' in device.config_context:
                config = device.config_context['configuration']
                logger.info(f"Retrieved config from config_context for {device_name}")

        # Option 2: Configuration stored in custom field
        if not config and hasattr(device, 'custom_fields'):
            if device.custom_fields.get('startup_config'):
                config = device.custom_fields['startup_config']
                logger.info(f"Retrieved config from custom_fields for {device_name}")
            elif device.custom_fields.get('configuration'):
                config = device.custom_fields['configuration']
                logger.info(f"Retrieved config from custom_fields for {device_name}")

        # Option 3: Try to get from local context
        if not config:
            try:
                local_context = device.local_context_data
                if local_context and 'configuration' in local_context:
                    config = local_context['configuration']
                    logger.info(f"Retrieved config from local_context_data for {device_name}")
            except AttributeError:
                pass

        if not config:
            logger.error(f"No configuration found for device '{device_name}'")
            raise ConfigurationNotFoundError(
                f"No configuration available for device '{device_name}'. "
                f"Configuration should be stored in config_context, custom_fields, "
                f"or local_context_data with key 'startup_config' or 'configuration'"
            )

        # Validate configuration is not empty
        if not config.strip():
            raise ConfigurationNotFoundError(
                f"Configuration for device '{device_name}' is empty"
            )

        logger.info(f"Successfully retrieved configuration for {device_name} "
                   f"({len(config)} characters)")
        logger.debug(f"Config preview: {config[:200]}...")

        return config

    def get_device_serial(self, device_name: str) -> str:
        """
        Retrieve serial number for a device from NetBox.

        The serial number is used to verify we're provisioning the correct
        physical device before applying configuration.

        Args:
            device_name: Name of the device

        Returns:
            Device serial number

        Raises:
            DeviceNotFoundError: If device is not found
            NetBoxClientError: If serial number is not available
        """
        logger.info(f"Retrieving serial number for device '{device_name}'")

        device = self.get_device(device_name)

        if not device.serial:
            logger.error(f"Serial number not found for device '{device_name}'")
            raise NetBoxClientError(
                f"Serial number not available for device '{device_name}' in NetBox. "
                f"This is required for device verification."
            )

        serial = device.serial.strip()
        logger.info(f"Serial number for {device_name}: {serial}")

        return serial

    def get_device_metadata(self, device_name: str) -> Dict[str, Any]:
        """
        Retrieve comprehensive metadata for a device.

        Args:
            device_name: Name of the device

        Returns:
            Dictionary containing device metadata

        Raises:
            DeviceNotFoundError: If device is not found
        """
        logger.info(f"Retrieving metadata for device '{device_name}'")

        device = self.get_device(device_name)

        # Handle both NetBox v3 (device_role) and v4 (role) attribute names
        role = getattr(device, 'role', None) or getattr(device, 'device_role', None)

        metadata = {
            'name': device.name,
            'id': device.id,
            'serial': device.serial,
            'device_type': str(device.device_type) if device.device_type else None,
            'device_role': str(role) if role else None,
            'site': str(device.site) if device.site else None,
            'status': str(device.status) if device.status else None,
            'platform': str(device.platform) if device.platform else None,
            'primary_ip': str(device.primary_ip) if device.primary_ip else None,
        }

        logger.debug(f"Device metadata: {metadata}")

        return metadata
