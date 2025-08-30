#!/bin/bash
# Script to run pytest with enhanced mock file detection to trace problematic tests

set -e

echo "🔍 Running tests with mock file detection enabled..."
echo ""

# Clean any existing mock files first
echo "🧹 Cleaning any existing mock files..."
uv run python tests/detect_mock_files.py --clean

# Run pytest with mock detection enabled
echo ""
echo "🧪 Running tests one by one to identify which creates mock files..."
echo ""

# Collect all test files
test_files=$(find tests -name "test_*.py" -type f | sort)

# Track which tests create mock files
problematic_tests=""

for test_file in $test_files; do
    echo "Testing: $test_file"

    # Clean before each test file
    uv run python tests/detect_mock_files.py --clean 2>/dev/null || true

    # Run the test file
    if uv run pytest "$test_file" -q --tb=no 2>/dev/null; then
        # Check if mock files were created
        if ! uv run python tests/detect_mock_files.py 2>/dev/null; then
            echo "  ⚠️  Mock files detected after $test_file"
            problematic_tests="$problematic_tests\n  - $test_file"

            # Clean up for next test
            uv run python tests/detect_mock_files.py --clean 2>/dev/null || true
        fi
    else
        echo "  ❌ Test failed (may be unrelated to mock files)"
    fi
done

# Final report
echo ""
echo "📊 Summary:"
if [ -z "$problematic_tests" ]; then
    echo "✅ No tests created mock file artifacts"
else
    echo "⚠️  The following test files created mock artifacts:"
    echo -e "$problematic_tests"
fi

echo ""
echo "✅ Mock file detection complete"
