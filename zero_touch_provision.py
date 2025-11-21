#!/usr/bin/env python3
"""
Zero Touch Provisioning (ZTP) Tool

This script automates the provisioning of network devices by:
1. Retrieving configuration from NetBox
2. Deploying configuration via FTP
3. Applying configuration through console access
4. Verifying device identity before configuration

Usage:
    python zero_touch_provision.py --device-name DEVICE_NAME --console-port PORT

Example:
    python zero_touch_provision.py --device-name router-01 --console-port 5

Environment variables must be configured in .env file.
See .env.template for required variables.
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: python-dotenv not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    from ztp import ProvisioningOrchestrator
    from ztp.orchestrator import ProvisioningError
except ImportError as e:
    print(f"ERROR: Failed to import ZTP modules: {e}")
    print("Ensure all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)


# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def setup_logging(log_level: str, log_file: Optional[str] = None) -> None:
    """
    Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
    """
    # Create logs directory if it doesn't exist
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    # Configure root logger
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Set up handlers
    handlers = []

    # Console handler with color support
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    handlers.append(console_handler)

    # File handler if log file specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        handlers.append(file_handler)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )

    # Suppress paramiko logging noise
    logging.getLogger('paramiko').setLevel(logging.WARNING)
    logging.getLogger('netmiko').setLevel(logging.WARNING)


def load_environment() -> dict:
    """
    Load and validate environment variables.

    Returns:
        Dictionary of environment variables

    Raises:
        ValueError: If required environment variables are missing
    """
    # Load .env file
    env_file = Path(__file__).parent / '.env'

    if not env_file.exists():
        print(f"{Colors.FAIL}ERROR: .env file not found!{Colors.ENDC}")
        print(f"\nPlease create .env file from template:")
        print(f"  cp .env.template .env")
        print(f"  vim .env  # Edit with your configuration")
        sys.exit(1)

    load_dotenv(env_file)

    # Required environment variables
    required_vars = [
        'NETBOX_URL',
        'NETBOX_TOKEN',
        'JUMPHOST_IP',
        'JUMPHOST_USERNAME',
        'JUMPHOST_PASSWORD',
        'TERMINAL_SERVER_IP',
        'TERMINAL_SERVER_USERNAME',
        'TERMINAL_SERVER_PASSWORD',
        'FTP_SERVER_IP',
        'FTP_USERNAME',
        'FTP_PASSWORD',
    ]

    # Validate required variables
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"{Colors.FAIL}ERROR: Missing required environment variables:{Colors.ENDC}")
        for var in missing_vars:
            print(f"  - {var}")
        print(f"\nPlease update your .env file with these variables.")
        sys.exit(1)

    # Return environment configuration
    return {
        'netbox_url': os.getenv('NETBOX_URL'),
        'netbox_token': os.getenv('NETBOX_TOKEN'),
        'jumphost_ip': os.getenv('JUMPHOST_IP'),
        'jumphost_username': os.getenv('JUMPHOST_USERNAME'),
        'jumphost_password': os.getenv('JUMPHOST_PASSWORD'),
        'terminal_server_ip': os.getenv('TERMINAL_SERVER_IP'),
        'terminal_server_username': os.getenv('TERMINAL_SERVER_USERNAME'),
        'terminal_server_password': os.getenv('TERMINAL_SERVER_PASSWORD'),
        'ftp_server_ip': os.getenv('FTP_SERVER_IP'),
        'ftp_username': os.getenv('FTP_USERNAME'),
        'ftp_password': os.getenv('FTP_PASSWORD'),
        'ftp_directory': os.getenv('FTP_DIRECTORY', '/srv/ftp'),
        'verify_ssl': os.getenv('VERIFY_SSL', 'true').lower() == 'true',
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'log_file': os.getenv('LOG_FILE', './logs/provisioning.log'),
    }


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Zero Touch Provisioning (ZTP) for Network Devices',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Provision device with default logging
  %(prog)s --device-name router-01 --console-port 5

  # Provision with verbose debug logging
  %(prog)s --device-name switch-02 --console-port 10 --log-level DEBUG

  # Dry run to validate configuration
  %(prog)s --device-name router-01 --console-port 5 --dry-run

Environment:
  Configuration is loaded from .env file in the current directory.
  See .env.template for required variables.
        """
    )

    parser.add_argument(
        '--device-name',
        required=True,
        help='Name of device to provision (must exist in NetBox)'
    )

    parser.add_argument(
        '--console-port',
        required=True,
        type=int,
        help='Console port number on terminal server'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (overrides .env LOG_LEVEL)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate configuration and connections without applying changes'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0'
    )

    return parser.parse_args()


def print_banner():
    """Print application banner."""
    banner = f"""
{Colors.OKCYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║        Zero Touch Provisioning (ZTP) Tool v1.0.0            ║
║        Network Device Automation                             ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.ENDC}
"""
    print(banner)


def print_summary(device_name: str, console_port: int, config: dict):
    """
    Print provisioning summary.

    Args:
        device_name: Device name
        console_port: Console port number
        config: Configuration dictionary
    """
    print(f"\n{Colors.BOLD}Provisioning Configuration:{Colors.ENDC}")
    print(f"  Device Name:      {Colors.OKBLUE}{device_name}{Colors.ENDC}")
    print(f"  Console Port:     {Colors.OKBLUE}{console_port}{Colors.ENDC}")
    print(f"  NetBox URL:       {config['netbox_url']}")
    print(f"  Jump Host:        {config['jumphost_ip']}")
    print(f"  Terminal Server:  {config['terminal_server_ip']}")
    print(f"  FTP Server:       {config['ftp_server_ip']}")
    print(f"  Log Level:        {config['log_level']}")
    print(f"  Log File:         {config['log_file']}")
    print()


def main() -> int:
    """
    Main entry point for the application.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Parse arguments
    args = parse_arguments()

    # Print banner
    print_banner()

    # Load environment configuration
    try:
        config = load_environment()
    except Exception as e:
        print(f"{Colors.FAIL}ERROR: Failed to load configuration: {e}{Colors.ENDC}")
        return 1

    # Override log level if specified
    if args.log_level:
        config['log_level'] = args.log_level

    # Setup logging
    setup_logging(config['log_level'], config['log_file'])
    logger = logging.getLogger(__name__)

    # Print summary
    print_summary(args.device_name, args.console_port, config)

    # Dry run mode
    if args.dry_run:
        print(f"{Colors.WARNING}DRY RUN MODE - No changes will be applied{Colors.ENDC}\n")
        logger.info("Running in dry-run mode")

        # TODO: Implement dry-run validation
        print(f"{Colors.WARNING}Dry-run mode not yet implemented{Colors.ENDC}")
        print("In dry-run mode, the tool would:")
        print("  1. Validate NetBox connectivity")
        print("  2. Verify device exists in NetBox")
        print("  3. Test SSH connectivity to jump host and terminal server")
        print("  4. Validate console port accessibility")
        print("  5. Show configuration preview without applying")
        return 0

    # Record start time
    start_time = datetime.now()

    # Initialize orchestrator
    try:
        print(f"{Colors.BOLD}Initializing provisioning orchestrator...{Colors.ENDC}\n")

        orchestrator = ProvisioningOrchestrator(
            device_name=args.device_name,
            console_port=args.console_port,
            netbox_url=config['netbox_url'],
            netbox_token=config['netbox_token'],
            jumphost_ip=config['jumphost_ip'],
            jumphost_username=config['jumphost_username'],
            jumphost_password=config['jumphost_password'],
            terminal_server_ip=config['terminal_server_ip'],
            terminal_server_username=config['terminal_server_username'],
            terminal_server_password=config['terminal_server_password'],
            ftp_server_ip=config['ftp_server_ip'],
            ftp_username=config['ftp_username'],
            ftp_password=config['ftp_password'],
            ftp_directory=config['ftp_directory'],
            verify_ssl=config['verify_ssl']
        )

    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")
        print(f"\n{Colors.FAIL}ERROR: Initialization failed: {e}{Colors.ENDC}")
        return 1

    # Execute provisioning
    try:
        print(f"{Colors.BOLD}Starting provisioning workflow...{Colors.ENDC}\n")

        success = orchestrator.provision_device()

        # Calculate duration
        duration = datetime.now() - start_time

        if success:
            print(f"\n{Colors.OKGREEN}{Colors.BOLD}SUCCESS!{Colors.ENDC}")
            print(f"{Colors.OKGREEN}Device '{args.device_name}' provisioned successfully{Colors.ENDC}")
            print(f"Duration: {duration}")
            print(f"\nStatus: {orchestrator.get_status()}")
            return 0
        else:
            print(f"\n{Colors.FAIL}{Colors.BOLD}FAILED!{Colors.ENDC}")
            print(f"{Colors.FAIL}Provisioning did not complete successfully{Colors.ENDC}")
            print(f"Duration: {duration}")
            print(f"\nStatus: {orchestrator.get_status()}")
            return 1

    except ProvisioningError as e:
        duration = datetime.now() - start_time
        logger.error(f"Provisioning error: {e}")
        print(f"\n{Colors.FAIL}{Colors.BOLD}PROVISIONING FAILED!{Colors.ENDC}")
        print(f"{Colors.FAIL}Error: {e}{Colors.ENDC}")
        print(f"Duration: {duration}")
        print(f"\nCheck logs for details: {config['log_file']}")
        return 1

    except KeyboardInterrupt:
        duration = datetime.now() - start_time
        logger.warning("Provisioning interrupted by user")
        print(f"\n{Colors.WARNING}Provisioning interrupted by user{Colors.ENDC}")
        print(f"Duration: {duration}")
        return 1

    except Exception as e:
        duration = datetime.now() - start_time
        logger.exception(f"Unexpected error: {e}")
        print(f"\n{Colors.FAIL}{Colors.BOLD}UNEXPECTED ERROR!{Colors.ENDC}")
        print(f"{Colors.FAIL}Error: {e}{Colors.ENDC}")
        print(f"Duration: {duration}")
        print(f"\nCheck logs for details: {config['log_file']}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
