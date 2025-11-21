# Using UV with Zero Touch Provisioning

This guide shows how to use `uv` (the modern Python package installer) with the ZTP tool.

## What is UV?

`uv` is an extremely fast Python package installer and resolver, written in Rust. It's designed as a drop-in replacement for pip and pip-tools, offering:

- **10-100x faster** than pip
- Better dependency resolution
- Built-in virtual environment management
- Memory-efficient
- Cross-platform support

## Installation

### Install UV

**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Using pip (if you already have Python):**
```bash
pip install uv
```

**Verify installation:**
```bash
uv --version
```

## Quick Start with UV

### 1. Create Virtual Environment

```bash
# Create virtual environment in .venv directory
uv venv

# Activate the virtual environment
# Linux/macOS:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

### 2. Install Dependencies

**Option A: Install from requirements.txt (recommended - simplest)**
```bash
uv pip install -r requirements.txt
```

**Option B: Install from pyproject.toml in editable mode**
```bash
# Install setuptools first (required for building)
uv pip install setuptools

# Then install package in editable mode with all dependencies
uv pip install -e .

# This reads from pyproject.toml and installs:
# - pynetbox>=7.0.0
# - paramiko>=3.0.0
# - netmiko>=4.0.0
# - python-dotenv>=1.0.0
```

**Option C: Install with development dependencies**
```bash
# Install setuptools first
uv pip install setuptools

# Install with optional dev dependencies (pytest, black, mypy, etc.)
uv pip install -e ".[dev]"
```

### 3. Run the Tool

```bash
# After installation, you can run with uv run:
uv run zero_touch_provision.py --device-name router-01 --console-port 5

# Or if installed with -e flag, you can use the CLI command:
uv run ztp --device-name router-01 --console-port 5
```

## Common UV Commands

### Installing Packages

```bash
# Install a single package
uv pip install pynetbox

# Install specific version
uv pip install pynetbox==7.3.3

# Install multiple packages
uv pip install pynetbox paramiko netmiko

# Install from requirements file
uv pip install -r requirements.txt

# Install in editable mode (for development)
# Note: Install setuptools first if using editable mode
uv pip install setuptools
uv pip install -e .
```

### Managing Environments

```bash
# Create virtual environment
uv venv

# Create with specific Python version
uv venv --python 3.11

# Create in custom location
uv venv my-custom-env

# Remove virtual environment
rm -rf .venv  # or del .venv on Windows
```

### Listing Packages

```bash
# List installed packages
uv pip list

# Show package details
uv pip show pynetbox

# Check for outdated packages
uv pip list --outdated
```

### Updating Packages

```bash
# Update a specific package
uv pip install --upgrade pynetbox

# Update all packages
uv pip install --upgrade -r requirements.txt
```

### Uninstalling

```bash
# Uninstall a package
uv pip uninstall pynetbox

# Uninstall all packages
uv pip freeze | xargs uv pip uninstall -y
```

## UV vs PIP Comparison

| Feature | UV | PIP |
|---------|-------|-------|
| **Speed** | 10-100x faster | Standard |
| **Dependency Resolution** | Advanced, correct | Basic |
| **Virtual Environment** | Built-in (`uv venv`) | Requires separate venv module |
| **Caching** | Aggressive, efficient | Limited |
| **Memory Usage** | Low | Higher |
| **Installation** | Single binary | Python package |
| **Compatibility** | Drop-in replacement | Standard tool |

## Complete Setup Example

Here's a complete workflow from scratch:

```bash
# 1. Install uv (one-time setup)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone/download project
cd /path/to/zero-touch-provisioning

# 3. Create and activate virtual environment
uv venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\activate  # Windows

# 4. Install dependencies
# Recommended: Install from requirements.txt
uv pip install -r requirements.txt

# OR: Install as editable package (requires setuptools)
uv pip install setuptools
uv pip install -e .

# 5. Configure environment
cp .env.template .env
vim .env  # Add your credentials

# 6. Run the tool
uv run zero_touch_provision.py --device-name router-01 --console-port 5
```

## Troubleshooting

### ModuleNotFoundError: No module named 'setuptools.build_backend'

If you get this error when running `uv pip install -e .`, install setuptools first:

```bash
uv pip install setuptools
uv pip install -e .
```

Or simply use requirements.txt instead:

```bash
uv pip install -r requirements.txt
```

### UV command not found

After installation, you may need to restart your terminal or add uv to your PATH:

```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.cargo/bin:$PATH"

# Then reload
source ~/.bashrc  # or source ~/.zshrc
```

### Virtual environment not activating

Make sure you're in the project directory and the .venv folder exists:

```bash
ls -la .venv  # Should show the virtual environment directory
```

### Package installation fails

Try updating uv itself:

```bash
uv self update
```

Or clear the cache:

```bash
uv cache clean
```

### Python version issues

Specify Python version explicitly:

```bash
uv venv --python 3.11
# or
uv venv --python /usr/bin/python3.11
```

## Development Workflow

For developers contributing to the project:

```bash
# Install with development dependencies
uv pip install setuptools
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Format code
uv run black .

# Type checking
uv run mypy ztp/

# Linting
uv run flake8 ztp/
```

## Performance Comparison

Real-world example installing ZTP dependencies:

```
uv pip install -r requirements.txt
- Time: ~2-3 seconds
- Bandwidth efficient caching

pip install -r requirements.txt
- Time: ~30-45 seconds
- Downloads repeatedly
```

## Resources

- **UV Documentation**: https://github.com/astral-sh/uv
- **UV Installation Guide**: https://astral.sh/uv
- **Astral (makers of UV)**: https://astral.sh

## Migration from PIP

If you're currently using pip, migrating to uv is simple:

```bash
# Your existing pip workflow:
pip install -r requirements.txt

# Replace with uv:
uv pip install -r requirements.txt

# Everything else stays the same!
```

UV is a drop-in replacement, so all your existing requirements.txt, pyproject.toml, and pip commands work as-is.
