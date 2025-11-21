# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Zero Touch Provisioning (ZTP) Tool** for network devices. It automates device provisioning by retrieving configurations from NetBox (source of truth), deploying them via FTP, and applying them through console access. The tool verifies device identity by serial number before configuration to prevent misconfiguration.

## Important Documentation

- **[NetBox Rendered Config Guide](docs/NETBOX_RENDERED_CONFIG.md)** - Comprehensive guide on retrieving rendered configurations from NetBox using the API. READ THIS FIRST when troubleshooting NetBox config retrieval issues.

## Development Commands

### Environment Setup

```bash
# Install dependencies using uv (recommended - 10-100x faster than pip)
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Or install as editable package (requires setuptools)
uv pip install setuptools
uv pip install -e .

# Or using traditional pip
pip install -r requirements.txt

# Configure environment
cp .env.template .env
# Edit .env with your NetBox, jump host, terminal server, and FTP credentials
```

### Running the Tool

```bash
# Basic provisioning
uv run zero_touch_provision.py --device-name DEVICE_NAME --console-port PORT

# With debug logging
uv run zero_touch_provision.py --device-name DEVICE_NAME --console-port PORT --log-level DEBUG

# Dry run (validation only - not yet implemented)
uv run zero_touch_provision.py --device-name DEVICE_NAME --console-port PORT --dry-run

# Alternatively, using the installed script entry point
uv run ztp --device-name DEVICE_NAME --console-port PORT
```

### Development Tools

```bash
# Code formatting
uv run black zero_touch_provision.py ztp/

# Type checking
uv run mypy zero_touch_provision.py ztp/

# Linting
uv run flake8 zero_touch_provision.py ztp/
```

## Architecture

### Component Hierarchy

The codebase follows a modular three-tier architecture:

1. **CLI Layer** (`zero_touch_provision.py`)
   - Entry point with argument parsing
   - Environment configuration loading from `.env`
   - Logging setup and colored terminal output
   - Error handling and user feedback

2. **Orchestration Layer** (`ztp/orchestrator.py`)
   - `ProvisioningOrchestrator`: Coordinates the complete workflow
   - Implements a state machine (`ProvisioningState` enum) tracking progress through:
     - INITIALIZED → NETBOX_CONNECTED → CONFIG_RETRIEVED → FTP_FILE_CREATED → CONSOLE_CONNECTED → DEVICE_VERIFIED → CONFIG_COPIED_TO_FLASH → CONFIG_APPLIED → COMPLETED/FAILED
   - Manages error handling, cleanup, and connection lifecycle
   - Each workflow step is isolated in `_step_*` methods for clarity

3. **Integration Layer** (`ztp/` modules)
   - `NetBoxClient`: Retrieves device configs and metadata from NetBox API
   - `SSHManager`: Manages SSH connections to jump host for FTP file creation
   - `ConsoleManager`: Handles terminal server console access and device command execution

### Critical Workflow Details

The provisioning workflow is strictly sequential and cannot skip steps:

1. **NetBox Retrieval**: Fetches configuration from config_context, custom_fields, or local_context_data (in that order). Also retrieves expected serial number for verification.

2. **FTP File Creation**: SSH to jump host, create `{device_name}.txt` in `/srv/ftp` with configuration content using SFTP.

3. **Console Connection**: SSH to terminal server, invoke `pmshell`, select console port number to establish interactive console session. **Enter enable mode**: Automatically detects current prompt and enters privileged EXEC mode using `enable` command. Handles cases with or without enable password.

4. **Device Verification**: Execute `show version`, parse serial number using regex patterns, compare with NetBox serial. **Abort if mismatch** to prevent wrong device configuration.

5. **Config Copy to Flash**: Execute `copy ftp://user:pass@IP//file.txt flash: vrf Mgmt-vrf`. The command includes FTP credentials inline and assumes management VRF. **Automatic confirmation**: The tool detects the "Destination filename [...]?" prompt and automatically sends Enter to accept the default filename.

6. **Config Application**: Execute `copy {filename} running-config`. **Automatic confirmation**: The tool detects the "Destination filename [running-config]?" prompt and automatically sends Enter.

7. **Configuration Verification**: After applying the configuration, the tool performs intelligent verification by:
   - Extracting key configuration elements from the original config (hostname, VLANs, interfaces with descriptions, IP addresses)
   - Executing `show running-config` commands to verify each element exists on the device
   - **Failing the provisioning if ANY element is missing** - this catches cases where the copy command appeared successful but configuration wasn't actually applied (e.g., due to missed confirmation prompts)
   - Example verification: If config contains `hostname test-switch-01`, the tool executes `show running-config | include hostname` and verifies "test-switch-01" appears in the output

### Error Handling Philosophy

- Each layer has custom exceptions: `NetBoxClientError`, `SSHError`, `ProvisioningError`
- Serial number mismatch raises `DeviceVerificationError` and aborts immediately
- Cleanup (`_cleanup()`) removes FTP files on failure
- All connections closed in `finally` block via `_close_connections()`
- Retry logic built into SSH connections (3 attempts with 5-second delays)

### State Management

The `ProvisioningState` enum tracks workflow progress. This is crucial for:
- Determining what cleanup actions are needed on failure
- Providing status to users via `get_status()` method
- Logging and debugging (state transitions are logged)

## Configuration Notes

### Environment Variables (`.env`)

Required variables (see `.env.template` for full list):
- **NetBox**: `NETBOX_URL`, `NETBOX_TOKEN`, `VERIFY_SSL`
- **Jump Host**: `JUMPHOST_IP`, `JUMPHOST_USERNAME`, `JUMPHOST_PASSWORD`, `FTP_DIRECTORY`
- **Terminal Server**: `TERMINAL_SERVER_IP`, `TERMINAL_SERVER_USERNAME`, `TERMINAL_SERVER_PASSWORD`
- **FTP Server**: `FTP_SERVER_IP`, `FTP_USERNAME`, `FTP_PASSWORD` (accessible from devices)
- **Logging**: `LOG_LEVEL`, `LOG_FILE`

**Important**: FTP_SERVER_IP is the IP from the device's perspective (typically in management VRF), not necessarily the jump host IP from the operator's perspective.

### NetBox Configuration Requirements

Devices must have:
1. Configuration stored in one of: `config_context['startup_config']`, `custom_fields['startup_config']`, or `local_context_data['configuration']`
2. Serial number populated (used for device verification)

### Infrastructure Assumptions

- Jump host has FTP service with files in `/srv/ftp`
- Terminal server supports `pmshell` command for console access
- Network devices support: FTP client, management VRF, Cisco IOS-style commands
- Device console output follows common Cisco patterns for serial number extraction

## Device Command Patterns

The tool assumes Cisco IOS-style command syntax:
```
show version                                    # Device verification
copy ftp://user:pass@IP//file.txt flash: vrf Mgmt-vrf  # FTP copy
copy filename running-config                    # Apply config
show running-config | include hostname          # Verification
```

Serial number extraction patterns (in `ConsoleManager.parse_show_version()`):
- `Serial Number: XXX`
- `Processor board ID XXX`
- `System serial number: XXX`
- `Chassis Serial Number: XXX`

## Security Considerations

- **Never commit `.env`** - contains credentials and API tokens
- Credentials are logged in sanitized form (passwords replaced with `****`)
- FTP commands contain plaintext credentials - ensure console logs are secured
- NetBox API token should have minimal required permissions
- SSH key authentication is supported but requires code modification in `ssh_manager.py`
- Set `VERIFY_SSL=false` only for development with self-signed certificates

## Code Conventions

- Full type hints on all functions (enforced by mypy)
- Comprehensive docstrings with Args/Returns/Raises sections
- Logging levels: DEBUG (verbose SSH/API output), INFO (workflow progress), ERROR (failures)
- Paramiko and Netmiko logging suppressed to WARNING level to reduce noise
- Line length: 100 characters (Black configuration)
- Context managers supported for SSHManager and ConsoleManager (with `__enter__`/`__exit__`)

## Extension Points

### Adding SSH Key Authentication

Modify connection setup in `ztp/ssh_manager.py`:
```python
ssh_manager = SSHManager(
    hostname=jumphost_ip,
    username=username,
    key_filename='~/.ssh/ztp_key'  # Instead of password
)
```

### Supporting Non-Cisco Devices

1. Update command patterns in `_step_copy_config_to_flash()` and `_step_apply_configuration()`
2. Modify serial number regex patterns in `ConsoleManager.parse_show_version()`
3. Adjust success/error detection in command output parsing

### Adding Pre-Provisioning Validation

Implement dry-run mode logic in `zero_touch_provision.py:main()`:
- Test NetBox connectivity and device existence
- Verify SSH connectivity to jump host and terminal server
- Check console port accessibility
- Preview configuration without applying
