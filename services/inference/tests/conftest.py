import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    from threadline.testing import make_tiny_bundle

    bundle = make_tiny_bundle(tmp_path_factory.mktemp("bundle"))
    os.environ["BUNDLE_DIR"] = str(bundle)
    os.environ.pop("MODEL_URI", None)
    import importlib

    import app.settings

    importlib.reload(app.settings)
    import app.main

    importlib.reload(app.main)
    with TestClient(app.main.app) as c:
        c.bundle = bundle
        yield c
