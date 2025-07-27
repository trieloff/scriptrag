# Bulk Import API Documentation

## Module: `scriptrag.parser.bulk_import`

The bulk import module provides functionality for importing multiple Fountain screenplay
files with automatic TV series detection and organization.

### Classes

#### `BulkImportResult`

Tracks results from a bulk import operation.

**Attributes:**

- `total_files` (int): Total number of files to import
- `successful_imports` (int): Number of successfully imported files
- `failed_imports` (int): Number of failed imports
- `skipped_files` (int): Number of skipped files
- `errors` (dict[str, str]): Mapping of file paths to error messages
- `imported_scripts` (dict[str, str]): Mapping of file paths to script IDs
- `series_created` (dict[str, str]): Mapping of series names to script IDs

**Methods:**

- `add_success(file_path: str, script_id: str)`: Record successful import
- `add_failure(file_path: str, error: str)`: Record failed import
- `add_skipped(file_path: str)`: Record skipped file
- `to_dict() -> dict[str, Any]`: Convert results to dictionary

#### `BulkImporter`

Main class for handling bulk imports of Fountain files.

**Constructor:**

```python
BulkImporter(
    graph_ops: GraphOperations,
    custom_pattern: str | None = None,
    skip_existing: bool = True,
    update_existing: bool = False,
    batch_size: int = 10
)
```

**Parameters:**

- `graph_ops`: GraphOperations instance for database access
- `custom_pattern`: Optional custom regex pattern for series detection
- `skip_existing`: Skip files that already exist in database
- `update_existing`: Update existing scripts if file is newer
- `batch_size`: Number of files to process per transaction batch

**Methods:**

##### `import_files()`

```python
def import_files(
    file_paths: list[Path],
    series_name_override: str | None = None,
    dry_run: bool = False,
    progress_callback: Callable[[float, str], None] | None = None
) -> BulkImportResult
```

Import multiple Fountain files.

**Parameters:**

- `file_paths`: List of Path objects to Fountain files
- `series_name_override`: Override auto-detected series name
- `dry_run`: Preview import without actually importing
- `progress_callback`: Optional callback for progress updates

**Returns:**

- `BulkImportResult` object with import statistics

**Example:**

```python
from pathlib import Path
from scriptrag.database.operations import GraphOperations
from scriptrag.parser.bulk_import import BulkImporter

# Create importer
importer = BulkImporter(
    graph_ops=graph_ops,
    skip_existing=True,
    batch_size=20
)

# Import files
files = list(Path("./scripts").glob("**/*.fountain"))
result = importer.import_files(
    file_paths=files,
    series_name_override="My Show",
    dry_run=False
)

print(f"Imported {result.successful_imports} files")
```

## Module: `scriptrag.parser.series_detector`

Provides TV series pattern detection from filenames and directory structures.

### Classes

#### `SeriesInfo`

Information extracted from a TV series script filename.

**Attributes:**

- `series_name` (str): Name of the TV series
- `season_number` (int | None): Season number if detected
- `episode_number` (int | None): Episode number if detected
- `episode_title` (str | None): Episode title if detected
- `is_series` (bool): Whether this is part of a series
- `is_special` (bool): Whether this is a special episode
- `multi_part` (str | None): Multi-part episode indicator

#### `SeriesPatternDetector`

Detects TV series patterns in filenames.

**Constructor:**

```python
SeriesPatternDetector(custom_pattern: str | None = None)
```

**Parameters:**

- `custom_pattern`: Optional custom regex pattern for detection

**Methods:**

##### `detect()`

```python
def detect(file_path: str | Path) -> SeriesInfo
```

Detect series information from a single file path.

**Parameters:**

- `file_path`: Path to the Fountain file

**Returns:**

- `SeriesInfo` object with extracted metadata

##### `detect_bulk()`

```python
def detect_bulk(file_paths: list[Path]) -> dict[Path, SeriesInfo]
```

Detect series information for multiple files.

**Parameters:**

- `file_paths`: List of Fountain file paths

**Returns:**

- Dictionary mapping file paths to their SeriesInfo

##### `group_by_series()`

```python
def group_by_series(
    series_infos: dict[Path, SeriesInfo]
) -> dict[str, list[tuple[Path, SeriesInfo]]]
```

Group files by series name.

**Parameters:**

- `series_infos`: Dictionary of file paths to SeriesInfo

**Returns:**

- Dictionary mapping series names to lists of (path, info) tuples

**Example:**

```python
from pathlib import Path
from scriptrag.parser.series_detector import SeriesPatternDetector

# Create detector
detector = SeriesPatternDetector()

# Detect single file
info = detector.detect("ShowName_S01E01_Pilot.fountain")
print(f"Series: {info.series_name}, S{info.season_number}E{info.episode_number}")

# Detect multiple files
files = list(Path("./scripts").glob("*.fountain"))
all_info = detector.detect_bulk(files)

# Group by series
grouped = detector.group_by_series(all_info)
for series_name, episodes in grouped.items():
    print(f"{series_name}: {len(episodes)} episodes")
```

### Supported Patterns

The detector supports these filename patterns out of the box:

1. **Underscore format**: `ShowName_S01E01_Title.fountain`
2. **X format**: `ShowName - 1x01 - Title.fountain`
3. **Dotted format**: `ShowName.101.Title.fountain`
4. **Episode number**: `ShowName - Episode 101 - Title.fountain`
5. **Simple format**: `ShowName S01E01.fountain`
6. **Special format**: `ShowName - Special - Title.fountain`

### Custom Patterns

You can provide custom regex patterns with named groups:

```python
# Custom pattern for "MyShow_Season01_Episode01.fountain"
detector = SeriesPatternDetector(
    custom_pattern=r"^(?P<series>.+?)_Season(?P<season>\d+)_Episode(?P<episode>\d+)"
)
```

Required named groups:

- `series`: Series name (optional, can be extracted from path)
- `season`: Season number (optional)
- `episode`: Episode number (optional)
- `title`: Episode title (optional)
