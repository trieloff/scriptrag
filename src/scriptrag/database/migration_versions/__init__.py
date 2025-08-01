"""Database migrations package."""

from .base import Migration
from .v001_initial_schema import InitialSchemaMigration
from .v002_vector_storage import VectorStorageMigration
from .v003_fix_fts_columns import FixFTSColumnsMigration
from .v004_scene_dependencies import SceneDependenciesMigration
from .v005_script_bible import ScriptBibleMigration

__all__ = [
    "FixFTSColumnsMigration",
    "InitialSchemaMigration",
    "Migration",
    "SceneDependenciesMigration",
    "ScriptBibleMigration",
    "VectorStorageMigration",
]

# List of all migrations in order
MIGRATIONS = [
    InitialSchemaMigration,
    VectorStorageMigration,
    FixFTSColumnsMigration,
    SceneDependenciesMigration,
    ScriptBibleMigration,
]
