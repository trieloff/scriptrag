#!/bin/bash
# Script to run pytest with enhanced mock file detection to trace problematic tests

set -e

echo "🔍 Running tests with mock file detection enabled..."
echo ""

# Clean any existing mock files first
echo "🧹 Cleaning any existing mock files..."
python tests/detect_mock_files.py --clean

# Run pytest with mock detection enabled
echo ""
echo "🧪 Running tests with tracking..."
echo ""

# Use pytest's verbose mode to show each test as it runs
# This helps correlate mock file creation with specific tests
pytest -v --track-mock-files --tb=short "$@"

# Check if any mock files remain after tests
echo ""
echo "🔍 Final check for mock files..."
python tests/detect_mock_files.py

echo ""
echo "✅ Mock file detection complete"
