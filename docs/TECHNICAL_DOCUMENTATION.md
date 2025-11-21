# Zero Touch Provisioning (ZTP) Tool - Technical Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [System Requirements](#system-requirements)
4. [Installation and Setup](#installation-and-setup)
5. [Configuration](#configuration)
6. [Workflow Details](#workflow-details)
7. [Module Documentation](#module-documentation)
8. [Error Handling](#error-handling)
9. [Security Considerations](#security-considerations)
10. [Troubleshooting](#troubleshooting)
11. [API Reference](#api-reference)
12. [Extension Guide](#extension-guide)

---

## Overview

### Purpose

The Zero Touch Provisioning (ZTP) Tool is an automated network device provisioning system designed to eliminate manual configuration tasks and reduce human error in network deployments. The tool retrieves device configurations from NetBox (Network Source of Truth), deploys them via FTP, and applies them through console access with comprehensive verification.

### Key Features

- **Automated Configuration Retrieval**: Fetches device configurations from NetBox API
- **Device Identity Verification**: Validates device serial numbers before configuration to prevent misconfiguration
- **FTP-Based Configuration Deployment**: Transfers configuration files via FTP server
- **Console-Based Configuration Application**: Applies configurations through terminal server console access
- **Intelligent Prompt Handling**: Automatically detects and responds to interactive prompts
- **Configuration Verification**: Validates that configuration was actually applied using marker extraction
- **Comprehensive Logging**: Detailed logging at multiple levels (DEBUG, INFO, ERROR)
- **Error Recovery**: Automatic cleanup on failure with retry logic for connections

### Design Philosophy

1. **Safety First**: Serial number verification prevents wrong-device configurations
2. **Fail Fast**: Early detection and clear error messages
3. **Idempotent Operations**: Safe to retry on failure
4. **Observable**: Comprehensive logging for troubleshooting
5. **Modular**: Clear separation of concerns across modules

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLI Entry Point                              │
│                (zero_touch_provision.py)                        │
│  - Argument parsing                                             │
│  - Environment configuration                                    │
│  - Logging setup                                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Provisioning Orchestrator                          │
│                (ztp/orchestrator.py)                            │
│  - Workflow coordination                                        │
│  - State management                                             │
│  - Error handling and cleanup                                   │
└────────────┬────────────────┬──────────────────┬────────────────┘
             │                │                  │
             ▼                ▼                  ▼
┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  NetBox Client  │ │   SSH Manager    │ │ Console Manager  │
│(netbox_client)  │ │ (ssh_manager)    │ │ (ssh_manager)    │
├─────────────────┤ ├──────────────────┤ ├──────────────────┤
│ - Get device    │ │ - SSH connection │ │ - Terminal       │
│   config        │ │ - SFTP file      │ │   server         │
│ - Get serial    │ │   transfer       │ │   connection     │
│   number        │ │ - Command exec   │ │ - Console access │
│ - Get metadata  │ │ - Retry logic    │ │ - Device         │
│                 │ │                  │ │   commands       │
└─────────────────┘ └──────────────────┘ └──────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   NetBox API    │ │   Jump Host      │ │ Terminal Server  │
│  (pynetbox)     │ │  (Paramiko SSH)  │ │  (Paramiko SSH)  │
└─────────────────┘ └──────────────────┘ └──────────────────┘
```

### Component Layers

#### 1. CLI Layer (`zero_touch_provision.py`)

**Responsibilities:**
- Parse command-line arguments
- Load environment variables from `.env` file
- Configure logging (level, format, output destinations)
- Initialize and invoke orchestrator
- Handle top-level exceptions
- Display user-friendly status messages

**Key Functions:**
- `setup_logging()`: Configures Python logging with colored output
- `load_environment()`: Loads and validates environment variables
- `main()`: Entry point that orchestrates the provisioning workflow

#### 2. Orchestration Layer (`ztp/orchestrator.py`)

**Responsibilities:**
- Coordinate the complete provisioning workflow
- Manage state transitions through `ProvisioningState` enum
- Handle errors and perform cleanup
- Manage connection lifecycle (open/close)
- Execute verification logic

**State Machine:**
```
INITIALIZED
    ↓
NETBOX_CONNECTED
    ↓
CONFIG_RETRIEVED
    ↓
FTP_FILE_CREATED
    ↓
CONSOLE_CONNECTED
    ↓
DEVICE_VERIFIED
    ↓
CONFIG_COPIED_TO_FLASH
    ↓
CONFIG_APPLIED
    ↓
COMPLETED
```

If any step fails, state transitions to `FAILED` and cleanup is triggered.

#### 3. Integration Layer

##### NetBox Client (`ztp/netbox_client.py`)

**Responsibilities:**
- Interface with NetBox REST API via pynetbox library
- Retrieve device configurations from multiple sources
- Retrieve device serial numbers for verification
- Retrieve device metadata

**Configuration Retrieval Priority:**
1. Rendered configuration (from config templates)
2. Config context with key `startup_config` or `configuration`
3. Custom fields with key `startup_config` or `configuration`
4. Local context data with key `configuration`

##### SSH Manager (`ztp/ssh_manager.py`)

**Components:**

1. **SSHManager Class**
   - Establishes SSH connections to jump host
   - Executes shell commands with timeout and retry logic
   - Transfers files via SFTP
   - Supports both password and key-based authentication

2. **ConsoleManager Class**
   - Connects to terminal server via SSH
   - Invokes `pmshell` for console access
   - Executes device commands through console
   - Handles interactive prompts automatically
   - Parses device output (e.g., serial numbers from `show version`)

---

## System Requirements

### Infrastructure Requirements

1. **NetBox Server**
   - Version: 3.x or 4.x
   - API access enabled
   - Device configurations stored in config context, custom fields, or templates
   - Device serial numbers populated

2. **Jump Host**
   - SSH access (port 22)
   - FTP service running (vsftpd, ProFTPD, etc.)
   - FTP directory accessible (default: `/srv/ftp`)
   - Network connectivity to devices' management interface

3. **Terminal Server**
   - SSH access (port 22)
   - `pmshell` command available for console access
   - Console ports configured and accessible

4. **Network Devices**
   - Console connectivity via terminal server
   - FTP client capability
   - Management VRF configured (default: `Mgmt-vrf`)
   - Cisco IOS-style command syntax support
   - Sufficient flash storage for configuration files

### Software Requirements

**Python Environment:**
- Python 3.8 or higher
- pip or uv package manager

**Python Dependencies:**
```
pynetbox>=7.0.0
paramiko>=3.0.0
python-dotenv>=1.0.0
```

**Optional Development Tools:**
```
black>=23.0.0      # Code formatting
mypy>=1.0.0        # Type checking
flake8>=6.0.0      # Linting
```

### Network Requirements

- Operator workstation → NetBox API (HTTPS, port 443 or custom)
- Operator workstation → Jump host (SSH, port 22)
- Operator workstation → Terminal server (SSH, port 22)
- Jump host → Network devices (FTP, port 21 + data ports)
- Devices must have IP connectivity to FTP server via management VRF

---

## Installation and Setup

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd zero_touch_provision
```

### Step 2: Create Virtual Environment

**Using uv (recommended - 10-100x faster):**
```bash
uv venv
source .venv/bin/activate  # On Linux/Mac
# or
.venv\Scripts\activate     # On Windows

uv pip install -r requirements.txt
```

**Using traditional pip:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Configure Environment

```bash
cp .env.template .env
```

Edit `.env` file with your credentials and settings (see Configuration section).

### Step 4: Verify Installation

```bash
# Test imports
python -c "import pynetbox, paramiko; print('Dependencies OK')"

# Test environment loading
python -c "from dotenv import load_dotenv; load_dotenv(); print('Environment OK')"

# Run help
uv run zero_touch_provision.py --help
```

### Step 5: Test Connection (Dry Run)

```bash
# Test NetBox connectivity
python -c "
from ztp.netbox_client import NetBoxClient
import os
from dotenv import load_dotenv
load_dotenv()
client = NetBoxClient(os.getenv('NETBOX_URL'), os.getenv('NETBOX_TOKEN'))
print('NetBox connection successful')
"
```

---

## Configuration

### Environment Variables

All configuration is managed through the `.env` file. Required variables:

#### NetBox Configuration

```bash
# NetBox API Configuration
NETBOX_URL=https://netbox.example.com
NETBOX_TOKEN=your_api_token_here
VERIFY_SSL=true  # Set to false for self-signed certificates
```

**Notes:**
- API token needs read access to DCIM devices
- Token permissions: `dcim.view_device`, `dcim.view_configcontext`

#### Jump Host Configuration

```bash
# Jump Host / FTP Server SSH Access
JUMPHOST_IP=10.10.10.100
JUMPHOST_USERNAME=ftpuser
JUMPHOST_PASSWORD=secure_password
# JUMPHOST_KEY_FILE=/path/to/key  # Alternative to password

# FTP Configuration
FTP_DIRECTORY=/srv/ftp  # Directory where config files are stored
```

**Notes:**
- User must have write permissions to `FTP_DIRECTORY`
- FTP service must be configured and running

#### Terminal Server Configuration

```bash
# Terminal Server SSH Access
TERMINAL_SERVER_IP=10.10.10.200
TERMINAL_SERVER_USERNAME=console_user
TERMINAL_SERVER_PASSWORD=console_password
```

**Notes:**
- User must have access to `pmshell` command
- Console ports must be accessible

#### FTP Server Configuration (Device Perspective)

```bash
# FTP Server (as accessible from devices)
FTP_SERVER_IP=192.168.100.50  # Must be reachable from device management VRF
FTP_USERNAME=ftpnet
FTP_PASSWORD=ftppass
```

**Important:** `FTP_SERVER_IP` is the IP address from the **device's perspective**, typically in the management VRF. This may differ from `JUMPHOST_IP` if NAT or routing is involved.

#### Logging Configuration

```bash
# Logging Configuration
LOG_LEVEL=INFO     # DEBUG, INFO, WARNING, ERROR
LOG_FILE=ztp.log   # Log file path (optional)
```

**Log Levels:**
- `DEBUG`: Verbose output including SSH command details, API responses
- `INFO`: Workflow progress, major steps
- `WARNING`: Non-fatal issues, unclear statuses
- `ERROR`: Failures, exceptions

### Configuration File Hierarchy

1. `.env` file (highest priority)
2. Environment variables from shell
3. Default values in code

---

## Workflow Details

### Complete Provisioning Workflow

#### Step 1: NetBox Configuration Retrieval

**Objective:** Fetch device configuration and serial number from NetBox

**Process:**
1. Initialize NetBox API client with URL and token
2. Query device by name: `GET /api/dcim/devices/?name={device_name}`
3. Retrieve configuration using priority order:
   - Try rendered config: `POST /api/dcim/devices/{id}/render-config/`
   - Try config context: `device.config_context['startup_config']`
   - Try custom fields: `device.custom_fields['startup_config']`
   - Try local context: `device.local_context_data['configuration']`
4. Retrieve serial number: `device.serial`

**Success Criteria:**
- Configuration string retrieved (non-empty)
- Serial number retrieved (non-empty)

**State Transition:**
- `INITIALIZED` → `NETBOX_CONNECTED` → `CONFIG_RETRIEVED`

**Error Handling:**
- `DeviceNotFoundError`: Device doesn't exist in NetBox
- `ConfigurationNotFoundError`: No configuration found in any source
- `NetBoxClientError`: API connection or permission issues

---

#### Step 2: FTP File Creation

**Objective:** Upload configuration file to FTP server accessible by devices

**Process:**
1. Generate filename: `{device_name}.txt`
2. Construct full path: `{FTP_DIRECTORY}/{device_name}.txt`
3. Connect to jump host via SSH (3 retries, 5-second delays)
4. Open SFTP session
5. Write configuration content to remote file
6. Verify file creation: `ls -lh {filepath}`

**Success Criteria:**
- SSH connection established
- File created successfully
- File size matches configuration length

**State Transition:**
- `CONFIG_RETRIEVED` → `FTP_FILE_CREATED`

**Error Handling:**
- `ConnectionError`: SSH connection failed after retries
- `CommandExecutionError`: File creation or verification failed
- Cleanup: File removed on subsequent failure

---

#### Step 3: Console Connection and Enable Mode

**Objective:** Establish console session and enter privileged mode

**Process:**
1. Connect to terminal server via SSH
2. Invoke interactive shell
3. Execute `pmshell` command
4. Wait for console port selection prompt
5. Send console port number
6. Wait for device prompt
7. Send carriage returns to get current prompt
8. Detect prompt type:
   - `>` = User EXEC mode
   - `#` = Privileged EXEC mode
9. If in user mode, execute `enable` command
10. Handle enable password prompt (if present)
11. Verify `#` prompt appears

**Success Criteria:**
- Terminal server connection established
- Console session established on specified port
- Device responds to carriage returns
- Device in enable mode (`#` prompt)

**State Transition:**
- `FTP_FILE_CREATED` → `CONSOLE_CONNECTED`

**Enable Mode Logic:**
```
Current prompt?
    ├─ Contains '#' → Already in enable mode ✓
    └─ Contains '>' → User mode
           ├─ Send 'enable\r\n'
           ├─ Wait for prompt
           ├─ If 'Password:' appears
           │     └─ Send '\r\n' (blank password)
           └─ Verify '#' appears → Success ✓
```

**Error Handling:**
- `ConnectionError`: Terminal server SSH failed
- `CommandExecutionError`: pmshell failed or console unavailable
- `ProvisioningError`: Unable to enter enable mode

---

#### Step 4: Device Verification

**Objective:** Verify correct device by comparing serial numbers

**Process:**
1. Disable terminal pagination: `terminal length 0`
2. Execute `show version` command
3. Parse serial number from output using regex patterns:
   ```
   - Serial Number: XXX
   - Processor board ID XXX
   - System serial number: XXX
   - Chassis Serial Number: XXX
   ```
4. Clean output (remove ANSI codes, backspaces, pagination artifacts)
5. Compare with expected serial from NetBox (case-insensitive)

**Success Criteria:**
- Serial number extracted from device output
- Serial number matches NetBox record

**State Transition:**
- `CONSOLE_CONNECTED` → `DEVICE_VERIFIED`

**Serial Number Extraction:**

Regex patterns (in priority order):
```python
[
    r'Model [Nn]umber\s*:?\s*\S+\s+[Ss]ystem [Ss]erial [Nn]umber\s*:?\s*(\S+)',
    r'[Ss]ystem [Ss]erial [Nn]umber\s*:?\s*(\S+)',
    r'[Ss]erial\s+[Nn]umber\s*:?\s+(\S+)',
    r'[Pp]rocessor [Bb]oard ID\s+(\S+)',
    r'Chassis Serial Number\s*:?\s+(\S+)',
    r'Serial [Nn]um\s*:?\s*(\S+)',
    r'SN\s*:?\s*(\S+)',
]
```

Filters out placeholder values: `none`, `n/a`, `unknown`, empty strings

**Error Handling:**
- `DeviceVerificationError`: Serial mismatch (CRITICAL - workflow aborts)
- `CommandExecutionError`: `show version` command failed
- Provisioning aborts if verification fails (prevents wrong-device configuration)

**Critical Safety Feature:**
This step prevents catastrophic misconfiguration. If serial numbers don't match, provisioning terminates immediately.

---

#### Step 5: Copy Configuration to Flash

**Objective:** Transfer configuration file from FTP to device flash storage

**Process:**
1. Construct FTP URL: `ftp://{username}:{password}@{server_ip}//{filename}`
2. Build copy command: `copy {ftp_url} flash: vrf Mgmt-vrf`
3. Send carriage returns to ensure clean prompt
4. Clear console buffer
5. Send command (character-by-character if >100 chars)
6. Detect confirmation prompt: `Destination filename [...]?`
7. Automatically send Enter to accept default filename
8. Wait for copy completion (timeout: 5 minutes)
9. Parse output for success indicators

**Command Execution Details:**

**Prompt Handling:**
```
Device output: "Destination filename [os-device-01.txt]?"
Detection: Regex pattern r'Destination filename \[.*?\]\?'
Response: Send '\n'
Result: Copy proceeds with default filename
```

**Long Command Handling (>100 characters):**
```python
for char in command:
    channel.send(char)
    time.sleep(0.01)  # 10ms between chars
```

This prevents console buffer corruption with long FTP URLs.

**Success Indicators:**
- Output contains: `bytes copied` (case-insensitive)
- Output contains: `ok` (case-insensitive)

**Failure Indicators:**
- Output contains: `error` or `fail`

**State Transition:**
- `DEVICE_VERIFIED` → `CONFIG_COPIED_TO_FLASH`

**Error Handling:**
- `ConfigurationDeploymentError`: Copy failed (FTP unreachable, auth failure, insufficient space)
- Timeout: File too large or network issues

---

#### Step 6: Apply Configuration

**Objective:** Copy configuration from flash to running-config

**Process:**
1. Build command: `copy {filename} running-config`
2. Send carriage returns for clean prompt
3. Execute command with auto-confirmation enabled
4. Detect confirmation prompt: `Destination filename [running-config]?`
5. Automatically send Enter
6. Wait for application (timeout: 10 minutes)
7. Send two carriage returns after completion
8. Clear console buffer
9. Wait 10 seconds for device to process changes

**Success Indicators:**
- Output contains: `bytes copied`
- Output contains: `ok`, `success`, or `completed`

**Failure Indicators:**
- Output contains: `error` (but not `no error`)

**State Transition:**
- `CONFIG_COPIED_TO_FLASH` → `CONFIG_APPLIED`

**Error Handling:**
- `ConfigurationDeploymentError`: Application failed (syntax errors, conflicts)

---

#### Step 7: Configuration Verification

**Objective:** Verify configuration was actually applied to running-config

**Process:**

**Phase 1: Extract Verification Markers**

Parse original configuration to extract:
- **Hostname**: First occurrence of `hostname {name}`
- **VLANs**: First 3 VLANs matching `vlan {number}`
- **Interfaces**: First 3 interfaces with descriptions
- **IP Addresses**: First 2 IP addresses matching `ip address {ip} {mask}`

**Example Extraction:**
```
Configuration:
    hostname test-sw-01
    vlan 10
    vlan 20
    interface GigabitEthernet1/0/1
     description Uplink
    ip address 192.168.1.1 255.255.255.0

Markers Extracted:
    [('hostname', 'test-sw-01'),
     ('vlan', '10'),
     ('vlan', '20'),
     ('interface', 'GigabitEthernet1/0/1'),
     ('ip_address', '192.168.1.1')]
```

**Phase 2: Verify Each Marker**

For each marker, build and execute verification command:

| Marker Type | Verification Command |
|-------------|---------------------|
| hostname | `show running-config \| include hostname` |
| vlan | `show running-config \| include vlan {number}` |
| interface | `show running-config interface {name} \| include description` |
| ip_address | `show running-config \| include {ip}` |

Check if marker value appears in command output (case-insensitive).

**Success Criteria:**
- ALL markers found in running-config

**Failure Criteria:**
- ANY marker missing from running-config

**State Transition:**
- `CONFIG_APPLIED` → `COMPLETED` (if verification passes)
- `CONFIG_APPLIED` → `FAILED` (if verification fails)

**Why This Works:**

Traditional verification only checked if the device responded to commands. This new verification ensures configuration was **actually applied** by checking for specific config elements.

**Scenario Example:**
```
Without verification:
  copy command returns "OK" → Provisioning succeeds ✓
  But configuration not applied due to missed prompt
  Device remains unconfigured ✗

With verification:
  copy command returns "OK"
  Verification checks: hostname 'test-sw-01' in running-config?
  Not found → Provisioning fails ✗
  Clear error: "Configuration not properly applied"
```

**Error Handling:**
- `ConfigurationDeploymentError`: Verification failed (config not applied)
- Warning logged if verification command fails (doesn't fail provisioning)

---

### Cleanup and Error Recovery

#### Cleanup Process

Triggered when provisioning fails at any step:

1. **Remove FTP File** (if created):
   ```bash
   rm -f {FTP_DIRECTORY}/{device_name}.txt
   ```
   - Only executed if state >= `FTP_FILE_CREATED`
   - Prevents stale configuration files on FTP server

2. **Close Connections**:
   - Close console channel
   - Close terminal server SSH connection
   - Close jump host SSH connection
   - All closures logged, errors suppressed

#### Error Categories

**Recoverable Errors:**
- SSH connection failures (retried 3 times)
- NetBox API timeouts (can retry entire workflow)

**Non-Recoverable Errors:**
- Serial number mismatch (workflow aborts immediately)
- Device not found in NetBox
- Configuration not found in NetBox

**User Action Required:**
- Enable password required on device
- FTP credentials incorrect
- Insufficient flash space

---

## Module Documentation

### `zero_touch_provision.py`

Main entry point script.

#### Functions

**`setup_logging(log_level: str, log_file: Optional[str]) -> None`**

Configures Python logging with colored console output.

**Parameters:**
- `log_level`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `log_file`: Optional log file path

**Behavior:**
- Suppresses Paramiko and Netmiko debug logs (sets to WARNING)
- Adds colored formatter for console output
- Adds file handler if log_file specified

**`load_environment() -> Dict[str, str]`**

Loads and validates environment variables from `.env` file.

**Returns:**
- Dictionary of configuration parameters

**Raises:**
- `ValueError`: If required environment variables are missing

**`main() -> None`**

Main execution function.

**Workflow:**
1. Parse command-line arguments
2. Load environment variables
3. Setup logging
4. Display configuration summary
5. Initialize ProvisioningOrchestrator
6. Execute provisioning
7. Display results

---

### `ztp/orchestrator.py`

Provisioning workflow coordinator.

#### Classes

**`ProvisioningState(Enum)`**

Enumeration of workflow states.

**Values:**
```python
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
```

**`ProvisioningOrchestrator`**

Main orchestrator class.

**Initialization:**
```python
orchestrator = ProvisioningOrchestrator(
    device_name="switch-01",
    console_port=5001,
    netbox_url="https://netbox.example.com",
    netbox_token="token",
    jumphost_ip="10.10.10.100",
    jumphost_username="user",
    jumphost_password="pass",
    terminal_server_ip="10.10.10.200",
    terminal_server_username="console",
    terminal_server_password="pass",
    ftp_server_ip="192.168.1.100",
    ftp_username="ftp",
    ftp_password="ftp",
    ftp_directory="/srv/ftp",
    verify_ssl=True
)
```

**Methods:**

**`provision_device() -> bool`**

Executes complete provisioning workflow.

**Returns:**
- `True` if successful, `False` otherwise

**Raises:**
- `ProvisioningError`: On workflow failure

**`get_status() -> Dict[str, Any]`**

Returns current provisioning status.

**Returns:**
```python
{
    'device_name': str,
    'console_port': int,
    'state': str,
    'expected_serial': str,
    'actual_serial': str,
    'config_filename': str
}
```

**Private Methods:**

- `_step_retrieve_netbox_config()`: Step 1 implementation
- `_step_create_ftp_file()`: Step 2 implementation
- `_step_connect_to_console()`: Step 3 implementation
- `_enter_enable_mode()`: Enable mode handler
- `_step_verify_device()`: Step 4 implementation
- `_step_copy_config_to_flash()`: Step 5 implementation
- `_step_apply_configuration()`: Step 6 implementation
- `_verify_configuration_applied()`: Step 7 implementation
- `_extract_verification_markers()`: Extract config markers
- `_cleanup()`: Cleanup handler
- `_close_connections()`: Connection cleanup

---

### `ztp/netbox_client.py`

NetBox API client.

#### Classes

**`NetBoxClient`**

Interface to NetBox API.

**Methods:**

**`__init__(url: str, token: str, verify_ssl: bool = True)`**

Initialize NetBox client.

**Parameters:**
- `url`: NetBox server URL
- `token`: API authentication token
- `verify_ssl`: Whether to verify SSL certificates

**`get_device(device_name: str) -> Any`**

Retrieve device object from NetBox.

**Returns:**
- pynetbox Device object

**Raises:**
- `DeviceNotFoundError`: Device not found
- `NetBoxClientError`: API error

**`get_device_config(device_name: str) -> str`**

Retrieve device configuration.

**Priority Order:**
1. Rendered config template
2. Config context `startup_config` or `configuration`
3. Custom field `startup_config` or `configuration`
4. Local context data `configuration`

**Returns:**
- Configuration string

**Raises:**
- `ConfigurationNotFoundError`: No config found
- `NetBoxClientError`: API error

**`get_device_serial(device_name: str) -> str`**

Retrieve device serial number.

**Returns:**
- Serial number string

**Raises:**
- `NetBoxClientError`: Serial not available

**`get_device_metadata(device_name: str) -> Dict[str, Any]`**

Retrieve comprehensive device metadata.

**Returns:**
```python
{
    'name': str,
    'id': int,
    'serial': str,
    'device_type': str,
    'device_role': str,
    'site': str,
    'status': str,
    'platform': str,
    'primary_ip': str
}
```

---

### `ztp/ssh_manager.py`

SSH and console connection management.

#### Classes

**`SSHManager`**

SSH connection manager for jump host operations.

**Methods:**

**`__init__(hostname, username, password=None, key_filename=None, port=22, timeout=30)`**

Initialize SSH manager.

**`connect(retries: int = 3, retry_delay: int = 5) -> None`**

Establish SSH connection with retry logic.

**`execute_command(command: str, timeout: int = 60, get_pty: bool = False) -> Tuple[str, str, int]`**

Execute command on remote host.

**Returns:**
- Tuple of (stdout, stderr, exit_code)

**`create_remote_file(remote_path: str, content: str) -> None`**

Create file on remote host via SFTP.

**`close() -> None`**

Close SSH connection.

**Context Manager Support:**
```python
with SSHManager(hostname, username, password) as ssh:
    ssh.execute_command("ls -la")
```

---

**`ConsoleManager`**

Console connection manager for device access.

**Methods:**

**`__init__(hostname, username, password, port=22, timeout=30)`**

Initialize console manager.

**`connect(retries: int = 3, retry_delay: int = 5) -> None`**

Connect to terminal server.

**`connect_to_console(console_port: int) -> None`**

Connect to device console via pmshell.

**Parameters:**
- `console_port`: Console port number

**`execute_device_command(command, wait_time=5, expect=None, timeout=120, handle_pagination=True, auto_confirm=False) -> str`**

Execute command on device console.

**Parameters:**
- `command`: Command string
- `wait_time`: Seconds to wait after command
- `expect`: Expected string in output (optional)
- `timeout`: Command timeout in seconds
- `handle_pagination`: Auto-handle --More-- prompts
- `auto_confirm`: Auto-respond to confirmation prompts

**Returns:**
- Command output string

**Auto-Confirmation Patterns:**
```python
[
    r'Destination filename \[.*?\]\?',
    r'\[confirm\]',
    r'\(y/n\)',
    r'\[yes/no\]'
]
```

**`parse_show_version(output: str) -> Optional[str]`**

Extract serial number from show version output.

**Returns:**
- Serial number or None

**`send_control_c() -> None`**

Send Ctrl+C to console.

**`close() -> None`**

Close console and SSH connections.

---

## Error Handling

### Exception Hierarchy

```
Exception
│
├─ NetBoxClientError (base)
│  ├─ DeviceNotFoundError
│  └─ ConfigurationNotFoundError
│
├─ SSHError (base)
│  ├─ ConnectionError
│  └─ CommandExecutionError
│
└─ ProvisioningError (base)
   ├─ DeviceVerificationError
   └─ ConfigurationDeploymentError
```

### Error Messages

All errors include:
- Clear description of what failed
- Context (device name, step, etc.)
- Actionable suggestions when possible

**Example:**
```
DeviceVerificationError: Serial number mismatch!
Expected 'ABC123XYZ', but device reports 'DEF456UVW'.
Aborting to prevent misconfiguration.
```

### Logging Strategy

**DEBUG Level:**
- SSH command execution details
- Raw API responses
- Buffer contents
- Timing information

**INFO Level:**
- Workflow step transitions
- Major operations (connect, execute, verify)
- Success confirmations

**WARNING Level:**
- Unclear statuses
- Retries
- Non-fatal issues

**ERROR Level:**
- Operation failures
- Exceptions
- Workflow aborts

---

## Security Considerations

### Credential Management

**Best Practices:**

1. **Never commit `.env` file to version control**
   - Add to `.gitignore`
   - Use `.env.template` for examples

2. **Use SSH keys instead of passwords (when possible)**
   ```python
   ssh_manager = SSHManager(
       hostname=jumphost_ip,
       username=username,
       key_filename='~/.ssh/ztp_key'
   )
   ```

3. **Restrict file permissions**
   ```bash
   chmod 600 .env
   chmod 600 ~/.ssh/ztp_key
   ```

4. **Use read-only NetBox API tokens**
   - Only requires: `dcim.view_device`, `dcim.view_configcontext`

5. **Rotate credentials regularly**

### Network Security

**Recommendations:**

1. **Use management network**
   - Isolate provisioning traffic
   - Restrict access to jump host and terminal server

2. **Enable SSL verification**
   - Set `VERIFY_SSL=true` in production
   - Use valid SSL certificates for NetBox

3. **Audit console access**
   - Log all console sessions
   - Review terminal server logs regularly

### Configuration Security

**Device Configurations:**

1. **Sanitize logs**
   - FTP passwords replaced with `****` in logs
   - Enable passwords not logged

2. **Secure FTP directory**
   ```bash
   chmod 750 /srv/ftp
   chown ftpuser:ftpgroup /srv/ftp
   ```

3. **Clean up after provisioning**
   - FTP files removed on completion/failure

### Operational Security

1. **Serial number verification**
   - Prevents wrong-device configuration
   - Critical safety feature

2. **Configuration verification**
   - Ensures config actually applied
   - Detects silent failures

3. **Error handling**
   - Fail fast on critical errors
   - Clear error messages prevent dangerous retries

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: "Device not found in NetBox"

**Symptoms:**
```
DeviceNotFoundError: Device 'switch-01' not found in NetBox
```

**Causes:**
- Device name mismatch (case-sensitive in some versions)
- Device not created in NetBox
- Insufficient API permissions

**Solutions:**
1. Verify device exists: Check NetBox UI
2. Check exact name spelling (copy from NetBox)
3. Verify API token permissions:
   ```python
   # Test in Python
   import pynetbox
   nb = pynetbox.api('https://netbox.example.com', token='...')
   devices = nb.dcim.devices.all()
   print([d.name for d in devices])
   ```

---

#### Issue: "Configuration not found"

**Symptoms:**
```
ConfigurationNotFoundError: No configuration available for device 'switch-01'
```

**Causes:**
- Configuration not populated in any source
- Wrong field names used
- API token lacks permissions

**Solutions:**
1. Check config sources in NetBox:
   - Config context: Add `startup_config` or `configuration` key
   - Custom field: Create field named `startup_config`
   - Config template: Assign template to device
2. Verify configuration content is not empty
3. Test config retrieval:
   ```python
   from ztp.netbox_client import NetBoxClient
   client = NetBoxClient(url, token)
   config = client.get_device_config('switch-01')
   print(config)
   ```

---

#### Issue: "Serial number mismatch"

**Symptoms:**
```
DeviceVerificationError: Serial number mismatch!
Expected 'ABC123', but device reports 'XYZ789'
```

**Causes:**
- Wrong console port (connected to different device)
- Serial number not updated in NetBox
- Device recently replaced

**Solutions:**
1. Verify console port number in terminal server
2. Update NetBox serial number:
   - Check device label for actual serial
   - Update in NetBox UI
3. Execute `show version` manually to confirm serial
4. Check terminal server port mapping

---

#### Issue: "Unable to enter enable mode"

**Symptoms:**
```
ProvisioningError: Unable to enter enable mode. Device may require enable password.
```

**Causes:**
- Enable password configured on device
- Device in ROMMON or special mode
- Console connection issues

**Solutions:**
1. Remove enable password from device (recommended):
   ```
   Device# configure terminal
   Device(config)# no enable password
   Device(config)# no enable secret
   ```
2. Or extend tool to support enable password:
   ```python
   # In .env
   ENABLE_PASSWORD=cisco

   # In _enter_enable_mode()
   if 'Password:' in output:
       self.console_manager.channel.send(f'{enable_password}\r\n')
   ```
3. Check device is in normal mode (not ROMMON)

---

#### Issue: "Command contains backspace characters (^h)"

**Symptoms:**
```
Switch>copy ftp://...flas  ^h: vrf Mgmt-vrf
% Invalid input detected at '^' marker.
```

**Causes:**
- Console buffer corruption
- Command sent too fast
- Terminal emulation issues

**Solutions:**
- Fixed in latest version with character-by-character sending
- If still occurs:
  1. Increase delay between characters (change `0.01` to `0.02`)
  2. Check terminal server configuration
  3. Verify console cable and connection quality

---

#### Issue: "Configuration applied but verification fails"

**Symptoms:**
```
ConfigurationDeploymentError: Configuration verification failed.
Missing items: hostname 'switch-01'
```

**Causes:**
- Configuration syntax errors (device rejected parts)
- Device applying config slowly
- Verification markers not in configuration

**Solutions:**
1. Check device logs for syntax errors:
   ```
   show logging | include ERROR
   ```
2. Increase wait time after config application:
   ```python
   # In orchestrator.py
   time.sleep(30)  # Increase from 10
   ```
3. Manually verify configuration was applied:
   ```
   show running-config | include hostname
   ```
4. Check if device requires `write memory` or `copy run start`

---

#### Issue: "FTP copy timeout"

**Symptoms:**
```
Configuration copy timed out after 300 seconds
```

**Causes:**
- Network connectivity issues
- FTP server unreachable from device
- FTP credentials incorrect
- Management VRF misconfigured

**Solutions:**
1. Test FTP connectivity from device:
   ```
   Device# ping vrf Mgmt-vrf 192.168.1.100
   Device# telnet vrf Mgmt-vrf 192.168.1.100 21
   ```
2. Verify FTP credentials work:
   ```bash
   ftp 192.168.1.100
   # Enter username and password
   ```
3. Check FTP server logs:
   ```bash
   tail -f /var/log/vsftpd.log
   ```
4. Verify management VRF configuration:
   ```
   Device# show vrf Mgmt-vrf
   ```

---

#### Issue: "SSH connection refused"

**Symptoms:**
```
ConnectionError: Failed to connect to 10.10.10.100 after 3 attempts
```

**Causes:**
- Host unreachable
- SSH service not running
- Firewall blocking connection
- Wrong credentials

**Solutions:**
1. Test basic connectivity:
   ```bash
   ping 10.10.10.100
   ```
2. Test SSH manually:
   ```bash
   ssh user@10.10.10.100
   ```
3. Check SSH service status:
   ```bash
   systemctl status sshd
   ```
4. Review firewall rules
5. Verify credentials in `.env`

---

### Debug Mode

Enable detailed logging:

```bash
# In .env
LOG_LEVEL=DEBUG

# Run provisioning
uv run zero_touch_provision.py --device-name switch-01 --console-port 5001 --log-level DEBUG
```

**Debug output includes:**
- Raw SSH command output
- Console buffer contents
- API request/response details
- Timing information
- State transitions

---

### Log Analysis

**Locate key events:**

```bash
# Find failures
grep ERROR ztp.log

# Find state transitions
grep "STEP [0-9]" ztp.log

# Find serial number verification
grep "serial" ztp.log -i

# Find configuration verification
grep "verification" ztp.log -i

# Find command execution
grep "Executing device command" ztp.log
```

---

## API Reference

### Command-Line Interface

```bash
usage: zero_touch_provision.py [-h] --device-name DEVICE_NAME
                                --console-port CONSOLE_PORT
                                [--log-level {DEBUG,INFO,WARNING,ERROR}]
                                [--dry-run]

Zero Touch Provisioning Tool

required arguments:
  --device-name DEVICE_NAME    Name of device in NetBox
  --console-port CONSOLE_PORT  Console port number on terminal server

optional arguments:
  -h, --help                   Show help message
  --log-level LEVEL            Logging level (default: INFO)
  --dry-run                    Validate only, don't apply (not implemented)
```

**Examples:**

```bash
# Basic usage
uv run zero_touch_provision.py --device-name switch-01 --console-port 5001

# With debug logging
uv run zero_touch_provision.py \
  --device-name switch-01 \
  --console-port 5001 \
  --log-level DEBUG

# Using installed entry point
ztp --device-name switch-01 --console-port 5001
```

---

### Python API

**Programmatic Usage:**

```python
from ztp.orchestrator import ProvisioningOrchestrator
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Initialize orchestrator
orchestrator = ProvisioningOrchestrator(
    device_name="switch-01",
    console_port=5001,
    netbox_url=os.getenv("NETBOX_URL"),
    netbox_token=os.getenv("NETBOX_TOKEN"),
    jumphost_ip=os.getenv("JUMPHOST_IP"),
    jumphost_username=os.getenv("JUMPHOST_USERNAME"),
    jumphost_password=os.getenv("JUMPHOST_PASSWORD"),
    terminal_server_ip=os.getenv("TERMINAL_SERVER_IP"),
    terminal_server_username=os.getenv("TERMINAL_SERVER_USERNAME"),
    terminal_server_password=os.getenv("TERMINAL_SERVER_PASSWORD"),
    ftp_server_ip=os.getenv("FTP_SERVER_IP"),
    ftp_username=os.getenv("FTP_USERNAME"),
    ftp_password=os.getenv("FTP_PASSWORD"),
    ftp_directory=os.getenv("FTP_DIRECTORY", "/srv/ftp"),
    verify_ssl=os.getenv("VERIFY_SSL", "true").lower() == "true"
)

# Execute provisioning
try:
    success = orchestrator.provision_device()
    if success:
        print("Provisioning completed successfully!")
        status = orchestrator.get_status()
        print(f"Device: {status['device_name']}")
        print(f"State: {status['state']}")
    else:
        print("Provisioning failed")
except Exception as e:
    print(f"Error: {e}")
```

---

## Extension Guide

### Adding Support for Non-Cisco Devices

**Step 1: Add Command Patterns**

Edit `ztp/orchestrator.py`:

```python
def _step_copy_config_to_flash(self):
    # Detect device type
    device_type = self._detect_device_type()

    if device_type == 'cisco':
        copy_command = f"copy {ftp_url} flash: vrf Mgmt-vrf"
    elif device_type == 'arista':
        copy_command = f"copy {ftp_url} flash:"
    elif device_type == 'juniper':
        copy_command = f"file copy {ftp_url} /var/tmp/{filename}"
```

**Step 2: Add Serial Parsing**

Edit `ztp/ssh_manager.py`:

```python
def parse_show_version(self, output: str, device_type: str = 'cisco'):
    if device_type == 'cisco':
        # Existing patterns
        patterns = [...]
    elif device_type == 'arista':
        patterns = [
            r'Serial number:\s+(\S+)',
            r'System serial number:\s+(\S+)'
        ]
    elif device_type == 'juniper':
        patterns = [
            r'Chassis:\s+(\S+)'
        ]
```

### Adding Enable Password Support

**Step 1: Add Environment Variable**

In `.env.template`:
```bash
ENABLE_PASSWORD=cisco123
```

**Step 2: Update Orchestrator**

```python
def __init__(self, ..., enable_password: Optional[str] = None):
    self.enable_password = enable_password

def _enter_enable_mode(self):
    # ... existing code ...
    if 'Password:' in output:
        if self.enable_password:
            logger.info("Sending enable password")
            self.console_manager.channel.send(f'{self.enable_password}\r\n')
        else:
            logger.warning("Enable password required but not provided")
            self.console_manager.channel.send('\r\n')
```

### Adding SSH Key Authentication

**Step 1: Update SSHManager**

Already supported! Just use:

```python
ssh_manager = SSHManager(
    hostname=jumphost_ip,
    username=username,
    key_filename='~/.ssh/ztp_key'  # Instead of password
)
```

**Step 2: Update CLI**

Add argument:
```python
parser.add_argument(
    '--ssh-key',
    help='SSH private key file'
)
```

### Adding Dry-Run Mode

**Implementation:**

```python
def provision_device(self, dry_run: bool = False) -> bool:
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

        # Step 1: Validate NetBox connectivity
        self._step_retrieve_netbox_config()
        logger.info(f"✓ Config retrieved ({len(self.device_config)} bytes)")

        # Step 2: Validate SSH connectivity
        logger.info("✓ Would create FTP file: {self.config_filename}")

        # Step 3: Validate console connectivity
        logger.info("✓ Would connect to console port {self.console_port}")

        # Don't actually apply anything
        logger.info("DRY RUN COMPLETE - No changes made")
        return True
    else:
        # Normal provisioning
        return self._provision_device_normal()
```

### Adding Post-Provisioning Actions

**Example: Save Configuration**

```python
def _step_save_configuration(self):
    """Step 8: Save running-config to startup-config"""
    logger.info("-" * 80)
    logger.info("STEP 8: Saving configuration")
    logger.info("-" * 80)

    save_command = "write memory"  # or "copy run start"
    output = self.console_manager.execute_device_command(
        command=save_command,
        wait_time=30
    )

    if 'OK' in output or 'success' in output.lower():
        logger.info("Configuration saved successfully")
    else:
        logger.warning("Save status unclear")
```

**Example: Send Notification**

```python
def _send_notification(self, status: str, message: str):
    """Send notification via Slack/email"""
    import requests

    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    if webhook_url:
        payload = {
            'text': f'ZTP {status}: {self.device_name}',
            'attachments': [{
                'text': message,
                'color': 'good' if status == 'SUCCESS' else 'danger'
            }]
        }
        requests.post(webhook_url, json=payload)
```

---

## Performance Considerations

### Timing Benchmarks

Typical provisioning times (per device):

| Step | Duration | Notes |
|------|----------|-------|
| NetBox retrieval | 1-2s | Depends on API latency |
| FTP file creation | 2-3s | Includes SSH connection |
| Console connection | 5-8s | Includes pmshell invocation |
| Enable mode | 2-3s | Quick on most devices |
| Device verification | 10-15s | `show version` output |
| Config copy to flash | 10-60s | Depends on file size |
| Config application | 30-120s | Depends on complexity |
| Verification | 5-15s | Multiple show commands |
| **Total** | **1.5-4 minutes** | For typical switch |

### Optimization Strategies

**1. Parallel Provisioning**

For multiple devices:

```python
from concurrent.futures import ThreadPoolExecutor

devices = [
    ('switch-01', 5001),
    ('switch-02', 5002),
    ('switch-03', 5003)
]

def provision_single(device_name, console_port):
    orchestrator = ProvisioningOrchestrator(...)
    return orchestrator.provision_device()

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [
        executor.submit(provision_single, name, port)
        for name, port in devices
    ]
    results = [f.result() for f in futures]
```

**2. Configuration Caching**

Cache NetBox configs to reduce API calls:

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_device_config_cached(device_name: str) -> str:
    return netbox_client.get_device_config(device_name)
```

**3. Reduce Wait Times**

For well-behaved devices, reduce timeouts:

```python
# Default
wait_time=60

# Optimized (if device is fast)
wait_time=20
```

---

## Appendix

### A. Device Command Reference

**Cisco IOS/IOS-XE Commands:**

```bash
# Enter enable mode
enable

# Disable pagination
terminal length 0

# Show version
show version

# Copy from FTP to flash
copy ftp://user:pass@server//file.txt flash: vrf Mgmt-vrf

# Apply configuration
copy filename running-config

# Verify configuration
show running-config | include hostname
show running-config | include vlan
show running-config interface GigabitEthernet1/0/1

# Save configuration
write memory
copy running-config startup-config
```

### B. FTP Server Configuration

**vsftpd Configuration (`/etc/vsftpd.conf`):**

```ini
# Basic settings
listen=YES
anonymous_enable=NO
local_enable=YES
write_enable=YES

# FTP directory
local_root=/srv/ftp

# Passive mode (recommended)
pasv_enable=YES
pasv_min_port=10000
pasv_max_port=10100

# Security
chroot_local_user=YES
allow_writeable_chroot=YES

# Logging
xferlog_enable=YES
xferlog_file=/var/log/vsftpd.log
```

**Create FTP user:**

```bash
sudo useradd -m -d /srv/ftp ftpnet
sudo passwd ftpnet
sudo chown ftpnet:ftpnet /srv/ftp
sudo chmod 750 /srv/ftp
```

### C. Terminal Server Configuration

**Console Server Requirements:**

- SSH access enabled
- `pmshell` or equivalent console manager
- Console ports configured with correct baud rates
- Port numbering scheme documented

**Example pmshell Session:**

```bash
$ ssh console-user@terminal-server
$ pmshell
Select console port: 5001
Connected to console port 5001
Press Ctrl+] to exit

Switch>
```

### D. NetBox Configuration Templates

**Example Config Template:**

```django
hostname {{ device.name }}

{% for interface in device.interfaces.all() %}
interface {{ interface.name }}
 {% if interface.description %}
 description {{ interface.description }}
 {% endif %}
 {% if interface.mode %}
 switchport mode {{ interface.mode }}
 {% endif %}
!
{% endfor %}

{% for vlan in device.site.vlans.all() %}
vlan {{ vlan.vid }}
 name {{ vlan.name }}
!
{% endfor %}
```

### E. Regular Expression Patterns

**Serial Number Patterns:**

```python
# Cisco Catalyst
r'Model [Nn]umber\s*:?\s*\S+\s+[Ss]ystem [Ss]erial [Nn]umber\s*:?\s*(\S+)'
r'[Ss]ystem [Ss]erial [Nn]umber\s*:?\s*(\S+)'
r'[Pp]rocessor [Bb]oard ID\s+(\S+)'

# Chassis-based
r'Chassis Serial Number\s*:?\s+(\S+)'

# Generic
r'[Ss]erial\s+[Nn]umber\s*:?\s+(\S+)'
r'Serial [Nn]um\s*:?\s*(\S+)'
r'SN\s*:?\s*(\S+)'
```

**Configuration Element Patterns:**

```python
# Hostname
r'^hostname\s+(\S+)'

# VLANs
r'^vlan\s+(\d+)'

# Interfaces
r'^interface\s+(\S+)'

# IP addresses
r'ip address\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)'
```

### F. Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Provisioning failed |
| 2 | Configuration error |
| 3 | Missing required arguments |

---

## Document Version

- **Version:** 1.0
- **Date:** 2025-11-21
- **Author:** Generated by Claude Code
- **Status:** Production

---

## Support and Contribution

### Reporting Issues

Open issues at: [GitHub Issues](https://github.com/mountaintop1/zero_touch/issues)

Include:
- Complete error message
- Log file excerpt (with sensitive data redacted)
- Device type and software version
- Steps to reproduce

### Contributing

1. Fork repository
2. Create feature branch
3. Add tests for new functionality
4. Update documentation
5. Submit pull request

### License

See LICENSE file in repository.

---

*End of Technical Documentation*
