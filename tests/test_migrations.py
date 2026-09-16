import subprocess
import sys


def test_migration_chain_widens_alembic_version_column():
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)" in result.stdout
