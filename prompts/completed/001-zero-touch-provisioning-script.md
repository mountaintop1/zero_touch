<objective>
Build a production-ready Python script that automates zero-touch provisioning for network devices. This script will streamline the deployment process by automatically retrieving configurations from NetBox, deploying them via FTP, and applying them to network devices through console access. This eliminates manual configuration steps, reduces human error, and enables rapid, consistent device provisioning at scale.
</objective>

<context>
This is a network automation tool for provisioning new network devices (routers, switches) in an enterprise environment. The infrastructure includes:
- NetBox as the source of truth for device configurations
- A Linux jump host with FTP service at `/srv/ftp`
- An out-of-band (OOB) terminal server providing console access to devices
- Network devices accessible via console and out-of-band management interfaces

The script must handle the complete provisioning workflow autonomously while maintaining production-level reliability and security.
</context>

<requirements>

## Functional Requirements

The script must execute these steps in sequence:

1. **NetBox Configuration Retrieval**
   - Connect to NetBox API using authentication token
   - Retrieve device configuration for a specified device name
   - Handle API errors gracefully (auth failures, device not found, network issues)

2. **FTP File Preparation**
   - SSH to Linux jump host
   - Create configuration file in `/srv/ftp` directory
   - Write NetBox configuration to file named `{device_name}.txt`
   - Verify file creation and content integrity

3. **Terminal Server Console Access**
   - SSH to OOB terminal server
   - Execute `pmshell` command to access console management
   - Respond to console number prompt with device's console port
   - Establish console session to target device

4. **Device Verification**
   - Execute `show version` command on device
   - Parse output to extract serial number
   - Compare against expected serial number from NetBox
   - Abort provisioning if serial numbers don't match (safety check)

5. **Configuration Deployment**
   - Execute: `copy ftp://username:pwd@1.1.1.1//{device_name}.txt flash: vrf Mgmt-vrf`
   - Monitor copy process for completion or errors
   - Verify successful file transfer to device flash

6. **Configuration Application**
   - Execute: `copy {device_name}.txt running-config`
   - Monitor configuration application
   - Verify device accepts configuration without errors

## Non-Functional Requirements

- **Error Handling**: Comprehensive exception handling at each stage with meaningful error messages
- **Logging**: Detailed logging using Python's logging module (INFO for progress, DEBUG for details, ERROR for failures)
- **Retry Logic**: Implement retries with exponential backoff for transient failures (network timeouts, SSH disconnections)
- **Security**: All credentials managed via environment variables (no hardcoded secrets)
- **Validation**: Input validation for device names, IP addresses, and configuration content
- **Timeout Management**: Appropriate timeouts for SSH sessions, commands, and file transfers
- **Idempotency**: Safe to re-run if interrupted (check if config file exists, verify current device state)

</requirements>

<implementation>

## Technology Stack

Use these Python libraries:
- **pynetbox**: NetBox API client for retrieving device configurations
- **paramiko**: Low-level SSH client for jump host and terminal server connections
- **netmiko**: High-level SSH client optimized for network devices (use for device console interactions)
- **python-dotenv**: Loading environment variables from `.env` file
- **logging**: Built-in module for comprehensive logging

## Architecture

Create a modular design with these components:

1. **NetBoxClient class**: Handles NetBox API interactions
   - `get_device_config(device_name)`: Retrieve configuration
   - `get_device_serial(device_name)`: Get expected serial number

2. **SSHManager class**: Manages SSH connections and command execution
   - `connect_to_host(hostname, username, password)`: Establish SSH connection
   - `execute_command(command, timeout)`: Run command and return output
   - `create_remote_file(path, content)`: Create file on remote system via SSH

3. **ConsoleManager class**: Handles terminal server and device console access
   - `connect_to_pmshell(console_port)`: Access device via pmshell
   - `execute_device_command(command)`: Run command on device console
   - `parse_show_version(output)`: Extract serial number from show version output

4. **ProvisioningOrchestrator class**: Main workflow coordinator
   - `provision_device(device_name, console_port)`: Execute full provisioning workflow
   - `verify_device(expected_serial)`: Safety check before applying config
   - `rollback()`: Cleanup on failure (remove FTP file, disconnect sessions)

## What to Avoid and Why

- **Don't hardcode credentials**: Credentials in code lead to security vulnerabilities and can't be rotated without code changes. Use environment variables for flexibility and security.
- **Don't skip serial number verification**: Applying wrong config to wrong device can cause network outages. Always verify before applying configuration.
- **Don't ignore command output**: Network devices report errors in command output. Parse and validate all output to detect failures.
- **Don't use shell=True in subprocess**: This creates security vulnerabilities. Use paramiko/netmiko for SSH operations instead.
- **Don't log sensitive data**: Never log passwords, API tokens, or full configurations. Sanitize logs to show only non-sensitive metadata.

## Error Handling Strategy

For each operation:
- Wrap in try-except blocks with specific exception types
- Log errors with full context (what operation, which device, error details)
- For transient errors (network timeout, SSH disconnect): Retry up to 3 times with exponential backoff
- For permanent errors (auth failure, device not found): Fail fast with clear error message
- Always cleanup resources (close SSH connections, remove temp files) in finally blocks

## Configuration File Structure

Create `.env.template` with placeholders:
```
# NetBox Configuration
NETBOX_URL=https://netbox.example.com
NETBOX_TOKEN=your_token_here

# Jump Host Configuration
JUMPHOST_IP=10.0.0.1
JUMPHOST_USERNAME=admin
JUMPHOST_PASSWORD=password_or_use_ssh_key

# Terminal Server Configuration
TERMINAL_SERVER_IP=10.0.0.2
TERMINAL_SERVER_USERNAME=admin
TERMINAL_SERVER_PASSWORD=password_or_use_ssh_key

# FTP Configuration
FTP_SERVER_IP=1.1.1.1
FTP_USERNAME=ftpuser
FTP_PASSWORD=ftppass

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/provisioning.log
```

</implementation>

<output>

Create these files:

1. **`./zero_touch_provision.py`** - Main script with CLI interface
   - Accept device_name and console_port as command-line arguments
   - Execute full provisioning workflow
   - Display progress and results to console
   - Return appropriate exit codes (0=success, 1=failure)

2. **`./ztp/netbox_client.py`** - NetBox API client class
   - NetBoxClient implementation with error handling
   - Methods for retrieving device config and serial number

3. **`./ztp/ssh_manager.py`** - SSH connection manager
   - SSHManager and ConsoleManager classes
   - Robust connection handling with retries

4. **`./ztp/orchestrator.py`** - Main orchestration logic
   - ProvisioningOrchestrator class
   - Complete workflow implementation with state tracking

5. **`./ztp/__init__.py`** - Package initialization

6. **`./requirements.txt`** - Python dependencies
   ```
   pynetbox>=7.0.0
   paramiko>=3.0.0
   netmiko>=4.0.0
   python-dotenv>=1.0.0
   ```

7. **`./.env.template`** - Environment variable template (as shown above)

8. **`./README.md`** - Documentation with:
   - Overview of the tool
   - Prerequisites and infrastructure requirements
   - Installation instructions
   - Configuration setup (copy .env.template to .env and fill in values)
   - Usage examples with command-line syntax
   - Troubleshooting common issues
   - Architecture overview

9. **`./logs/`** - Create logs directory (with .gitkeep)

</output>

<verification>

Before declaring the implementation complete, verify:

1. **Code Quality**
   - All classes have docstrings explaining purpose and methods
   - Type hints used for function parameters and return values
   - Follows PEP 8 style guidelines
   - No hardcoded credentials or sensitive data

2. **Error Handling**
   - Every external operation (API call, SSH command, file operation) wrapped in try-except
   - Specific exceptions caught (not bare `except:`)
   - All errors logged with context
   - Resources cleaned up in finally blocks

3. **Logging**
   - Log statements at appropriate levels (DEBUG/INFO/ERROR)
   - No sensitive data in logs
   - Logs include timestamps, device name, and operation context

4. **Configuration**
   - All configurable values in .env.template
   - No hardcoded IPs, credentials, or paths
   - Environment variables validated on startup

5. **Documentation**
   - README includes all necessary setup and usage information
   - Code comments explain WHY for complex logic
   - .env.template has clear descriptions for each variable

6. **Workflow Completeness**
   - All 6 steps from requirements are implemented
   - Serial number verification prevents wrong device configuration
   - Script handles both success and failure scenarios gracefully

</verification>

<success_criteria>

The script is successful when:

1. ✅ Can successfully connect to NetBox and retrieve device configuration
2. ✅ Creates configuration file on jump host FTP directory via SSH
3. ✅ Connects through terminal server pmshell to device console
4. ✅ Verifies device serial number before applying configuration
5. ✅ Successfully copies configuration file from FTP to device flash
6. ✅ Applies configuration to device running-config
7. ✅ Handles errors at each stage with meaningful messages and appropriate retries
8. ✅ Logs all operations with sufficient detail for troubleshooting
9. ✅ No hardcoded credentials - all secrets from environment variables
10. ✅ README provides clear instructions for setup and usage

The script should be ready to use in a production environment after installing dependencies and providing configuration via .env file.

</success_criteria>

<additional_guidance>

## Best Practices to Follow

- **Use context managers**: Use `with` statements for SSH connections to ensure proper cleanup
- **Parse command output**: Don't assume success - validate device responses
- **Progress indicators**: Print clear progress messages so users know what stage is executing
- **Timeout configuration**: Set appropriate timeouts (shorter for simple commands, longer for file transfers)
- **Dry-run mode**: Consider adding a `--dry-run` flag that validates inputs and connections without applying config

## Example Usage Pattern

```bash
# Setup
cp .env.template .env
# Edit .env with your credentials
vim .env

# Install dependencies
pip install -r requirements.txt

# Run provisioning
python zero_touch_provision.py --device-name router-01 --console-port 5

# With verbose logging
python zero_touch_provision.py --device-name router-01 --console-port 5 --log-level DEBUG
```

## Testing Considerations

While you don't need to write tests now, structure the code to be testable:
- Dependency injection for external services (pass NetBox client, SSH manager to orchestrator)
- Pure functions for parsing (show version output → serial number)
- Mock-friendly interfaces (abstract base classes for clients)

This will enable unit testing later if needed.

</additional_guidance>
