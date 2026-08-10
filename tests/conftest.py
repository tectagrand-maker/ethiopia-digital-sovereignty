import os
import pytest
from peewee import SqliteDatabase


@pytest.fixture(autouse=True)
def eds_test_db(tmp_path, monkeypatch):
    """Bind all models to an isolated temporary SQLite database for every test.

    Each test gets a fresh database file under the pytest tmp_path so the
    repository is never polluted with generated DB files. Raw-source writes are
    also redirected into the temporary directory.
    """
    import src.evidence.models as models
    import src.evidence.collection as collection

    # Redirect raw-source writes for tests into the temporary directory so
    # tests never leave artifacts under data/raw.
    raw_root = os.path.join(str(tmp_path), "raw")
    monkeypatch.setattr(collection, "RAW_ROOT", raw_root)
    os.makedirs(raw_root, exist_ok=True)

    db_path = os.path.join(str(tmp_path), "eds_test.db")
    test_db = SqliteDatabase(db_path)

    # Re-bind every model to the test database.
    models.db = test_db
    for model in (models.Source, models.Evidence,
                  models.GovernanceObservation, models.EvidenceObservation):
        model._meta.database = test_db

    test_db.connect()
    test_db.create_tables([
        models.Source, models.Evidence,
        models.GovernanceObservation, models.EvidenceObservation,
    ])

    yield test_db

    test_db.close()
