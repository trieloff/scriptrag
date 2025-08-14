# Platform-Specific Setup Guide for ScriptRAG

This guide provides platform-specific setup instructions for developing and testing ScriptRAG on Windows, macOS, and Linux.

## Table of Contents

- [General Requirements](#general-requirements)
- [Windows Setup](#windows-setup)
- [macOS Setup](#macos-setup)
- [Linux Setup](#linux-setup)
- [CI/CD Configuration](#cicd-configuration)
- [Troubleshooting](#troubleshooting)

## General Requirements

### Python Version

- **Minimum**: Python 3.11
- **Recommended**: Python 3.12 or 3.13
- **Testing**: All versions should be tested in CI

### Core Dependencies

```bash
# Install uv package manager (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh  # Unix
# or
pip install uv  # All platforms

# Install development dependencies
uv pip install -e ".[dev]"
```

## Windows Setup

### Prerequisites

1. **Python Installation**

   ```bash
   # Using winget (Windows Package Manager)
   winget install Python.Python.3.12

   # Or download from python.org
   # Ensure "Add Python to PATH" is checked during installation
   ```

2. **Git Configuration**

   ```bash
   # Configure Git to handle line endings
   git config --global core.autocrlf true

   # For this repository specifically (recommended)
   cd scriptrag
   git config core.autocrlf input
   ```

3. **Long Path Support** (Administrator required)

   ```bash
   # Enable long path support for Windows 10/11
   New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
     -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
   ```

4. **Visual C++ Build Tools**
   - Required for some Python packages
   - Download from: <https://visualstudio.microsoft.com/visual-cpp-build-tools/>
   - Or install Visual Studio Community with C++ workload

### SQLite Vector Extension (Windows)

```bash
# Download pre-built DLL
curl -L -o vec0.dll https://github.com/asg017/sqlite-vec/releases/latest/download/vec0-windows-x86_64.dll

# Place in one of these locations:
# - Project root directory
# - Python Scripts directory: C:\Python312\Scripts\
# - System PATH directory

# Verify installation
python -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.enable_load_extension(True); conn.load_extension('vec0')"
```

### Environment Variables

```bash
# Set environment variables (PowerShell)
$env:SCRIPTRAG_DATABASE_PATH = "$HOME\scriptrag\scriptrag.db"
$env:SCRIPTRAG_LOG_LEVEL = "INFO"

# Permanent environment variables
[System.Environment]::SetEnvironmentVariable('SCRIPTRAG_DATABASE_PATH', "$HOME\scriptrag\scriptrag.db", 'User')
```

### Terminal Configuration

For better ANSI color support:

1. **Windows Terminal** (Recommended)

   ```bash
   winget install Microsoft.WindowsTerminal
   ```

2. **PowerShell 7+** (Recommended)

   ```bash
   winget install Microsoft.PowerShell
   ```

3. **Enable ANSI in CMD** (Legacy)

   ```bash
   reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1
   ```

## macOS Setup

### Prerequisites

1. **Homebrew Installation**

   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **Python Installation**

   ```bash
   # Using Homebrew
   brew install python@3.12

   # Or using pyenv for multiple versions
   brew install pyenv
   pyenv install 3.12.0
   pyenv global 3.12.0
   ```

3. **Development Tools**

   ```bash
   # Install Xcode Command Line Tools
   xcode-select --install
   ```

### SQLite Vector Extension (macOS)

```bash
# Intel Mac
curl -L -o vec0.dylib https://github.com/asg017/sqlite-vec/releases/latest/download/vec0-macos-x86_64.dylib

# Apple Silicon (M1/M2)
curl -L -o vec0.dylib https://github.com/asg017/sqlite-vec/releases/latest/download/vec0-macos-aarch64.dylib

# Install to standard location
sudo cp vec0.dylib /usr/local/lib/
sudo chmod 755 /usr/local/lib/vec0.dylib

# Verify installation
python3 -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.enable_load_extension(True); conn.load_extension('vec0')"
```

### Case Sensitivity

macOS uses a case-insensitive filesystem by default:

```bash
# Check if filesystem is case-sensitive
touch test.txt Test.txt
ls test.txt Test.txt
# If only one file is listed, filesystem is case-insensitive

# Create case-sensitive volume (optional, for testing)
diskutil apfs addVolume disk1 "Case-sensitive APFS" CaseSensitive
```

### Environment Variables

```bash
# Add to ~/.zshrc or ~/.bash_profile
export SCRIPTRAG_DATABASE_PATH="$HOME/scriptrag/scriptrag.db"
export SCRIPTRAG_LOG_LEVEL="INFO"

# Apply changes
source ~/.zshrc
```

## Linux Setup

### Prerequisites

1. **Python Installation**

   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3.12 python3.12-venv python3.12-dev

   # Fedora/RHEL
   sudo dnf install python3.12 python3.12-devel

   # Arch Linux
   sudo pacman -S python
   ```

2. **Build Dependencies**

   ```bash
   # Ubuntu/Debian
   sudo apt install build-essential libsqlite3-dev

   # Fedora/RHEL
   sudo dnf groupinstall "Development Tools"
   sudo dnf install sqlite-devel

   # Arch Linux
   sudo pacman -S base-devel sqlite
   ```

### SQLite Vector Extension (Linux)

```bash
# Download for your architecture
# x86_64
curl -L -o vec0.so https://github.com/asg017/sqlite-vec/releases/latest/download/vec0-linux-x86_64.so

# ARM64
curl -L -o vec0.so https://github.com/asg017/sqlite-vec/releases/latest/download/vec0-linux-aarch64.so

# Install system-wide
sudo cp vec0.so /usr/local/lib/
sudo chmod 755 /usr/local/lib/vec0.so
sudo ldconfig

# Or install locally
mkdir -p ~/.local/lib
cp vec0.so ~/.local/lib/
export LD_LIBRARY_PATH="$HOME/.local/lib:$LD_LIBRARY_PATH"

# Verify
python3 -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.enable_load_extension(True); conn.load_extension('vec0')"
```

### File Permissions

```bash
# Ensure proper permissions for development
chmod 755 ~/.local/bin/*
chmod 644 ~/.config/scriptrag/*

# For shared development
umask 002  # Group-writable files
```

### Environment Variables

```bash
# Add to ~/.bashrc or ~/.zshrc
export SCRIPTRAG_DATABASE_PATH="$HOME/scriptrag/scriptrag.db"
export SCRIPTRAG_LOG_LEVEL="INFO"
export LD_LIBRARY_PATH="$HOME/.local/lib:$LD_LIBRARY_PATH"

# Apply changes
source ~/.bashrc
```

## CI/CD Configuration

### GitHub Actions Matrix

```yaml
name: Cross-Platform Tests

on: [push, pull_request]

jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ["3.11", "3.12", "3.13"]
        include:
          # Specific configurations
          - os: ubuntu-latest
            python-version: "3.12"
            coverage: true
        exclude:
          # Skip certain combinations
          - os: macos-latest
            python-version: "3.11"

    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e ".[dev]"

      - name: Platform-specific setup
        shell: bash
        run: |
          if [[ "$RUNNER_OS" == "Windows" ]]; then
            echo "Setting up Windows environment"
            # Windows-specific setup
          elif [[ "$RUNNER_OS" == "macOS" ]]; then
            echo "Setting up macOS environment"
            # macOS-specific setup
          else
            echo "Setting up Linux environment"
            # Linux-specific setup
          fi

      - name: Run tests
        run: |
          make test
```

### Platform-Specific Test Execution

```bash
# Run tests with platform-specific markers
# Windows-only tests
pytest -m "windows" tests/

# Unix-only tests (Linux/macOS)
pytest -m "unix" tests/

# Skip slow tests on CI
SCRIPTRAG_TEST_SKIP_SLOW=1 pytest tests/
```

## Troubleshooting

### Windows Issues

#### PowerShell Execution Policy

```bash
# If scripts won't run
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### ANSI Colors Not Working

```bash
# Check if ANSI is enabled
[Console]::OutputEncoding
# Should show UTF-8 encoding

# Enable in registry
reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1 /f
```

#### Path Too Long Errors

```bash
# Check if long paths are enabled
(Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem").LongPathsEnabled

# If 0, enable with admin rights
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1
```

### macOS Issues

#### SSL Certificate Errors

```bash
# Install certificates for Python
/Applications/Python\ 3.12/Install\ Certificates.command

# Or manually
pip install --upgrade certifi
```

#### Homebrew Python vs System Python

```bash
# Ensure using Homebrew Python
which python3
# Should show /opt/homebrew/bin/python3 (Apple Silicon) or /usr/local/bin/python3 (Intel)

# Fix PATH if needed
export PATH="/opt/homebrew/bin:$PATH"  # Apple Silicon
export PATH="/usr/local/bin:$PATH"     # Intel
```

### Linux Issues

#### Permission Denied Errors

```bash
# Fix script permissions
chmod +x scripts/*.sh

# Fix Python package permissions
pip install --user --force-reinstall package_name
```

#### Missing SQLite Features

```bash
# Check SQLite version
sqlite3 --version

# Need version 3.35+ for certain features
# Ubuntu/Debian - add PPA for newer version
sudo add-apt-repository ppa:sergey-dryabzhinsky/packages
sudo apt update
sudo apt install sqlite3
```

### Common Cross-Platform Issues

#### Different Temp Directories

```python
# Always use Python's tempfile module
import tempfile
temp_dir = tempfile.gettempdir()
# Returns appropriate directory for each platform
```

#### File Locking Differences

```python
# Windows has mandatory locking, Unix has advisory
# Always close files properly
with open(file_path, 'r') as f:
    content = f.read()
# File automatically closed
```

#### Unicode Handling

```python
# Always specify encoding
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()
```

## Testing Your Setup

Run the platform compatibility test suite:

```bash
# Run all platform tests
pytest tests/unit/test_cross_platform.py -v

# Check your platform configuration
python -c "from tests.platform_utils import get_platform_info; import json; print(json.dumps(get_platform_info(), indent=2))"

# Verify SQLite extensions
python -c "from tests.platform_utils import check_sqlite_extension_support; print('Vector extension available:', check_sqlite_extension_support('vec0'))"
```

## Additional Resources

- [Python on Windows Documentation](https://docs.python.org/3/using/windows.html)
- [Python on macOS Documentation](https://docs.python.org/3/using/mac.html)
- [SQLite Vector Extension](https://github.com/asg017/sqlite-vec)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Cross-Platform Python Development](https://realpython.com/cross-platform-python/)

---

*Last updated: 2025-08-14*
