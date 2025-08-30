#!/bin/bash
# Script to run pytest with enhanced mock file detection to trace problematic tests

set -e

echo "Running tests with mock file detection enabled..."
echo ""

# Clean any existing mock files first
echo "Cleaning any existing mock files..."
uv run python tests/detect_mock_files.py --clean

# Function to test a single file or function
test_for_mock_files() {
    local test_spec=$1
    local indent=$2

    # Clean before test
    uv run python tests/detect_mock_files.py --clean 2>/dev/null || true

    # Run the test
    if uv run pytest "$test_spec" -q --tb=no 2>/dev/null; then
        # Check if mock files were created
        if ! uv run python tests/detect_mock_files.py --quiet 2>/dev/null; then
            echo "${indent}[ERROR] Mock files detected!"
            uv run python tests/detect_mock_files.py 2>/dev/null || true
            uv run python tests/detect_mock_files.py --clean 2>/dev/null || true
            return 1
        fi
    else
        echo "${indent}[WARNING] Test failed (may be unrelated to mock files)"
        return 2
    fi

    return 0
}

# Step 1: Find problematic directories
echo "Step 1: Checking test directories..."
PROBLEMATIC_DIRS=""

for test_dir in tests/unit tests/integration tests/cli tests/llm tests/utils; do
    if [ -d "$test_dir" ]; then
        echo "  Testing $test_dir..."
        if test_for_mock_files "$test_dir" "    "; then
            echo "    [OK] Clean"
        else
            PROBLEMATIC_DIRS="$PROBLEMATIC_DIRS $test_dir"
        fi
    fi
done

# Step 2: Narrow down to specific files
if [ -n "$PROBLEMATIC_DIRS" ]; then
    echo ""
    echo "Step 2: Identifying specific test files..."
    PROBLEMATIC_FILES=""

    # Clean any existing mock files from Step 1
    uv run python tests/detect_mock_files.py --clean 2>/dev/null || true

    for dir in $PROBLEMATIC_DIRS; do
        echo "  Checking files in $dir..."
        for test_file in $(find "$dir" -maxdepth 1 -name "test_*.py" -type f | sort); do
            echo "    Testing $test_file..."
            if ! test_for_mock_files "$test_file" "      "; then
                PROBLEMATIC_FILES="$PROBLEMATIC_FILES $test_file"

                # Step 3: Try to identify specific test functions
                echo ""
                echo "      Step 3: Identifying specific test functions in $test_file..."

                # Get list of test functions
                TEST_FUNCTIONS=$(uv run pytest "$test_file" --collect-only -q 2>/dev/null | grep "<Function" | sed 's/.*<Function \(.*\)>/\1/' || true)

                if [ -n "$TEST_FUNCTIONS" ]; then
                    for test_func in $TEST_FUNCTIONS; do
                        echo "        Testing $test_func..."
                        if ! test_for_mock_files "${test_file}::${test_func}" "          "; then
                            echo "          [WARNING] This test function creates mock files!"
                        fi
                    done
                else
                    echo "        Could not extract individual test functions"
                fi
                echo ""
            fi
        done
    done

    # Final report
    echo ""
    echo "Summary:"
    echo "[WARNING] Mock file artifacts detected!"

    if [ -n "$PROBLEMATIC_FILES" ]; then
        echo ""
        echo "Problematic test files:"
        for file in $PROBLEMATIC_FILES; do
            echo "  - $file"
        done
    fi

    echo ""
    echo "To fix: Check these files for:"
    echo "  1. MagicMock() created without spec parameter"
    echo "  2. Mock's database_path not set to a proper string/Path"
    echo "  3. Mock objects used directly as file paths"
    echo ""
    echo "Example fix:"
    echo "  mock_settings = MagicMock(spec=ScriptRAGSettings)"
    echo "  mock_settings.database_path = Path('/test/db.sqlite')"
else
    echo ""
    echo "Summary:"
    echo "[SUCCESS] No tests created mock file artifacts!"
fi

echo ""
echo "Mock file detection complete"
