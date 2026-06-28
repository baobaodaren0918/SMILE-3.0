"""End-to-end coverage for the web server's /api/run_script and /api/inspect.

The canned-migration core path is covered by test_full_flow; this test covers
the HTTP glue of the user-script path (parse source -> parse SMILE -> apply ->
export -> validate) that previously had only a manual smoke script, plus the
"empty parse" guards added in the 2026-06-28 review.

A ThreadingHTTPServer is started on an ephemeral port so the test never
collides with a real instance on the default port.
"""
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from web_server import SMILEHandler

SOURCE_PG = """
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50)
);
"""

SCRIPT_SPECIFIC = """
EVOLUTION test_min:1.0
FROM RELATIONAL TO RELATIONAL
USING test_schema VERSION 1 TO 2

ADD_PROPERTY email TO users WITH TYPE String
"""


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("localhost", 0), SMILEHandler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://localhost:{port}"
    finally:
        httpd.shutdown()
        t.join(timeout=5)


def _post(base, path, payload):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_run_script_happy_path(server):
    out = _post(server, "/api/run_script", {
        "script": SCRIPT_SPECIFIC,
        "source_text": SOURCE_PG,
        "source_db_type": "relational",
        "target_db_type": "relational",
        "syntax": "specific",
    })
    assert out.get("ok") is True, out
    assert out["operations_total"] >= 1
    assert out["operations_applied"] >= 1
    assert out["source_entity_count"] == 1
    # the new property must reach the exported target
    assert "email" in out["exported_target"]
    # validation panel is present and uniform with /api/migrate
    assert "validation_layer0" in out
    assert "validation_blame" in out


def test_run_script_empty_source_is_reported(server):
    """A source that parses to 0 entities yields a clear error, not a green run."""
    out = _post(server, "/api/run_script", {
        "script": SCRIPT_SPECIFIC,
        "source_text": "-- just a comment, no tables\n",
        "source_db_type": "relational",
        "target_db_type": "relational",
        "syntax": "specific",
    })
    assert out.get("ok") is False, out
    assert "0 entities" in out.get("error", "")


def test_inspect_empty_input_emits_notice(server):
    out = _post(server, "/api/inspect", {
        "text": "-- nothing here\n",
        "db_type": "relational",
    })
    assert out.get("notice"), out
    assert "0 entities" in out["notice"]


def test_inspect_valid_input_has_no_notice(server):
    out = _post(server, "/api/inspect", {
        "text": SOURCE_PG,
        "db_type": "relational",
    })
    assert out.get("notice") is None, out
    assert out["summary"]["entity_count"] == 1