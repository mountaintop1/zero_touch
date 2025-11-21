"""
SSH Connection Management

This module provides SSH connection managers for interacting with jump hosts,
terminal servers, and network devices through console connections.
"""

import logging
import time
import re
from typing import Optional, Tuple
import paramiko
from paramiko.ssh_exception import (
    SSHException,
    AuthenticationException,
    NoValidConnectionsError
)


logger = logging.getLogger(__name__)


class SSHError(Exception):
    """Base exception for SSH-related errors."""
    pass


class ConnectionError(SSHError):
    """Raised when SSH connection fails."""
    pass


class CommandExecutionError(SSHError):
    """Raised when command execution fails."""
    pass


class SSHManager:
    """
    Manages SSH connections to remote hosts.

    This class handles SSH connections to jump hosts and provides methods
    for executing commands and managing files on remote systems.

    Attributes:
        hostname (str): Target host IP or hostname
        username (str): SSH username
        password (str): SSH password (optional if using key)
        port (int): SSH port (default: 22)
        timeout (int): Connection timeout in seconds
        client (paramiko.SSHClient): SSH client instance
    """

    def __init__(
        self,
        hostname: str,
        username: str,
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
        port: int = 22,
        timeout: int = 30
    ):
        """
        Initialize SSH manager.

        Args:
            hostname: Target host IP or hostname
            username: SSH username
            password: SSH password (optional)
            key_filename: Path to SSH private key (optional)
            port: SSH port (default: 22)
            timeout: Connection timeout in seconds (default: 30)
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.port = port
        self.timeout = timeout
        self.client: Optional[paramiko.SSHClient] = None
        self._connected = False

    def connect(self, retries: int = 3, retry_delay: int = 5) -> None:
        """
        Establish SSH connection with retry logic.

        Args:
            retries: Number of connection attempts (default: 3)
            retry_delay: Delay between retries in seconds (default: 5)

        Raises:
            ConnectionError: If connection fails after all retries
        """
        logger.info(f"Connecting to {self.hostname}:{self.port} as {self.username}")

        for attempt in range(1, retries + 1):
            try:
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                connect_kwargs = {
                    'hostname': self.hostname,
                    'port': self.port,
                    'username': self.username,
                    'timeout': self.timeout,
                    'look_for_keys': False,
                    'allow_agent': False,
                }

                if self.password:
                    connect_kwargs['password'] = self.password
                if self.key_filename:
                    connect_kwargs['key_filename'] = self.key_filename

                self.client.connect(**connect_kwargs)
                self._connected = True

                logger.info(f"Successfully connected to {self.hostname}")
                return

            except AuthenticationException as e:
                logger.error(f"Authentication failed for {self.hostname}: {e}")
                raise ConnectionError(f"Authentication failed: {e}")

            except NoValidConnectionsError as e:
                logger.warning(f"Connection attempt {attempt}/{retries} failed: {e}")
                if attempt < retries:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    raise ConnectionError(f"Failed to connect after {retries} attempts: {e}")

            except SSHException as e:
                logger.error(f"SSH error connecting to {self.hostname}: {e}")
                raise ConnectionError(f"SSH error: {e}")

            except Exception as e:
                logger.error(f"Unexpected error connecting to {self.hostname}: {e}")
                raise ConnectionError(f"Connection failed: {e}")

    def execute_command(
        self,
        command: str,
        timeout: int = 60,
        get_pty: bool = False
    ) -> Tuple[str, str, int]:
        """
        Execute command on remote host.

        Args:
            command: Command to execute
            timeout: Command timeout in seconds (default: 60)
            get_pty: Request pseudo-terminal (default: False)

        Returns:
            Tuple of (stdout, stderr, exit_code)

        Raises:
            CommandExecutionError: If command execution fails
        """
        if not self._connected or not self.client:
            raise CommandExecutionError("Not connected. Call connect() first.")

        logger.debug(f"Executing command on {self.hostname}: {command}")

        try:
            stdin, stdout, stderr = self.client.exec_command(
                command,
                timeout=timeout,
                get_pty=get_pty
            )

            # Read output
            stdout_output = stdout.read().decode('utf-8', errors='ignore')
            stderr_output = stderr.read().decode('utf-8', errors='ignore')
            exit_code = stdout.channel.recv_exit_status()

            logger.debug(f"Command exit code: {exit_code}")
            if stdout_output:
                logger.debug(f"STDOUT: {stdout_output[:500]}")
            if stderr_output:
                logger.debug(f"STDERR: {stderr_output[:500]}")

            return stdout_output, stderr_output, exit_code

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise CommandExecutionError(f"Failed to execute command: {e}")

    def create_remote_file(self, remote_path: str, content: str) -> None:
        """
        Create a file on the remote host with specified content.

        Args:
            remote_path: Path where file should be created
            content: File content

        Raises:
            CommandExecutionError: If file creation fails
        """
        logger.info(f"Creating file on {self.hostname}: {remote_path}")

        try:
            sftp = self.client.open_sftp()

            # Write content to remote file
            with sftp.file(remote_path, 'w') as remote_file:
                remote_file.write(content)

            sftp.close()

            logger.info(f"Successfully created {remote_path} ({len(content)} bytes)")

        except Exception as e:
            logger.error(f"Failed to create remote file: {e}")
            raise CommandExecutionError(f"File creation failed: {e}")

    def close(self) -> None:
        """Close SSH connection."""
        if self.client:
            logger.info(f"Closing connection to {self.hostname}")
            self.client.close()
            self._connected = False

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class ConsoleManager:
    """
    Manages console access to network devices via terminal server.

    This class handles connections to terminal servers running pmshell
    and provides methods for executing commands on network devices
    through console connections.

    Attributes:
        hostname (str): Terminal server IP or hostname
        username (str): SSH username
        password (str): SSH password
        port (int): SSH port
        timeout (int): Connection timeout
        client (paramiko.SSHClient): SSH client instance
        channel: Interactive SSH channel for console session
    """

    def __init__(
        self,
        hostname: str,
        username: str,
        password: str,
        port: int = 22,
        timeout: int = 30
    ):
        """
        Initialize console manager.

        Args:
            hostname: Terminal server IP or hostname
            username: SSH username
            password: SSH password
            port: SSH port (default: 22)
            timeout: Connection timeout in seconds (default: 30)
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.client: Optional[paramiko.SSHClient] = None
        self.channel = None
        self._connected = False

    def connect(self, retries: int = 3, retry_delay: int = 5) -> None:
        """
        Connect to terminal server.

        Args:
            retries: Number of connection attempts (default: 3)
            retry_delay: Delay between retries in seconds (default: 5)

        Raises:
            ConnectionError: If connection fails
        """
        logger.info(f"Connecting to terminal server {self.hostname}")

        for attempt in range(1, retries + 1):
            try:
                self.client = paramiko.SSHClient()
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                self.client.connect(
                    hostname=self.hostname,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout,
                    look_for_keys=False,
                    allow_agent=False,
                )

                self._connected = True
                logger.info(f"Connected to terminal server {self.hostname}")
                return

            except Exception as e:
                logger.warning(f"Connection attempt {attempt}/{retries} failed: {e}")
                if attempt < retries:
                    time.sleep(retry_delay)
                else:
                    raise ConnectionError(
                        f"Failed to connect to terminal server after {retries} attempts: {e}"
                    )

    def connect_to_console(self, console_port: int) -> None:
        """
        Connect to device console via pmshell.

        Args:
            console_port: Console port number for the device

        Raises:
            CommandExecutionError: If console connection fails
        """
        if not self._connected or not self.client:
            raise CommandExecutionError("Not connected to terminal server")

        logger.info(f"Connecting to console port {console_port} via pmshell")

        try:
            # Start interactive shell
            self.channel = self.client.invoke_shell()
            self.channel.settimeout(self.timeout)

            # Wait for initial prompt
            time.sleep(2)
            self._read_channel()

            # Execute pmshell
            logger.debug("Executing pmshell command")
            self.channel.send('pmshell\n')
            time.sleep(2)
            output = self._read_channel()

            # Check if we got the console number prompt
            if 'Select' not in output and 'console' not in output.lower():
                logger.warning(f"Unexpected pmshell output: {output}")

            # Send console port number
            logger.debug(f"Selecting console port {console_port}")
            self.channel.send(f'{console_port}\n')
            time.sleep(3)
            output = self._read_channel()

            logger.info(f"Successfully connected to console port {console_port}")
            logger.debug(f"Console connection output: {output[:200]}")

        except Exception as e:
            logger.error(f"Failed to connect to console: {e}")
            raise CommandExecutionError(f"Console connection failed: {e}")

    def execute_device_command(
        self,
        command: str,
        wait_time: int = 5,
        expect: Optional[str] = None,
        timeout: int = 120,
        handle_pagination: bool = True,
        auto_confirm: bool = False
    ) -> str:
        """
        Execute command on device console.

        Args:
            command: Command to execute
            wait_time: Time to wait after command (seconds)
            expect: Expected string in output (optional)
            timeout: Command timeout in seconds
            handle_pagination: Automatically handle --More-- prompts (default: True)
            auto_confirm: Automatically confirm prompts with Enter (default: False)

        Returns:
            Command output

        Raises:
            CommandExecutionError: If command execution fails
        """
        if not self.channel:
            raise CommandExecutionError("Console channel not established")

        logger.debug(f"Executing device command: {command}")

        try:
            # Clear channel buffer
            self._read_channel()

            # Send command
            self.channel.send(f'{command}\n')

            # Wait for output
            start_time = time.time()
            output = ''
            pagination_count = 0
            max_pagination = 50  # Prevent infinite loops
            confirmation_sent = False

            while True:
                time.sleep(1)
                chunk = self._read_channel()
                output += chunk

                # Handle pagination prompts
                if handle_pagination and pagination_count < max_pagination:
                    if '--More--' in chunk or '-- More --' in chunk:
                        logger.debug("Detected pagination prompt, sending space")
                        self.channel.send(' ')
                        pagination_count += 1
                        # Reset timer when handling pagination
                        start_time = time.time()
                        continue

                # Handle confirmation prompts (e.g., "Destination filename [...]?")
                if auto_confirm and not confirmation_sent:
                    # Look for common confirmation patterns
                    confirmation_patterns = [
                        r'Destination filename \[.*?\]\?',
                        r'\[confirm\]',
                        r'\(y/n\)',
                        r'\[yes/no\]',
                    ]
                    for pattern in confirmation_patterns:
                        if re.search(pattern, chunk, re.IGNORECASE):
                            logger.debug(f"Detected confirmation prompt: {pattern}, sending Enter")
                            self.channel.send('\n')
                            confirmation_sent = True
                            start_time = time.time()
                            break

                # Check for expected string
                if expect and expect in output:
                    logger.debug(f"Found expected string: {expect}")
                    break

                # Check timeout
                if time.time() - start_time > timeout:
                    logger.warning(f"Command timeout after {timeout} seconds")
                    break

                # If no expect string, wait for specified time
                if not expect and time.time() - start_time > wait_time:
                    # Check if we're still receiving data
                    if chunk:
                        # Keep waiting if data is still coming
                        start_time = time.time()
                        continue
                    break

            if pagination_count > 0:
                logger.debug(f"Handled {pagination_count} pagination prompts")
            if confirmation_sent:
                logger.debug("Sent confirmation response")

            logger.debug(f"Command output ({len(output)} chars): {output[:300]}")
            return output

        except Exception as e:
            logger.error(f"Failed to execute device command: {e}")
            raise CommandExecutionError(f"Device command execution failed: {e}")

    def _read_channel(self) -> str:
        """
        Read available data from channel.

        Returns:
            Data read from channel
        """
        output = ''
        try:
            while self.channel.recv_ready():
                chunk = self.channel.recv(4096)
                output += chunk.decode('utf-8', errors='ignore')
        except Exception as e:
            logger.debug(f"Error reading channel: {e}")

        return output

    def send_control_c(self) -> None:
        """Send Ctrl+C to console."""
        if self.channel:
            logger.debug("Sending Ctrl+C to console")
            self.channel.send('\x03')
            time.sleep(1)

    def parse_show_version(self, output: str) -> Optional[str]:
        """
        Parse 'show version' output to extract serial number.

        Args:
            output: Output from 'show version' command

        Returns:
            Serial number if found, None otherwise
        """
        logger.debug("Parsing show version output for serial number")

        # Clean up pagination artifacts
        cleaned_output = output.replace('--More--', '').replace('-- More --', '')
        # Remove backspace characters and ANSI escape codes
        cleaned_output = re.sub(r'\x08+', '', cleaned_output)
        cleaned_output = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', cleaned_output)

        # Common patterns for serial number in show version output
        patterns = [
            # Cisco IOS XE / Catalyst switches
            r'Model [Nn]umber\s*:?\s*\S+\s+[Ss]ystem [Ss]erial [Nn]umber\s*:?\s*(\S+)',
            r'[Ss]ystem [Ss]erial [Nn]umber\s*:?\s*(\S+)',
            # Standard patterns
            r'[Ss]erial\s+[Nn]umber\s*:?\s+(\S+)',
            r'[Pp]rocessor [Bb]oard ID\s+(\S+)',
            r'Chassis Serial Number\s*:?\s+(\S+)',
            # Alternative patterns
            r'Serial [Nn]um\s*:?\s*(\S+)',
            r'SN\s*:?\s*(\S+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, cleaned_output, re.IGNORECASE)
            if match:
                serial = match.group(1).strip()
                # Filter out placeholder values
                if serial and serial.lower() not in ['none', 'n/a', 'unknown', '']:
                    logger.info(f"Extracted serial number using pattern '{pattern}': {serial}")
                    return serial

        logger.warning("Could not extract serial number from show version output")
        logger.debug(f"Show version output (first 1000 chars): {cleaned_output[:1000]}")

        return None

    def close(self) -> None:
        """Close console and SSH connections."""
        if self.channel:
            logger.debug("Closing console channel")
            self.channel.close()

        if self.client:
            logger.info(f"Closing connection to terminal server {self.hostname}")
            self.client.close()
            self._connected = False

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
