"""
Provisioning Orchestrator

This module coordinates the complete zero-touch provisioning workflow,
integrating NetBox, SSH, and console management to automate device deployment.
"""

import logging
import time
import os
import re
from typing import Optional, Dict, Any
from enum import Enum

from .netbox_client import (
    NetBoxClient,
    NetBoxClientError,
    DeviceNotFoundError,
    ConfigurationNotFoundError
)
from .ssh_manager import (
    SSHManager,
    ConsoleManager,
    SSHError,
    ConnectionError,
    CommandExecutionError
)


logger = logging.getLogger(__name__)


class ProvisioningState(Enum):
    """Provisioning workflow states."""
    INITIALIZED = "initialized"
    NETBOX_CONNECTED = "netbox_connected"
    CONFIG_RETRIEVED = "config_retrieved"
    FTP_FILE_CREATED = "ftp_file_created"
    CONSOLE_CONNECTED = "console_connected"
    DEVICE_VERIFIED = "device_verified"
    CONFIG_COPIED_TO_FLASH = "config_copied_to_flash"
    CONFIG_APPLIED = "config_applied"
    COMPLETED = "completed"
    FAILED = "failed"


class ProvisioningError(Exception):
    """Base exception for provisioning errors."""
    pass


class DeviceVerificationError(ProvisioningError):
    """Raised when device verification fails."""
    pass


class ConfigurationDeploymentError(ProvisioningError):
    """Raised when configuration deployment fails."""
    pass


class ProvisioningOrchestrator:
    """
    Orchestrates the complete zero-touch provisioning workflow.

    This class manages the end-to-end provisioning process, including:
    - Retrieving configuration from NetBox
    - Creating configuration file on FTP server
    - Connecting to device via console
    - Verifying device identity
    - Deploying and applying configuration

    Attributes:
        device_name (str): Name of device to provision
        console_port (int): Console port number on terminal server
        state (ProvisioningState): Current provisioning state
        netbox_client (NetBoxClient): NetBox API client
        ssh_manager (SSHManager): SSH manager for jump host
        console_manager (ConsoleManager): Console manager for device
    """

    def __init__(
        self,
        device_name: str,
        console_port: int,
        netbox_url: str,
        netbox_token: str,
        jumphost_ip: str,
        jumphost_username: str,
        jumphost_password: str,
        terminal_server_ip: str,
        terminal_server_username: str,
        terminal_server_password: str,
        ftp_server_ip: str,
        ftp_username: str,
        ftp_password: str,
        ftp_directory: str = "/srv/ftp",
        verify_ssl: bool = True
    ):
        """
        Initialize provisioning orchestrator.

        Args:
            device_name: Name of device to provision
            console_port: Console port number
            netbox_url: NetBox server URL
            netbox_token: NetBox API token
            jumphost_ip: Jump host IP address
            jumphost_username: Jump host username
            jumphost_password: Jump host password
            terminal_server_ip: Terminal server IP
            terminal_server_username: Terminal server username
            terminal_server_password: Terminal server password
            ftp_server_ip: FTP server IP
            ftp_username: FTP username
            ftp_password: FTP password
            ftp_directory: FTP directory path (default: /srv/ftp)
            verify_ssl: Verify SSL certificates (default: True)
        """
        self.device_name = device_name
        self.console_port = console_port
        self.state = ProvisioningState.INITIALIZED

        # Configuration parameters
        self.netbox_url = netbox_url
        self.netbox_token = netbox_token
        self.jumphost_ip = jumphost_ip
        self.jumphost_username = jumphost_username
        self.jumphost_password = jumphost_password
        self.terminal_server_ip = terminal_server_ip
        self.terminal_server_username = terminal_server_username
        self.terminal_server_password = terminal_server_password
        self.ftp_server_ip = ftp_server_ip
        self.ftp_username = ftp_username
        self.ftp_password = ftp_password
        self.ftp_directory = ftp_directory
        self.verify_ssl = verify_ssl

        # Client instances
        self.netbox_client: Optional[NetBoxClient] = None
        self.ssh_manager: Optional[SSHManager] = None
        self.console_manager: Optional[ConsoleManager] = None

        # Provisioning data
        self.device_config: Optional[str] = None
        self.expected_serial: Optional[str] = None
        self.actual_serial: Optional[str] = None
        self.config_filename: Optional[str] = None

        logger.info(f"Initialized provisioning orchestrator for device: {device_name}")
        logger.info(f"Console port: {console_port}")

    def provision_device(self) -> bool:
        """
        Execute complete provisioning workflow.

        This method orchestrates all provisioning steps in sequence,
        handling errors and cleanup appropriately.

        Returns:
            True if provisioning completed successfully, False otherwise

        Raises:
            ProvisioningError: If critical error occurs during provisioning
        """
        logger.info("=" * 80)
        logger.info(f"STARTING ZERO-TOUCH PROVISIONING FOR: {self.device_name}")
        logger.info("=" * 80)

        try:
            # Step 1: Connect to NetBox and retrieve configuration
            self._step_retrieve_netbox_config()

            # Step 2: Create configuration file on FTP server
            self._step_create_ftp_file()

            # Step 3: Connect to device console
            self._step_connect_to_console()

            # Step 4: Verify device identity
            self._step_verify_device()

            # Step 5: Copy configuration to device flash
            self._step_copy_config_to_flash()

            # Step 6: Apply configuration to running-config
            self._step_apply_configuration()

            # Mark as completed
            self.state = ProvisioningState.COMPLETED
            logger.info("=" * 80)
            logger.info(f"PROVISIONING COMPLETED SUCCESSFULLY FOR: {self.device_name}")
            logger.info("=" * 80)

            return True

        except Exception as e:
            self.state = ProvisioningState.FAILED
            logger.error("=" * 80)
            logger.error(f"PROVISIONING FAILED FOR: {self.device_name}")
            logger.error(f"Error: {e}")
            logger.error("=" * 80)

            # Attempt cleanup
            self._cleanup()

            raise ProvisioningError(f"Provisioning failed: {e}")

        finally:
            # Always close connections
            self._close_connections()

    def _step_retrieve_netbox_config(self) -> None:
        """Step 1: Retrieve device configuration from NetBox."""
        logger.info("-" * 80)
        logger.info("STEP 1: Retrieving configuration from NetBox")
        logger.info("-" * 80)

        try:
            # Initialize NetBox client
            self.netbox_client = NetBoxClient(
                url=self.netbox_url,
                token=self.netbox_token,
                verify_ssl=self.verify_ssl
            )
            self.state = ProvisioningState.NETBOX_CONNECTED

            # Retrieve device configuration
            logger.info(f"Fetching configuration for device: {self.device_name}")
            self.device_config = self.netbox_client.get_device_config(self.device_name)

            # Retrieve expected serial number
            logger.info(f"Fetching serial number for device: {self.device_name}")
            self.expected_serial = self.netbox_client.get_device_serial(self.device_name)

            self.state = ProvisioningState.CONFIG_RETRIEVED
            logger.info(f"Successfully retrieved configuration ({len(self.device_config)} bytes)")
            logger.info(f"Expected serial number: {self.expected_serial}")

        except (DeviceNotFoundError, ConfigurationNotFoundError) as e:
            logger.error(f"NetBox error: {e}")
            raise ProvisioningError(f"Failed to retrieve device information: {e}")
        except NetBoxClientError as e:
            logger.error(f"NetBox client error: {e}")
            raise ProvisioningError(f"NetBox connection failed: {e}")

    def _step_create_ftp_file(self) -> None:
        """Step 2: Create configuration file on FTP server."""
        logger.info("-" * 80)
        logger.info("STEP 2: Creating configuration file on FTP server")
        logger.info("-" * 80)

        try:
            # Generate configuration filename
            self.config_filename = f"{self.device_name}.txt"
            remote_path = os.path.join(self.ftp_directory, self.config_filename)

            logger.info(f"Target file: {remote_path}")
            logger.info(f"Connecting to jump host: {self.jumphost_ip}")

            # Connect to jump host
            self.ssh_manager = SSHManager(
                hostname=self.jumphost_ip,
                username=self.jumphost_username,
                password=self.jumphost_password
            )
            self.ssh_manager.connect()

            # Create configuration file
            logger.info(f"Creating configuration file: {self.config_filename}")
            self.ssh_manager.create_remote_file(remote_path, self.device_config)

            # Verify file was created
            stdout, stderr, exit_code = self.ssh_manager.execute_command(
                f"ls -lh {remote_path}"
            )

            if exit_code == 0:
                logger.info(f"File created successfully: {stdout.strip()}")
                self.state = ProvisioningState.FTP_FILE_CREATED
            else:
                raise CommandExecutionError(f"File verification failed: {stderr}")

        except SSHError as e:
            logger.error(f"SSH error creating FTP file: {e}")
            raise ProvisioningError(f"Failed to create FTP file: {e}")

    def _step_connect_to_console(self) -> None:
        """Step 3: Connect to device console via terminal server."""
        logger.info("-" * 80)
        logger.info("STEP 3: Connecting to device console")
        logger.info("-" * 80)

        try:
            logger.info(f"Connecting to terminal server: {self.terminal_server_ip}")

            # Initialize console manager
            self.console_manager = ConsoleManager(
                hostname=self.terminal_server_ip,
                username=self.terminal_server_username,
                password=self.terminal_server_password
            )

            # Connect to terminal server
            self.console_manager.connect()

            # Connect to device console
            logger.info(f"Accessing console port: {self.console_port}")
            self.console_manager.connect_to_console(self.console_port)

            self.state = ProvisioningState.CONSOLE_CONNECTED
            logger.info("Successfully connected to device console")

            # Send enter to get prompt
            time.sleep(2)
            self.console_manager.channel.send('\n')
            time.sleep(1)

            # Enter enable mode
            logger.info("Entering enable mode")
            self._enter_enable_mode()

        except (ConnectionError, CommandExecutionError) as e:
            logger.error(f"Console connection error: {e}")
            raise ProvisioningError(f"Failed to connect to console: {e}")

    def _enter_enable_mode(self) -> None:
        """
        Enter enable (privileged EXEC) mode on the device.

        Detects current prompt and enters enable mode if needed.
        Handles enable password if required.

        Raises:
            ProvisioningError: If unable to enter enable mode
        """
        try:
            # Send carriage return to get current prompt
            self.console_manager.channel.send('\r\n')
            time.sleep(1)
            output = self.console_manager._read_channel()

            logger.debug(f"Current prompt: {output[-50:]}")

            # Check if already in enable mode (prompt ends with #)
            if '#' in output:
                logger.info("Already in enable mode")
                return

            # Try to enter enable mode
            logger.info("Attempting to enter enable mode with 'enable' command")
            self.console_manager.channel.send('enable\r\n')
            time.sleep(2)
            output = self.console_manager._read_channel()

            # Check if password is required
            if 'password:' in output.lower() or 'Password:' in output:
                logger.warning("Enable password required but not configured")
                logger.warning("Attempting to proceed without password (press Enter)")
                self.console_manager.channel.send('\r\n')
                time.sleep(2)
                output = self.console_manager._read_channel()

            # Verify we're in enable mode now
            self.console_manager.channel.send('\r\n')
            time.sleep(1)
            output = self.console_manager._read_channel()

            if '#' not in output:
                logger.error(f"Failed to enter enable mode. Prompt: {output[-100:]}")
                raise ProvisioningError(
                    "Unable to enter enable mode. Device may require enable password. "
                    "Please configure device with no enable password or update tool to support it."
                )

            logger.info("Successfully entered enable mode")

        except Exception as e:
            logger.error(f"Error entering enable mode: {e}")
            raise ProvisioningError(f"Failed to enter enable mode: {e}")

    def _step_verify_device(self) -> None:
        """Step 4: Verify device identity by comparing serial numbers."""
        logger.info("-" * 80)
        logger.info("STEP 4: Verifying device identity")
        logger.info("-" * 80)

        try:
            # Disable pagination to get full output without --More-- prompts
            logger.info("Disabling terminal pagination")
            self.console_manager.execute_device_command(
                command='terminal length 0',
                wait_time=2
            )

            logger.info("Executing 'show version' command")

            # Execute show version
            output = self.console_manager.execute_device_command(
                command='show version',
                wait_time=10
            )

            # Parse serial number from output
            self.actual_serial = self.console_manager.parse_show_version(output)

            if not self.actual_serial:
                logger.error("Could not extract serial number from device output")
                logger.debug(f"Show version output: {output}")
                raise DeviceVerificationError(
                    "Failed to extract serial number from 'show version' output"
                )

            # Compare serial numbers
            logger.info(f"Expected serial: {self.expected_serial}")
            logger.info(f"Actual serial:   {self.actual_serial}")

            if self.expected_serial.lower() != self.actual_serial.lower():
                logger.error("SERIAL NUMBER MISMATCH!")
                logger.error(f"Expected: {self.expected_serial}")
                logger.error(f"Got:      {self.actual_serial}")
                raise DeviceVerificationError(
                    f"Serial number mismatch! Expected '{self.expected_serial}', "
                    f"but device reports '{self.actual_serial}'. "
                    f"Aborting to prevent misconfiguration."
                )

            self.state = ProvisioningState.DEVICE_VERIFIED
            logger.info("Device identity verified successfully!")

        except DeviceVerificationError:
            raise
        except Exception as e:
            logger.error(f"Device verification error: {e}")
            raise ProvisioningError(f"Failed to verify device: {e}")

    def _step_copy_config_to_flash(self) -> None:
        """Step 5: Copy configuration from FTP to device flash."""
        logger.info("-" * 80)
        logger.info("STEP 5: Copying configuration to device flash")
        logger.info("-" * 80)

        try:
            # Construct FTP URL
            ftp_url = (
                f"ftp://{self.ftp_username}:{self.ftp_password}"
                f"@{self.ftp_server_ip}//{self.config_filename}"
            )

            # Sanitized URL for logging (hide password)
            ftp_url_log = (
                f"ftp://{self.ftp_username}:****"
                f"@{self.ftp_server_ip}//{self.config_filename}"
            )

            copy_command = f"copy {ftp_url} flash: vrf Mgmt-vrf"
            copy_command_log = f"copy {ftp_url_log} flash: vrf Mgmt-vrf"

            logger.info(f"Executing: {copy_command_log}")

            # Execute copy command with auto-confirmation for filename prompt
            output = self.console_manager.execute_device_command(
                command=copy_command,
                wait_time=30,
                timeout=300,  # 5 minutes for large configs
                auto_confirm=True  # Automatically confirm destination filename prompt
            )

            # Check for successful copy
            if 'bytes copied' in output.lower() or 'ok' in output.lower():
                logger.info("Configuration successfully copied to flash")
                self.state = ProvisioningState.CONFIG_COPIED_TO_FLASH
            elif 'error' in output.lower() or 'fail' in output.lower():
                logger.error(f"Copy failed: {output}")
                raise ConfigurationDeploymentError(
                    f"Failed to copy configuration to flash: {output}"
                )
            else:
                logger.warning("Copy command completed but success unclear")
                logger.debug(f"Copy output: {output}")

        except ConfigurationDeploymentError:
            raise
        except Exception as e:
            logger.error(f"Error copying configuration to flash: {e}")
            raise ProvisioningError(f"Failed to copy config to flash: {e}")

    def _step_apply_configuration(self) -> None:
        """Step 6: Apply configuration to running-config."""
        logger.info("-" * 80)
        logger.info("STEP 6: Applying configuration to device")
        logger.info("-" * 80)

        try:
            apply_command = f"copy {self.config_filename} running-config"
            logger.info(f"Executing: {apply_command}")

            # Execute apply command with auto-confirmation for any prompts
            output = self.console_manager.execute_device_command(
                command=apply_command,
                wait_time=60,
                timeout=600,  # 10 minutes for config application
                auto_confirm=True  # Automatically confirm any prompts
            )

            # Check for errors in output
            if 'error' in output.lower() and 'no error' not in output.lower():
                logger.error(f"Configuration application error: {output}")
                raise ConfigurationDeploymentError(
                    f"Errors occurred while applying configuration: {output}"
                )

            # Check for success indicators
            if 'bytes copied' in output.lower() or any(
                indicator in output.lower()
                for indicator in ['ok', 'success', 'completed']
            ):
                logger.info("Configuration successfully applied!")
                self.state = ProvisioningState.CONFIG_APPLIED
            else:
                logger.warning("Configuration apply completed but status unclear")
                logger.debug(f"Apply output: {output}")

            # Wait for device to process configuration
            logger.info("Waiting for device to process configuration...")
            time.sleep(10)

            # Verify configuration was applied by extracting key config elements
            logger.info("Verifying configuration application...")
            self._verify_configuration_applied()

        except ConfigurationDeploymentError:
            raise
        except Exception as e:
            logger.error(f"Error applying configuration: {e}")
            raise ProvisioningError(f"Failed to apply configuration: {e}")

    def _verify_configuration_applied(self) -> None:
        """
        Verify that configuration was actually applied to the device.

        This method extracts key configuration elements from the original config
        and verifies they exist in the running configuration on the device.

        Raises:
            ConfigurationDeploymentError: If verification fails
        """
        logger.info("Performing configuration verification...")

        # Extract verification markers from the original configuration
        verification_items = self._extract_verification_markers()

        if not verification_items:
            logger.warning(
                "No verification markers could be extracted from configuration. "
                "Skipping detailed verification."
            )
            return

        logger.info(f"Extracted {len(verification_items)} verification markers")

        # Check each verification item
        failed_items = []
        for item_type, item_value in verification_items:
            logger.debug(f"Checking {item_type}: {item_value}")

            # Build verification command based on item type
            if item_type == 'hostname':
                verify_cmd = 'show running-config | include hostname'
            elif item_type == 'interface':
                verify_cmd = f'show running-config interface {item_value} | include description'
            elif item_type == 'vlan':
                verify_cmd = f'show running-config | include vlan {item_value}'
            elif item_type == 'ip_address':
                verify_cmd = f'show running-config | include {item_value}'
            else:
                verify_cmd = f'show running-config | include {item_value}'

            try:
                output = self.console_manager.execute_device_command(
                    command=verify_cmd,
                    wait_time=5,
                    timeout=30
                )

                # Check if the expected value appears in output
                if item_value.lower() not in output.lower():
                    logger.error(f"Verification failed for {item_type}: {item_value}")
                    failed_items.append((item_type, item_value))
                else:
                    logger.debug(f"✓ Verified {item_type}: {item_value}")

            except Exception as e:
                logger.warning(f"Could not verify {item_type} {item_value}: {e}")
                # Don't fail on verification command errors, just log them

        # If any verification failed, raise error
        if failed_items:
            failed_list = '\n'.join([f"  - {t}: {v}" for t, v in failed_items])
            logger.error(f"Configuration verification FAILED. Missing items:\n{failed_list}")
            raise ConfigurationDeploymentError(
                f"Configuration verification failed. {len(failed_items)} items not found "
                f"in running-config. This indicates the configuration was not properly applied. "
                f"Missing items:\n{failed_list}"
            )

        logger.info("✓ Configuration verification PASSED - all markers found in running-config")

    def _extract_verification_markers(self) -> list:
        """
        Extract verification markers from the device configuration.

        Returns a list of tuples: (marker_type, marker_value)

        Returns:
            List of (type, value) tuples to verify
        """
        if not self.device_config:
            return []

        markers = []

        # Extract hostname
        hostname_match = re.search(r'^hostname\s+(\S+)', self.device_config, re.MULTILINE)
        if hostname_match:
            markers.append(('hostname', hostname_match.group(1)))

        # Extract first 3 interface configurations with descriptions
        interface_matches = re.findall(
            r'^interface\s+(\S+).*?(?:description\s+(.+?))?(?=^interface|\Z)',
            self.device_config,
            re.MULTILINE | re.DOTALL
        )
        for intf, desc in interface_matches[:3]:
            if desc and desc.strip():
                markers.append(('interface', intf))

        # Extract VLANs
        vlan_matches = re.findall(r'^vlan\s+(\d+)', self.device_config, re.MULTILINE)
        for vlan in vlan_matches[:3]:  # Check first 3 VLANs
            markers.append(('vlan', vlan))

        # Extract IP addresses (IPv4)
        ip_matches = re.findall(
            r'ip address\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)',
            self.device_config
        )
        for ip, mask in ip_matches[:2]:  # Check first 2 IP addresses
            markers.append(('ip_address', ip))

        logger.debug(f"Extracted verification markers: {markers}")
        return markers

    def _cleanup(self) -> None:
        """Cleanup resources on failure."""
        logger.info("Performing cleanup operations...")

        try:
            # Remove FTP file if it was created
            if (
                self.state.value >= ProvisioningState.FTP_FILE_CREATED.value
                and self.ssh_manager
                and self.config_filename
            ):
                logger.info(f"Removing FTP file: {self.config_filename}")
                remote_path = os.path.join(self.ftp_directory, self.config_filename)
                try:
                    self.ssh_manager.execute_command(f"rm -f {remote_path}")
                    logger.info("FTP file removed")
                except Exception as e:
                    logger.warning(f"Failed to remove FTP file: {e}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def _close_connections(self) -> None:
        """Close all active connections."""
        logger.info("Closing connections...")

        if self.console_manager:
            try:
                self.console_manager.close()
            except Exception as e:
                logger.warning(f"Error closing console connection: {e}")

        if self.ssh_manager:
            try:
                self.ssh_manager.close()
            except Exception as e:
                logger.warning(f"Error closing SSH connection: {e}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current provisioning status.

        Returns:
            Dictionary containing current status information
        """
        return {
            'device_name': self.device_name,
            'console_port': self.console_port,
            'state': self.state.value,
            'expected_serial': self.expected_serial,
            'actual_serial': self.actual_serial,
            'config_filename': self.config_filename,
        }
