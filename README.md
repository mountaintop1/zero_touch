# Zero Touch Provisioning (ZTP) Tool

A production-ready Python automation tool for zero-touch provisioning of network devices. This tool streamlines the deployment process by automatically retrieving configurations from NetBox, deploying them via FTP, and applying them to network devices through console access.

## Overview

The ZTP tool eliminates manual configuration steps, reduces human error, and enables rapid, consistent device provisioning at scale. It integrates with your existing infrastructure to provide a complete, hands-off provisioning workflow.

### Key Features

- **Automated Configuration Retrieval**: Fetches device configurations from NetBox (source of truth)
- **FTP-Based Deployment**: Creates and deploys configuration files via FTP server
- **Console-Based Application**: Applies configurations through out-of-band console access
- **Device Verification**: Validates device identity by serial number before applying configuration
- **Comprehensive Error Handling**: Robust error handling with retry logic and detailed logging
- **Production-Ready**: Designed for enterprise environments with security and reliability in mind

## Architecture

### Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Zero Touch Provisioning Flow                 │
└─────────────────────────────────────────────────────────────────┘

1. NetBox API
   ├─ Retrieve device configuration
   └─ Get expected serial number

2. Jump Host (FTP Server)
   ├─ SSH connection
   ├─ Create config file in /srv/ftp
   └─ Verify file creation

3. Terminal Server
   ├─ SSH connection
   ├─ Execute pmshell command
   └─ Connect to device console port

4. Device Verification
   ├─ Execute 'show version'
   ├─ Parse serial number
   └─ Compare with NetBox serial

5. Configuration Deployment
   ├─ Copy config from FTP to flash
   └─ Copy config to running-config

6. Verification & Cleanup
   ├─ Verify configuration applied
   └─ Close all connections
```

### Infrastructure Requirements

- **NetBox**: Source of truth for device configurations and metadata
- **Linux Jump Host**: SSH-accessible server with FTP service at `/srv/ftp`
- **Terminal Server**: Out-of-band terminal server running `pmshell` for console access
- **Network Devices**: Routers/switches with console and management network connectivity

### Component Architecture

```
zero_touch_provision.py          # Main CLI entry point
│
├─ ztp/
│  ├─ __init__.py                # Package initialization
│  ├─ netbox_client.py           # NetBox API client
│  │  └─ NetBoxClient            # Handles NetBox interactions
│  │
│  ├─ ssh_manager.py             # SSH connection management
│  │  ├─ SSHManager              # Jump host SSH connections
│  │  └─ ConsoleManager          # Terminal server & console access
│  │
│  └─ orchestrator.py            # Main workflow orchestration
│     └─ ProvisioningOrchestrator # Coordinates entire workflow
│
├─ .env                          # Environment configuration (create from template)
├─ .env.template                 # Configuration template
├─ requirements.txt              # Python dependencies
└─ logs/                         # Application logs
```

## Prerequisites

### System Requirements

- Python 3.8 or higher
- SSH access to jump host and terminal server
- Network connectivity to NetBox API
- FTP service configured on jump host

### NetBox Configuration

Device configurations must be stored in NetBox in one of these locations:

1. **Config Context** (recommended):
   ```json
   {
     "startup_config": "hostname router-01\n..."
   }
   ```

2. **Custom Fields**:
   - Field name: `startup_config` or `configuration`
   - Field type: Text

3. **Local Context Data**:
   ```json
   {
     "configuration": "hostname router-01\n..."
   }
   ```

Device must have serial number populated in NetBox for verification.

### Infrastructure Setup

1. **Jump Host**:
   - FTP service running (vsftpd, proftpd, etc.)
   - FTP directory: `/srv/ftp` (configurable)
   - SSH access enabled
   - Network connectivity to devices' management network

2. **Terminal Server**:
   - `pmshell` command available
   - Console ports mapped to devices
   - SSH access enabled

3. **Network Devices**:
   - Console connectivity via terminal server
   - Management VRF configured (if applicable)
   - FTP client capability
   - Network reachability to FTP server

## Installation

### 1. Clone or Download

```bash
# Clone repository or download source code
cd /path/to/installation
```

### 2. Install Python Dependencies

**Option A: Using uv (Recommended - Fast & Modern)**

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install as editable package (requires setuptools)
uv pip install setuptools
uv pip install -e .

# Or install from requirements.txt
uv pip install -r requirements.txt
```

**Option B: Using traditional pip**

```bash
pip install -r requirements.txt
```

**Why uv?**
- 10-100x faster than pip
- Better dependency resolution
- Built-in virtual environment management
- Modern Python package installer written in Rust

> 📖 **For detailed uv usage, troubleshooting, and examples, see [UV_SETUP.md](UV_SETUP.md)**

### 3. Configure Environment

```bash
# Copy template to create .env file
cp .env.template .env

# Edit configuration with your values
vim .env  # or use your preferred editor
```

### 4. Update .env File

Edit `.env` and configure all required parameters:

```bash
# NetBox Configuration
NETBOX_URL=https://netbox.example.com
NETBOX_TOKEN=your_netbox_api_token

# Jump Host
JUMPHOST_IP=10.0.0.1
JUMPHOST_USERNAME=admin
JUMPHOST_PASSWORD=secure_password

# Terminal Server
TERMINAL_SERVER_IP=10.0.0.2
TERMINAL_SERVER_USERNAME=admin
TERMINAL_SERVER_PASSWORD=secure_password

# FTP Server (from device perspective)
FTP_SERVER_IP=1.1.1.1
FTP_USERNAME=ftpuser
FTP_PASSWORD=ftp_password

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/provisioning.log
```

### 5. Verify Installation

```bash
# Verify help output
uv run zero_touch_provision.py --help

# Or using the script entry point
uv run ztp --help
```

## Usage

### Basic Usage

```bash
# Provision a device
uv run zero_touch_provision.py --device-name router-01 --console-port 5

# Or using the script entry point
uv run ztp --device-name router-01 --console-port 5
```

### Command-Line Options

```
usage: zero_touch_provision.py [-h] --device-name DEVICE_NAME --console-port CONSOLE_PORT
                                [--log-level {DEBUG,INFO,WARNING,ERROR}] [--dry-run] [--version]

Zero Touch Provisioning (ZTP) for Network Devices

options:
  -h, --help            show this help message and exit
  --device-name DEVICE_NAME
                        Name of device to provision (must exist in NetBox)
  --console-port CONSOLE_PORT
                        Console port number on terminal server
  --log-level {DEBUG,INFO,WARNING,ERROR}
                        Logging level (overrides .env LOG_LEVEL)
  --dry-run             Validate configuration and connections without applying changes
  --version             show program's version number and exit
```

### Examples

#### Provision with Default Settings

```bash
uv run zero_touch_provision.py \
  --device-name router-core-01 \
  --console-port 5
```

#### Provision with Debug Logging

```bash
uv run zero_touch_provision.py \
  --device-name switch-access-01 \
  --console-port 10 \
  --log-level DEBUG
```

#### Dry Run (Validation Only)

```bash
uv run zero_touch_provision.py \
  --device-name router-edge-01 \
  --console-port 15 \
  --dry-run
```

### Expected Output

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║        Zero Touch Provisioning (ZTP) Tool v1.0.0            ║
║        Network Device Automation                             ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

Provisioning Configuration:
  Device Name:      router-01
  Console Port:     5
  NetBox URL:       https://netbox.example.com
  Jump Host:        10.0.0.1
  Terminal Server:  10.0.0.2
  FTP Server:       1.1.1.1
  Log Level:        INFO
  Log File:         ./logs/provisioning.log

Initializing provisioning orchestrator...

================================================================================
STARTING ZERO-TOUCH PROVISIONING FOR: router-01
================================================================================
--------------------------------------------------------------------------------
STEP 1: Retrieving configuration from NetBox
--------------------------------------------------------------------------------
2025-11-20 10:00:01 - INFO - Fetching configuration for device: router-01
2025-11-20 10:00:02 - INFO - Successfully retrieved configuration (15234 bytes)
2025-11-20 10:00:02 - INFO - Expected serial number: FOC1234ABCD

--------------------------------------------------------------------------------
STEP 2: Creating configuration file on FTP server
--------------------------------------------------------------------------------
2025-11-20 10:00:03 - INFO - Connecting to jump host: 10.0.0.1
2025-11-20 10:00:04 - INFO - Creating configuration file: router-01.txt
2025-11-20 10:00:05 - INFO - File created successfully

... [steps continue] ...

SUCCESS!
Device 'router-01' provisioned successfully
Duration: 0:03:45
```

## Workflow Details

### Step-by-Step Process

1. **NetBox Configuration Retrieval**
   - Connects to NetBox API using authentication token
   - Retrieves device configuration from config context, custom fields, or local context
   - Fetches expected serial number for verification
   - Validates configuration is not empty

2. **FTP File Preparation**
   - Establishes SSH connection to jump host
   - Creates configuration file: `{device_name}.txt` in `/srv/ftp`
   - Writes NetBox configuration to file
   - Verifies file creation with `ls -lh`

3. **Terminal Server Console Access**
   - SSH connection to out-of-band terminal server
   - Executes `pmshell` command
   - Responds to console number prompt with device's console port
   - Establishes interactive console session

4. **Device Verification**
   - Executes `show version` on device
   - Parses output to extract serial number
   - Compares actual vs. expected serial number
   - **ABORTS if mismatch** to prevent misconfiguration

5. **Configuration Deployment**
   - Executes FTP copy command:
     ```
     copy ftp://username:pwd@1.1.1.1//device.txt flash: vrf Mgmt-vrf
     ```
   - Monitors transfer progress
   - Validates successful copy to flash

6. **Configuration Application**
   - Executes:
     ```
     copy device.txt running-config
     ```
   - Monitors configuration application
   - Validates no errors in output
   - Verifies configuration applied

## Security Considerations

### Credential Management

- **Never commit `.env` file** to version control
- Add `.env` to `.gitignore`
- Use strong, unique passwords for each service
- Rotate credentials regularly
- Consider SSH key authentication instead of passwords

### Network Security

- Use SSL/TLS for NetBox API (`VERIFY_SSL=true` in production)
- Implement network segmentation (management VRF)
- Restrict FTP access to authorized devices only
- Use secure protocols (SSH, HTTPS) exclusively

### Production Best Practices

- Generate NetBox API tokens with minimal required permissions
- Limit FTP user permissions to `/srv/ftp` directory only
- Use read-only accounts where possible
- Implement audit logging for all provisioning operations
- Consider secrets management system (HashiCorp Vault, AWS Secrets Manager)

### Log Security

- Sanitize logs to prevent credential exposure
- Rotate log files regularly
- Restrict log file permissions (`chmod 600`)
- Monitor logs for suspicious activity

## Troubleshooting

### Common Issues

#### 1. NetBox Connection Failed

**Symptoms**:
```
ERROR: Failed to connect to NetBox: Authentication failed
```

**Solutions**:
- Verify `NETBOX_URL` is correct and accessible
- Check `NETBOX_TOKEN` is valid (not expired)
- Test NetBox connectivity: `curl -H "Authorization: Token YOUR_TOKEN" https://netbox.example.com/api/`
- For self-signed certificates, set `VERIFY_SSL=false` (development only)

#### 2. Device Not Found in NetBox

**Symptoms**:
```
ERROR: Device 'router-01' not found in NetBox
```

**Solutions**:
- Verify device name matches exactly (case-sensitive)
- Check device exists in NetBox web interface
- Ensure device is not decommissioned or deleted

#### 3. Configuration Not Available

**Symptoms**:
```
ERROR: No configuration available for device 'router-01'
```

**Solutions**:
- Verify configuration is stored in NetBox config_context, custom_fields, or local_context_data
- Use key name: `startup_config` or `configuration`
- Check configuration is not empty

#### 4. SSH Connection Timeout

**Symptoms**:
```
ERROR: Connection timeout to 10.0.0.1
```

**Solutions**:
- Verify jump host/terminal server IP is correct and reachable
- Check SSH service is running: `systemctl status sshd`
- Verify firewall rules allow SSH (port 22)
- Test manual SSH: `ssh user@10.0.0.1`

#### 5. Serial Number Mismatch

**Symptoms**:
```
ERROR: Serial number mismatch! Expected 'FOC1234ABCD', but device reports 'FOC5678EFGH'
```

**Solutions**:
- **This is a safety feature** - verify you have the correct device
- Check device cabling and console port mapping
- Update NetBox with correct serial number if device was replaced
- Verify console port number is correct

#### 6. FTP Copy Failed

**Symptoms**:
```
ERROR: Failed to copy configuration to flash
```

**Solutions**:
- Verify FTP server IP is reachable from device: `ping 1.1.1.1 vrf Mgmt-vrf`
- Check FTP credentials are correct
- Verify FTP service is running on jump host
- Ensure device has sufficient flash space
- Check management VRF configuration

### Debug Mode

Enable detailed debug logging:

```bash
uv run zero_touch_provision.py \
  --device-name router-01 \
  --console-port 5 \
  --log-level DEBUG
```

Debug logs include:
- Full SSH command output
- API request/response details
- Console session transcripts
- Detailed error traces

### Log Files

Logs are written to `./logs/provisioning.log` by default.

```bash
# View recent logs
tail -f logs/provisioning.log

# Search for errors
grep ERROR logs/provisioning.log

# View specific provisioning session
grep "router-01" logs/provisioning.log
```

## Advanced Configuration

### SSH Key Authentication

To use SSH keys instead of passwords:

1. Generate SSH key pair:
   ```bash
   ssh-keygen -t rsa -b 4096 -f ~/.ssh/ztp_key
   ```

2. Copy public key to jump host and terminal server:
   ```bash
   ssh-copy-id -i ~/.ssh/ztp_key.pub user@jumphost
   ssh-copy-id -i ~/.ssh/ztp_key.pub user@termserver
   ```

3. Modify `ztp/ssh_manager.py` to use key authentication:
   ```python
   ssh_manager = SSHManager(
       hostname=jumphost_ip,
       username=username,
       key_filename='~/.ssh/ztp_key'  # Add this parameter
   )
   ```

### Custom Timeouts

Adjust timeouts in `.env` (requires code modification):

```bash
SSH_TIMEOUT=60
CONSOLE_TIMEOUT=300
FTP_COPY_TIMEOUT=600
```

### Multiple FTP Servers

For environments with multiple FTP servers, modify orchestrator to select based on device location.

## Development

### Running Tests

```bash
# Unit tests (when implemented)
uv run pytest tests/

# Integration tests
uv run pytest tests/integration/
```

### Code Structure

- **Modular Design**: Separate concerns (NetBox, SSH, Orchestration)
- **Error Handling**: Comprehensive exception handling at each layer
- **Logging**: Detailed logging at DEBUG, INFO, ERROR levels
- **Type Hints**: Full type annotations for IDE support
- **Docstrings**: Comprehensive documentation for all classes/methods

### Contributing

1. Follow PEP 8 style guidelines
2. Add docstrings to all functions/classes
3. Include type hints
4. Test thoroughly before submitting
5. Update README with new features

## License

This tool is provided as-is for network automation purposes. Adapt and modify as needed for your environment.

## Support

For issues, questions, or contributions:

1. Check logs in `./logs/provisioning.log`
2. Enable DEBUG logging for detailed output
3. Review this README's troubleshooting section
4. Verify infrastructure prerequisites are met

## Changelog

### Version 1.0.0 (2025-11-20)

- Initial release
- NetBox integration for configuration retrieval
- SSH-based FTP file deployment
- Console-based device provisioning
- Serial number verification
- Comprehensive error handling and logging
- Production-ready security features

## Acknowledgments

Built using:
- [pynetbox](https://github.com/netbox-community/pynetbox) - NetBox API client
- [Paramiko](https://github.com/paramiko/paramiko) - SSH protocol implementation
- [Netmiko](https://github.com/ktbyers/netmiko) - Network device SSH library
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Environment management
