"""SMILE Web Server - Web interface for schema migration visualization."""
import sys
import json
import re
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs
import threading
import webbrowser

sys.path.insert(0, str(Path(__file__).parent))

from core import run_migration, db_to_dict
from config import (
    MIGRATION_CONFIGS, DB_TYPE_EXPORT_LABEL, NORTHWIND_SCHEMA_FILES,
    PRODUCT_TO_SOURCE_TYPE,
)
from schema_inspector import inspect_schema, _resolve_db_type
from Schema.adapters import ADAPTER_REGISTRY

PORT = 5601


class SMILEHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for SMILE web interface."""

    def _send_json(self, obj, status=200, cache_control=None):
        """Send a JSON response with the shared CORS header."""
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        if cache_control:
            self.send_header('Cache-Control', cache_control)
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def do_GET(self):
        try:
            if self.path == '/' or self.path == '/index.html':
                content = get_html().encode('utf-8')
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
                self.wfile.write(content)
            elif self.path.startswith('/static/'):
                # Path traversal is blocked: only basename + safe extensions allowed.
                rel = self.path[len('/static/'):].split('?')[0].split('#')[0]
                if '..' in rel or rel.startswith('/') or '\\' in rel:
                    self.send_response(404); self.end_headers(); return
                fpath = Path(__file__).parent / 'static' / rel
                if not fpath.is_file():
                    self.send_response(404); self.end_headers(); return
                ext = fpath.suffix.lower()
                ctype = {'.js':'application/javascript','.css':'text/css',
                         '.json':'application/json','.html':'text/html'}.get(ext, 'application/octet-stream')
                data = fpath.read_bytes()
                self.send_response(200)
                self.send_header('Content-type', ctype)
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(data)
            elif self.path.startswith('/api/schemas'):
                # Return raw text + parsed Meta V1 per schema file so the Source
                # Schemas tab renders dynamically and never disagrees with disk.
                result = {"parsed": {}}
                for key, fpath in NORTHWIND_SCHEMA_FILES.items():
                    try:
                        result[key] = fpath.read_text(encoding='utf-8')
                    except Exception as e:
                        result[key] = f'Error reading {fpath}: {e}'
                        continue
                    src_type = PRODUCT_TO_SOURCE_TYPE.get(key)
                    adapter_cls = ADAPTER_REGISTRY.get(src_type) if src_type else None
                    if adapter_cls is None:
                        continue
                    try:
                        db = adapter_cls().load_from_file(str(fpath), key)
                        result["parsed"][key] = db_to_dict(db)
                    except Exception as e:
                        result["parsed"][key] = {"__error": f'parse failed: {e}'}

                self._send_json(result, cache_control='no-cache')
            elif self.path == '/api/operations_spec':
                spec_path = Path(__file__).parent / 'grammar' / 'smile_operations.json'
                try:
                    payload = json.loads(spec_path.read_text(encoding='utf-8'))
                except Exception as e:
                    payload = {"error": str(e)}
                self._send_json(payload, cache_control='no-cache')
            elif self.path.startswith('/api/migrate'):
                query = self.path.split('?')[1] if '?' in self.path else ''
                params = parse_qs(query)
                direction = params.get('direction', ['northwind_r2d_generalized'])[0]

                try:
                    result = run_migration(direction)
                except Exception as e:
                    result = {"error": f"Migration failed: {e}"}

                self._send_json(result, cache_control='no-cache')
            else:
                super().do_GET()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass  # Browser closed connection early — harmless on Windows

    def do_POST(self):
        try:
            if self.path == '/api/inspect':
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                content_type = self.headers.get('Content-Type', '')

                try:
                    if 'multipart/form-data' in content_type:
                        text, db_type = _parse_multipart_inspect(body, content_type)
                    else:
                        data = json.loads(body.decode('utf-8'))
                        text = data.get('text', '')
                        db_type = data.get('db_type', '')
                    result = inspect_schema(text, db_type, input_mode="text")

                    self._send_json(result)
                except Exception as e:
                    self._send_json({"error": str(e)})
            elif self.path == '/api/run_script':
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                try:
                    data = json.loads(body.decode('utf-8'))
                    script_text = data.get('script', '')
                    source_text = data.get('source_text', '')
                    source_db_type = data.get('source_db_type', '')
                    target_db_type = data.get('target_db_type', '')
                    syntax = data.get('syntax', 'specific')
                    if not script_text:
                        raise ValueError("script is required")
                    if not source_text:
                        raise ValueError("source_text is required (paste/upload a source schema first)")
                    if not source_db_type:
                        raise ValueError("source_db_type is required")
                    if not target_db_type:
                        raise ValueError("target_db_type is required")

                    src_db = _parse_schema_text(source_text, source_db_type, name='source')
                    src_count = len(src_db.entity_types)
                    # Adapters tolerate unrecognised input by returning an empty
                    # Database rather than raising. Catch that here so the user
                    # gets a clear "nothing parsed" message instead of a
                    # confusing all-green run over zero entities.
                    if src_count == 0:
                        raise ValueError(
                            "The source schema parsed to 0 entities. Check that the "
                            "pasted/uploaded text is valid and matches the selected "
                            f"source database type ({source_db_type}).")

                    from antlr4 import InputStream, CommonTokenStream, ParseTreeWalker
                    from parser.factory import get_parser_components, SyntaxErrorListener
                    from parser.listeners import SMILESpecificListener, SMILEGeneralizedListener
                    grammar = 'generalized' if syntax == 'generalized' else 'specific'
                    LexerClass, ParserClass, _ = get_parser_components(grammar)
                    ListenerCls = SMILEGeneralizedListener if grammar == 'generalized' else SMILESpecificListener
                    stream = InputStream(script_text)
                    lexer = LexerClass(stream)
                    tokens = CommonTokenStream(lexer)
                    parser = ParserClass(tokens)
                    err = SyntaxErrorListener(grammar)
                    lexer.removeErrorListeners(); lexer.addErrorListener(err)
                    parser.removeErrorListeners(); parser.addErrorListener(err)
                    tree = parser.migration()
                    if err.errors:
                        # Parse failed: emit ``unverifiable`` placeholders so the
                        # frontend gets a consistent validation_* shape across endpoints.
                        skipped = {"passed": None,
                                   "summary": "Other reasons (parse failed)",
                                   "details": {}}
                        skipped_integrity = {"passed": None,
                                             "summary": "Other reasons (parse failed)",
                                             "violations": []}
                        result = {
                            "ok": False, "errors": err.errors, "stage": "parse",
                            "validation_layer0": skipped,
                            "validation_meta": skipped,
                            "validation_export": skipped,
                            "validation_text_diff": skipped,
                            "validation_integrity": skipped_integrity,
                            "validation_blame": "unverifiable",
                            "validation_summary": "SMILE parse failed",
                        }
                    else:
                        listener = ListenerCls()
                        walker = ParseTreeWalker()
                        walker.walk(listener, tree)
                        operations = listener.operations
                        # Reuse run_migration()'s apply/export helpers so the canned
                        # and Run-button paths share one implementation.
                        from core import SchemaTransformer, run_apply, run_export
                        # Resolve the target model up front so target-model guards
                        # apply here too (e.g. NEST is document-only).
                        tgt_type_resolved = _resolve_db_type(target_db_type)
                        transformer = SchemaTransformer(src_db, target_type=tgt_type_resolved)
                        ops_detail, applied, skipped_ct, error_ct = run_apply(transformer, operations)
                        # Surface deliberate skips and handler errors as separate
                        # fields; conflating them would hide real defects (a handler
                        # bug would masquerade as a harmless "skipped" step).
                        skipped = [f"step {d['step']}: {d['type']}" for d in ops_detail
                                   if d['status'] == 'skipped']
                        errors = [f"step {d['step']}: {d['type']} — {d.get('reason', '')}"
                                  for d in ops_detail if d['status'] == 'error']

                        try:
                            result_db, exported_text, _ = run_export(
                                transformer,
                                _resolve_db_type(source_db_type),
                                tgt_type_resolved)
                            if not isinstance(exported_text, str):
                                # The Document adapter returns a dict → JSON-stringify.
                                # (Graph now exports a GraphQL SDL string.)
                                exported_text = json.dumps(exported_text, indent=2, ensure_ascii=False)
                        except Exception as ex:
                            result_db = transformer.database
                            exported_text = f"-- export() raised: {ex}\n"

                        from schema_inspector import _build_summary
                        meta_v2_summary = _build_summary(result_db)

                        # Run the same validation as /api/migrate for an identical
                        # response shape. User-pasted scripts have no ground-truth
                        # target file, so ``unverifiable`` is the legitimate (and
                        # still useful) verdict, letting the panel render uniformly.
                        from core import db_to_dict
                        # Layer 0 needs ``execution_stats`` + ``operations_detail`` to
                        # derive its verdict; without them it would pass on a zero-op
                        # assumption, hiding genuine handler errors/skips.
                        validation_input = {
                            "result": db_to_dict(result_db),
                            "exported_target": exported_text,
                            "execution_stats": {
                                "total": len(operations),
                                "success": applied,
                                "skipped": skipped_ct,
                                "error": error_ct,
                            },
                            "operations_detail": ops_detail,
                            # Live Database for the Layer-0.5 integrity scan;
                            # validate_pipeline consumes and drops it before serialization.
                            "__result_db": result_db,
                        }
                        try:
                            from validation.pipeline import validate_pipeline
                            v = validate_pipeline(
                                validation_input, tgt_type_resolved, config_key="")
                            validation_layer0 = v["layer0"]
                            validation_meta = v["layer1"]
                            validation_export = v["layer2"]
                            validation_text_diff = v["layer3"]
                            validation_integrity = v["integrity"]
                            validation_blame = v["blame"]
                            validation_summary = v["summary"]
                        except Exception as ex:
                            err_block = {"passed": None,
                                         "summary": f"Error: {ex}",
                                         "details": {}}
                            err_block_integrity = {"passed": None,
                                                   "summary": f"Error: {ex}",
                                                   "violations": []}
                            validation_layer0 = err_block
                            validation_meta = err_block
                            validation_export = err_block
                            validation_text_diff = err_block
                            validation_integrity = err_block_integrity
                            validation_blame = "unverifiable"
                            validation_summary = f"validation crashed: {ex}"

                        result = {
                            "ok": True, "stage": "run",
                            "operations_total": len(operations),
                            "operations_applied": applied,
                            "operations_skipped": skipped,
                            "operations_errors": errors,
                            "source_entity_count": src_count,
                            "result_entity_count": len(result_db.entity_types),
                            "meta_v2_summary": meta_v2_summary,
                            "exported_target": exported_text,
                            "target_db_type": tgt_type_resolved.upper(),
                            "validation_layer0": validation_layer0,
                            "validation_meta": validation_meta,
                            "validation_export": validation_export,
                            "validation_text_diff": validation_text_diff,
                            "validation_integrity": validation_integrity,
                            "validation_blame": validation_blame,
                            "validation_summary": validation_summary,
                        }
                    self._send_json(result)
                except Exception as e:
                    self._send_json({"ok": False, "error": str(e), "stage": "exception"})
            elif self.path == '/api/validate_script':
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                try:
                    data = json.loads(body.decode('utf-8'))
                    text = data.get('text', '')
                    syntax = data.get('syntax', 'specific')
                    errors = _validate_smile_text(text, syntax)
                    result = {"errors": errors, "ok": len(errors) == 0}
                    self._send_json(result)
                except Exception as e:
                    self._send_json({"error": str(e)})
            elif self.path == '/api/generate_script':
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                try:
                    data = json.loads(body.decode('utf-8'))
                    src_type = data.get('source_db_type', '')
                    tgt_type = data.get('target_db_type', '')
                    kind = (data.get('kind') or 'auto').lower()  # 'migration'|'evolution'|'auto'
                    if not (src_type and tgt_type):
                        raise ValueError("source_db_type and target_db_type are required")

                    src_token = _smile_db_token(src_type)
                    tgt_token = _smile_db_token(tgt_type)
                    if kind == 'auto':
                        is_evolution = (src_token == tgt_token)
                    else:
                        is_evolution = (kind == 'evolution')
                    migration_name = data.get('migration_name') or 'generated'
                    schema_name = data.get('schema_name') or 'generated_schema'
                    version = data.get('version') or '1.0'
                    schema_version_to = data.get('schema_version_to') or '2.0'

                    from script_renderer import render_header_only
                    spec_text = render_header_only(
                        src_token, tgt_token,
                        kind=('evolution' if is_evolution else 'migration'),
                        migration_name=migration_name,
                        schema_name=schema_name, version=version,
                        schema_version_to=schema_version_to,
                        syntax='specific')
                    gen_text = render_header_only(
                        src_token, tgt_token,
                        kind=('evolution' if is_evolution else 'migration'),
                        migration_name=migration_name,
                        schema_name=schema_name, version=version,
                        schema_version_to=schema_version_to,
                        syntax='generalized')

                    result = {
                        "specific_script": spec_text,
                        "generalized_script": gen_text,
                        "is_evolution": is_evolution,
                        "source_token": src_token,
                        "target_token": tgt_token,
                        "kind": "evolution" if is_evolution else "migration",
                    }
                    self._send_json(result)
                except Exception as e:
                    self._send_json({"error": str(e)})
            else:
                self.send_response(404)
                self.end_headers()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def log_message(self, format, *args):
        pass


def _parse_schema_text(text: str, db_type: str, name: str):
    """Parse raw schema text into a Database object using the appropriate adapter."""
    resolved = _resolve_db_type(db_type)
    adapter_cls = ADAPTER_REGISTRY.get(resolved)
    if not adapter_cls:
        raise ValueError(f"No adapter for db_type: {resolved}")
    adapter = adapter_cls()
    key = resolved.lower()
    if key == 'document':
        return adapter.parse(json.loads(text), name)
    if key == 'graph':
        stripped = text.strip()
        if stripped.startswith('{') or stripped.startswith('['):
            return adapter.parse(json.loads(text), name)
        return adapter.parse(text, name)
    return adapter.parse(text, name)


def _parse_multipart_inspect(body: bytes, content_type: str):
    """Manually parse multipart/form-data for /api/inspect (cgi removed in 3.13)."""
    boundary = None
    for piece in content_type.split(';'):
        piece = piece.strip()
        if piece.lower().startswith('boundary='):
            boundary = piece.split('=', 1)[1].strip().strip('"')
            break
    if not boundary:
        raise ValueError("multipart upload missing boundary")
    delim = ('--' + boundary).encode()
    parts = body.split(delim)
    text = ''
    db_type = ''
    for part in parts:
        if not part or part in (b'--\r\n', b'--'):
            continue
        part = part.lstrip(b'\r\n')
        head_end = part.find(b'\r\n\r\n')
        if head_end < 0:
            continue
        headers_blob = part[:head_end].decode('utf-8', errors='replace')
        payload = part[head_end + 4:]
        if payload.endswith(b'\r\n'):
            payload = payload[:-2]
        m = re.search(r'name="([^"]+)"', headers_blob)
        if not m:
            continue
        name = m.group(1)
        if name == 'db_type':
            db_type = payload.decode('utf-8', errors='replace').strip()
        elif name == 'file':
            text = payload.decode('utf-8', errors='replace')
    return text, db_type


def _validate_smile_text(text: str, syntax: str) -> list:
    """Parse SMILE text with the requested grammar and return a list of error strings."""
    from io import StringIO
    from antlr4 import InputStream, CommonTokenStream
    from parser.factory import get_parser_components, SyntaxErrorListener
    LexerClass, ParserClass, _ = get_parser_components(
        'generalized' if syntax == 'generalized' else 'specific'
    )
    input_stream = InputStream(text or '')
    lexer = LexerClass(input_stream)
    err = SyntaxErrorListener(syntax)
    # Attach to BOTH lexer and parser so lexer-level errors (illegal chars /
    # unrecognised tokens) are also caught, matching parse_smile_auto.
    lexer.removeErrorListeners()
    lexer.addErrorListener(err)
    token_stream = CommonTokenStream(lexer)
    parser = ParserClass(token_stream)
    parser.removeErrorListeners()
    parser.addErrorListener(err)
    parser.migration()
    return err.errors


def _smile_db_token(db_type: str) -> str:
    """Map adapter db_type strings to the SMILE header token."""
    return _resolve_db_type(db_type).upper()


def _build_dropdown_options() -> str:
    """Generate <optgroup>/<option> HTML tags from MIGRATION_CONFIGS (Northwind only)."""
    nw_evo, nw_cross = [], []
    for key, cfg in MIGRATION_CONFIGS.items():
        if not key.startswith("northwind_"):
            continue
        display = cfg.display_name
        selected = ' selected' if key == "northwind_r2d_generalized" else ''
        tag = f'<option value="{key}"{selected}>{display}</option>'
        if cfg.source_type == cfg.target_type:
            nw_evo.append(tag)
        else:
            nw_cross.append(tag)
    nl = '\n                        '
    html = ''
    if nw_evo:
        html += f'<optgroup label="Northwind (Schema Evolution)">{nl}{nl.join(nw_evo)}{nl}</optgroup>'
    if nw_cross:
        html += f'\n                    <optgroup label="Northwind (Cross-Model Migration)">{nl}{nl.join(nw_cross)}{nl}</optgroup>'
    return html


def _build_config_js() -> str:
    """Generate JavaScript constant for DB_TYPE_EXPORT_LABEL from config.py."""
    return f"const DB_TYPE_EXPORT_LABEL = {json.dumps(DB_TYPE_EXPORT_LABEL)};"


def get_html():
    """Return the HTML page with Apple-style design."""
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>SMILE - Schema Migration Viewer</title>
    <script src="https://cdn.jsdelivr.net/npm/@viz-js/viz@3/lib/viz-standalone.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/ace-builds@1.32.6/src-min-noconflict/ace.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/ace-builds@1.32.6/src-min-noconflict/ext-language_tools.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
            background: #FFFFFF;
            min-height: 100vh;
            color: #1D1D1F;
            -webkit-font-smoothing: antialiased;
        }

        .header {
            background: #FFFFFF;
            border-bottom: 1px solid #E8E8ED;
            padding: 32px 48px;
            position: sticky;
            top: 0;
            z-index: 100;
            text-align: center;
        }

        .header h1 { font-size: 28px; font-weight: 600; color: #1D1D1F; letter-spacing: -0.3px; }
        .header p { font-size: 14px; color: #636366; margin-top: 8px; }

        .controls {
            display: flex;
            align-items: center;
            gap: 24px;
            padding: 24px 48px;
            background: #FFFFFF;
            border-bottom: 1px solid #E8E8ED;
        }

        .control-group { display: flex; align-items: center; gap: 12px; }
        .control-label { font-size: 15px; font-weight: 500; color: #636366; }

        .dropdown { position: relative; min-width: 380px; }
        .dropdown select {
            width: 100%;
            padding: 12px 44px 12px 16px;
            border: 1px solid #E8E8ED;
            border-radius: 12px;
            background: #F5F5F7;
            font-size: 15px;
            font-weight: 500;
            color: #1D1D1F;
            cursor: pointer;
            appearance: none;
            transition: all 0.2s;
        }
        .dropdown select:hover { border-color: #0066CC; }
        .dropdown select:focus { outline: none; border-color: #0066CC; }
        .dropdown select optgroup { font-weight: 600; font-size: 13px; color: #636366; }
        .dropdown select option { font-weight: 400; font-size: 14px; color: #1D1D1F; padding: 4px 8px; }
        .dropdown::after {
            content: '';
            position: absolute;
            right: 16px;
            top: 50%;
            transform: translateY(-50%);
            border: 5px solid transparent;
            border-top-color: #636366;
            pointer-events: none;
        }

        .run-btn {
            padding: 12px 28px;
            background: #0066CC;
            border: none;
            border-radius: 12px;
            color: white;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .run-btn:hover { background: #0055AA; }

        .tab-nav {
            display: none;
            gap: 0;
            padding: 0 48px;
            background: #FFFFFF;
            border-bottom: 1px solid #E8E8ED;
        }
        .tab-nav.show { display: flex; }

        .tab-btn {
            padding: 16px 28px;
            background: none;
            border: none;
            font-size: 15px;
            font-weight: 500;
            color: #636366;
            cursor: pointer;
            position: relative;
            transition: all 0.2s;
        }
        .tab-btn:hover { color: #1D1D1F; }
        .tab-btn.active { color: #0066CC; }
        .tab-btn.active::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: #0066CC;
        }

        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .loading {
            display: none;
            padding: 120px 48px;
            text-align: center;
            color: #636366;
        }
        .loading.show { display: block; }
        .loading .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid #E8E8ED;
            border-top-color: #0066CC;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .welcome { padding: 160px 48px; text-align: center; }
        .welcome h2 { font-size: 28px; color: #1D1D1F; margin-bottom: 12px; font-weight: 600; }
        .welcome p { font-size: 17px; color: #636366; }

        .schema-compare {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1px;
            background: #E8E8ED;
            min-height: calc(100vh - 200px);
        }

        .schema-panel { background: #FFFFFF; padding: 32px; overflow-y: auto; }

        .panel-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 32px;
        }
        .panel-title { font-size: 22px; font-weight: 600; color: #1D1D1F; }

        .schema-badge {
            padding: 6px 14px;
            border-radius: 16px;
            font-size: 13px;
            font-weight: 600;
            background: #F5F5F7;
            color: #636366;
        }
        .schema-badge.relational { background: #F5F5F7; color: #0066CC; }
        .schema-badge.document { background: #F5F5F7; color: #BF4800; }
        .schema-badge.graph { background: #F5F5F7; color: #34A853; }
        .schema-badge.columnar { background: #F5F5F7; color: #8E24AA; }

        .er-section { margin-bottom: 40px; }
        .section-title {
            font-size: 13px;
            font-weight: 600;
            color: #636366;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 16px;
        }

        .er-diagram {
            background: #F5F5F7;
            border-radius: 16px;
            padding: 24px;
            min-height: 300px;
            overflow: auto;
        }
        .er-diagram svg { display: block; margin: 0 auto; max-width: 100%; height: auto; }
        .er-dot-container { min-height: 200px; display: flex; align-items: center; justify-content: center; }

        /* Graph SVG Circular Layout */
        .graph-svg-container { display: flex; justify-content: center; padding: 8px 0; }
        .graph-svg-container svg { max-height: 600px; }
        /* Compact graph in 4-column target column */
        .graph-compact .graph-svg-container svg { max-height: 260px; }
        .graph-compact { min-height: auto; padding: 8px; }

        /* Neo4j property card (click-to-expand) */
        .neo4j-graph-wrap { position: relative; }
        .neo4j-prop-card {
            position: absolute;
            background: #fff;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.18);
            padding: 10px 14px;
            font-size: 12px;
            z-index: 100;
            min-width: 150px;
            max-width: 240px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            pointer-events: auto;
            border: 1px solid #E5E7EB;
        }
        .neo4j-prop-card .card-title {
            font-weight: 700;
            font-size: 13px;
            margin-bottom: 6px;
            padding-bottom: 5px;
            border-bottom: 1px solid #F3F4F6;
        }
        .neo4j-prop-card .card-subtitle {
            font-size: 10px;
            color: #9CA3AF;
            margin-bottom: 6px;
        }
        .neo4j-prop-card .prop-row {
            display: flex;
            justify-content: space-between;
            padding: 2px 0;
            gap: 12px;
        }
        .neo4j-prop-card .prop-name { color: #1F2937; }
        .neo4j-prop-card .prop-type { color: #6B7280; font-style: italic; }
        .neo4j-prop-card .prop-key {
            font-size: 9px;
            background: #FEF3C7;
            color: #92400E;
            border-radius: 3px;
            padding: 0 4px;
            margin-left: 4px;
            font-weight: 600;
        }

        /* Chebotko Diagram (Cassandra) */
        .chebotko-diagram {
            display: flex;
            flex-wrap: wrap;
            gap: 24px;
            padding: 24px;
            background: #F5F5F7;
            border-radius: 16px;
        }
        .chebotko-table {
            background: #fff;
            border-radius: 10px;
            border: 2px solid #8E24AA;
            overflow: hidden;
            min-width: 180px;
            max-width: 240px;
            flex: 1;
        }
        .chebotko-header {
            background: #8E24AA;
            color: #fff;
            font-weight: 600;
            font-size: 14px;
            padding: 8px 16px;
            text-align: center;
        }
        .chebotko-cols { width: 100%; border-collapse: collapse; }
        .chebotko-cols tr { border-bottom: 1px solid #E8E8ED; }
        .chebotko-cols tr:last-child { border-bottom: none; }
        .chebotko-cols td { padding: 6px 10px; font-size: 13px; }
        .ck-marker-cell { width: 30px; text-align: center; }
        .ck-marker { font-weight: 700; font-size: 12px; }
        .ck-marker.pk { color: #8E24AA; }
        .ck-marker.ck { color: #0066CC; }
        .ck-name { font-weight: 500; }
        .ck-type { color: #636366; font-family: 'SF Mono', monospace; font-size: 12px; }

        .document-view {
            background: #F5F5F7;
            border-radius: 16px;
            padding: 24px;
            overflow-x: auto;
            border: 1px solid #E8E8ED;
        }

        .json-display {
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            line-height: 1.7;
            color: #1D1D1F;
            white-space: pre-wrap;
            word-break: break-word;
        }
        .json-key { color: #0066CC; }
        .json-string { color: #BF4800; }
        .json-number { color: #34C759; }
        .json-bracket { color: #AF52DE; }

        .sql-section { margin-bottom: 40px; }
        .sql-code-view {
            background: #F5F5F7;
            border-radius: 16px;
            padding: 24px;
            overflow-x: auto;
            border: 1px solid #E8E8ED;
        }
        .sql-code-view pre {
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            line-height: 1.7;
            color: #1D1D1F;
            white-space: pre-wrap;
            word-break: break-word;
            margin: 0;
        }
        .schema-view {
            background: #F5F5F7;
            border-radius: 12px;
            padding: 16px;
            overflow-x: auto;
            max-height: 600px;
            overflow-y: auto;
            border: 1px solid #E8E8ED;
        }
        .schema-code {
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
            font-size: 11px;
            line-height: 1.6;
            color: #1D1D1F;
            white-space: pre-wrap;
            word-break: break-word;
            margin: 0;
        }

        .migration-content { padding: 32px 48px; }

        .legend { display: flex; gap: 32px; margin-bottom: 32px; }
        .legend-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #636366; }
        .legend-dot { width: 10px; height: 10px; border-radius: 50%; }
        .legend-dot.new { background: #34C759; }
        .legend-dot.reference { background: #0066CC; }
        .legend-dot.embedded { background: #BF4800; }
        .legend-dot.edge { background: #8B5CF6; }
        .legend-dot.pk { background: #AF52DE; }

        .migration-layout { display: flex; gap: 24px; align-items: flex-start; }
        .meta-columns { flex: 3; min-width: 0; }
        .target-column {
            flex: 1;
            min-width: 320px;
            max-width: 400px;
            background: #F5F5F7;
            border-radius: 16px;
            overflow: hidden;
        }

        .target-header { padding: 20px; background: #0066CC; text-align: center; }
        .target-header h3 { font-size: 17px; font-weight: 600; color: #FFFFFF; }
        .target-header .subtitle { font-size: 14px; color: rgba(255, 255, 255, 0.7); margin-top: 4px; }

        .target-content { padding: 16px; max-height: 800px; overflow-y: auto; }

        .sql-display {
            background: #FFFFFF;
            border-radius: 12px;
            padding: 16px;
            border: 1px solid #E8E8ED;
        }
        .sql-display pre {
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
            font-size: 12px;
            line-height: 1.6;
            color: #1D1D1F;
            white-space: pre-wrap;
            word-break: break-word;
            margin: 0;
        }

        .json-display-box {
            background: #FFFFFF;
            border-radius: 12px;
            padding: 16px;
            border: 1px solid #E8E8ED;
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
            font-size: 12px;
            line-height: 1.6;
            color: #1D1D1F;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .target-er-section { margin-bottom: 16px; }
        .target-sql-section { margin-top: 16px; }
        .target-section-title {
            font-size: 12px;
            font-weight: 600;
            color: #636366;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }
        .target-er-diagram {
            background: #FFFFFF;
            border-radius: 12px;
            padding: 16px;
            border: 1px solid #E8E8ED;
            overflow: auto;
            min-height: 200px;
        }
        .target-er-diagram svg { display: block; margin: 0 auto; max-width: 100%; }

        .schema-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1px;
            background: #E8E8ED;
            border-radius: 16px;
            overflow: hidden;
        }

        /* Four-column layout for Migration Process */
        .four-column-layout {
            display: flex;
            gap: 12px;
            padding: 0;
        }

        .independent-column {
            flex: 1;
            min-width: 200px;
            max-width: 280px;
            background: #F5F5F7;
            border-radius: 16px;
            overflow: hidden;
        }

        .independent-column .column-header {
            padding: 12px;
            background: #FFFFFF;
            border-bottom: 1px solid #E8E8ED;
            text-align: center;
        }

        .independent-column .column-content {
            padding: 12px;
            max-height: 700px;
            overflow-y: auto;
        }

        .independent-column .entity-card {
            margin-bottom: 8px;
        }

        /* Dense layout for schemas with 7+ entities */
        .four-column-layout.dense-layout .independent-column { max-width: 320px; }
        .four-column-layout.dense-layout .column-content { max-height: 900px; }
        .four-column-layout.dense-layout .property { padding: 3px 0; font-size: 13px; }
        .four-column-layout.dense-layout .attr-name { font-size: 13px; }
        .four-column-layout.dense-layout .entity-name { padding: 10px 12px; font-size: 14px; }
        .four-column-layout.dense-layout .entity-body { padding: 8px 12px; }
        .four-column-layout.dense-layout .entity-card { margin-bottom: 6px; }

        .meta-aligned-columns {
            flex: 2;
            min-width: 0;
        }

        .meta-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1px;
            background: #E8E8ED;
            border-radius: 16px;
            overflow: hidden;
        }

        .meta-grid .column-header {
            padding: 12px;
            background: #F5F5F7;
            text-align: center;
        }

        .meta-grid .grid-cell {
            background: #FFFFFF;
            padding: 8px;
        }

        .sql-code-box {
            background: #FFFFFF;
            border-radius: 12px;
            padding: 16px;
            border: 1px solid #E8E8ED;
            overflow-x: auto;
        }

        .sql-code-box pre {
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
            font-size: 11px;
            line-height: 1.5;
            color: #1D1D1F;
            white-space: pre-wrap;
            word-break: break-word;
            margin: 0;
        }

        .grid-cell { background: #FFFFFF; padding: 12px; }

        .column-header { padding: 20px; background: #F5F5F7; text-align: center; }
        .column-header h3 { font-size: 17px; font-weight: 600; color: #1D1D1F; }
        .column-header .subtitle { font-size: 14px; color: #636366; margin-top: 4px; }

        .entity-card { background: #F5F5F7; border-radius: 12px; margin-bottom: 12px; overflow: hidden; }
        .entity-card.new { background: #F0FFF4; border: 1px solid #34C759; }

        .entity-name {
            padding: 12px 14px;
            background: #FFFFFF;
            border-bottom: 1px solid #E8E8ED;
            font-weight: 600;
            font-size: 15px;
            color: #1D1D1F;
        }
        .entity-name.new { color: #34C759; }

        .entity-body { padding: 10px 14px; }

        .property { display: flex; align-items: center; padding: 4px 0; font-size: 14px; }
        .attr-name { flex: 1; font-weight: 500; color: #1D1D1F; font-size: 14px; }
        .attr-type { color: #636366; font-size: 13px; }

        /* Nested object styling - makes hierarchy obvious like JSON */
        .property.nested-object {
            background: #F5F5F7;
            padding: 6px 8px;
            border-radius: 6px;
            margin: 4px 0;
            font-weight: 600;
        }
        .property.nested-object .attr-type {
            color: #AF52DE;
            font-weight: 600;
        }
        .nested-level-1 { margin-left: 16px; border-left: 3px solid #E8E8ED; padding-left: 12px; }
        .nested-level-2 { margin-left: 32px; border-left: 3px solid #D1D1D6; padding-left: 12px; }
        .nested-level-3 { margin-left: 48px; border-left: 3px solid #C7C7CC; padding-left: 12px; }
        .attr-badge {
            font-size: 9px;
            font-weight: 600;
            padding: 2px 5px;
            border-radius: 3px;
            margin-left: 4px;
        }
        .attr-badge.pk { background: #AF52DE; color: white; }
        .attr-badge.ck { background: #0066CC; color: white; }
        .attr-badge.optional { background: #E8E8ED; color: #636366; }

        .reference-item {
            display: flex;
            align-items: center;
            padding: 6px 10px;
            margin: 4px 0;
            background: rgba(0, 102, 204, 0.08);
            border-radius: 6px;
            font-size: 13px;
            color: #0066CC;
        }

        .embedded-item {
            display: flex;
            align-items: center;
            padding: 6px 10px;
            margin: 4px 0;
            background: rgba(191, 72, 0, 0.08);
            border-radius: 6px;
            font-size: 13px;
            color: #BF4800;
        }

        .edge-item {
            display: flex;
            align-items: center;
            padding: 6px 10px;
            margin: 4px 0;
            background: rgba(139, 92, 246, 0.08);
            border-radius: 6px;
            font-size: 13px;
            color: #8B5CF6;
        }

        .placeholder { padding: 14px; text-align: center; color: #636366; font-size: 14px; background: #F5F5F7; border-radius: 12px; margin-bottom: 12px; }
        .placeholder-card { background: #F5F5F7; opacity: 0.6; }
        .placeholder-name { color: #636366; font-style: italic; }
        .placeholder-body { padding: 20px 14px; text-align: center; color: #636366; font-size: 13px; }

        .validation { margin-top: 40px; padding: 28px; background: #F5F5F7; border-radius: 16px; }
        .validation-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
        .validation h2 { font-size: 18px; font-weight: 600; color: #1D1D1F; }
        .validation-status { padding: 8px 16px; border-radius: 16px; font-weight: 600; font-size: 14px; }
        .validation-status.passed { background: rgba(52, 199, 89, 0.1); color: #34C759; }
        .validation-status.failed { background: rgba(255, 59, 48, 0.1); color: #FF3B30; }

        .validation-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
        .stat-card { padding: 20px; background: #FFFFFF; border-radius: 12px; text-align: center; }
        .stat-value { font-size: 28px; font-weight: 700; color: #1D1D1F; }
        .stat-label { font-size: 13px; color: #636366; margin-top: 4px; }

        .footer { text-align: center; padding: 48px; color: #636366; font-size: 13px; }

        /* SMILE Script Tab Styles */
        .smile-content { padding: 32px 48px; }

        .smile-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }

        .smile-panel {
            background: #FFFFFF;
            border-radius: 16px;
            border: 1px solid #E8E8ED;
            overflow: hidden;
        }

        .smile-panel-header {
            padding: 20px 24px;
            background: #F5F5F7;
            border-bottom: 1px solid #E8E8ED;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .smile-panel-title {
            font-size: 17px;
            font-weight: 600;
            color: #1D1D1F;
        }

        .smile-file-badge {
            padding: 6px 12px;
            background: #0066CC;
            color: white;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
        }

        .smile-panel-body {
            padding: 24px;
            max-height: 600px;
            overflow-y: auto;
        }

        .smile-code {
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            line-height: 1.8;
            color: #1D1D1F;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .smile-keyword { color: #0066CC; font-weight: 600; }
        .smile-comment { color: #636366; font-style: italic; }
        .smile-string { color: #BF4800; }
        .smile-number { color: #34C759; }
        .smile-type { color: #AF52DE; }

        .operations-list { display: flex; flex-direction: column; gap: 12px; }

        .operation-item {
            background: #F5F5F7;
            border-radius: 12px;
            padding: 16px;
            border-left: 4px solid #0066CC;
        }

        .operation-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }

        .operation-step {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .step-number {
            width: 28px;
            height: 28px;
            background: #0066CC;
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            font-weight: 600;
        }

        .operation-type {
            font-size: 15px;
            font-weight: 600;
            color: #1D1D1F;
        }

        .operation-badge {
            padding: 4px 10px;
            background: #E8E8ED;
            border-radius: 6px;
            font-size: 12px;
            color: #636366;
        }

        .operation-badge.changed { background: rgba(52, 199, 89, 0.15); color: #34C759; }

        .operation-params {
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            color: #636366;
            padding-left: 38px;
        }

        .operation-param { margin: 4px 0; }
        .param-key { color: #0066CC; }
        .param-value { color: #1D1D1F; }

        .smile-summary {
            margin-top: 24px;
            padding: 20px;
            background: #F5F5F7;
            border-radius: 12px;
            display: flex;
            gap: 32px;
        }

        .summary-item { text-align: center; }
        .summary-value { font-size: 24px; font-weight: 700; color: #0066CC; }
        .summary-label { font-size: 13px; color: #636366; margin-top: 4px; }

        .validation-section {
            margin-top: 24px;
            padding: 20px 24px;
            background: #FFFFFF;
            border-radius: 12px;
            border: 1px solid #E8E8ED;
        }
        .validation-section-title {
            font-size: 15px;
            font-weight: 600;
            color: #1D1D1F;
            margin-bottom: 16px;
        }
        .validation-layer {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 0;
            border-bottom: 1px solid #F0F0F5;
        }
        .validation-layer:last-child { border-bottom: none; }
        .validation-layer-label {
            font-size: 13px;
            font-weight: 500;
            color: #636366;
            min-width: 180px;
        }
        .validation-badge {
            padding: 4px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
        }
        .validation-badge.pass { background: rgba(52, 199, 89, 0.12); color: #248A3D; }
        .validation-badge.fail { background: rgba(255, 59, 48, 0.12); color: #D70015; }
        .validation-badge.na { background: #F0F0F5; color: #8E8E93; }
        .validation-details {
            margin-top: 8px;
            padding: 12px 16px;
            background: #FFF5F5;
            border-radius: 8px;
            font-size: 12px;
            color: #636366;
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
        }
        .validation-details .detail-entity {
            margin: 4px 0;
            padding-left: 8px;
            border-left: 2px solid #FF3B30;
        }
        /* Structured per-entity diff layout (replaces text-joined run-on lines) */
        .validation-details .vd-row {
            margin: 6px 0; display:flex; align-items:flex-start; flex-wrap:wrap; gap:6px;
        }
        .validation-details .vd-tag {
            font-size:10px; font-weight:700; padding:2px 8px; border-radius:10px;
            text-transform:uppercase; letter-spacing:0.4px;
        }
        .validation-details .vd-tag-missing { background:#FFD7D7; color:#8C1F1F; }
        .validation-details .vd-tag-extra   { background:#FFE8C2; color:#8B5A00; }
        .validation-details .vd-row code {
            background:#fff; padding:1px 6px; border-radius:4px; font-size:11px; color:#1D1D1F;
        }
        .validation-details .vd-entity-card {
            margin-top:8px; padding:8px 12px; background:#fff;
            border-radius:6px; border-left:3px solid #FF3B30;
        }
        .validation-details .vd-entity-name {
            font-weight:700; color:#1D1D1F; font-size:12px; margin-bottom:4px;
            font-family:'Helvetica Neue', sans-serif;
        }
        .validation-details .vd-item-list {
            margin:0; padding-left:18px; font-size:11px; line-height:1.6;
        }
        .validation-details .vd-item-list code {
            background:#F5F5F7; padding:1px 5px; border-radius:3px; color:#1D1D1F; font-size:11px;
        }
        .validation-warnings {
            margin-top: 8px;
            padding: 12px 16px;
            background: #FFFAF0;
            border-radius: 8px;
            font-size: 12px;
            color: #636366;
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
        }
        .validation-warnings .detail-entity {
            margin: 4px 0;
            padding-left: 8px;
            border-left: 2px solid #F39C12;
        }

        /* Expand/Collapse styles */
        .toggle-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            margin-top: 8px;
            margin-left: 38px;
            background: #E8E8ED;
            border: none;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            color: #636366;
            cursor: pointer;
            transition: all 0.2s;
        }
        .toggle-btn:hover { background: #D1D1D6; color: #1D1D1F; }
        .toggle-btn .arrow { font-size: 10px; }

        .changes-detail {
            display: none;
            margin-top: 12px;
            margin-left: 38px;
            padding: 16px;
            background: #FFFFFF;
            border-radius: 10px;
            border: 1px solid #E8E8ED;
        }
        .changes-detail.show { display: block; }

        .affected-entity {
            margin-bottom: 12px;
            padding-bottom: 12px;
            border-bottom: 1px solid #F5F5F7;
        }
        .affected-entity:last-child { margin-bottom: 0; padding-bottom: 0; border-bottom: none; }

        .entity-name-header {
            font-size: 14px;
            font-weight: 600;
            color: #1D1D1F;
            margin-bottom: 8px;
        }
        .entity-name-header.new { color: #34C759; }
        .entity-name-header.deleted { color: #FF3B30; text-decoration: line-through; }

        .change-item {
            display: flex;
            align-items: center;
            padding: 4px 0;
            font-size: 13px;
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
        }
        .change-item.new { color: #34C759; }
        .change-item.deleted { color: #FF3B30; text-decoration: line-through; }

        .change-prefix {
            width: 20px;
            font-weight: 600;
        }
        .change-prefix.add { color: #34C759; }
        .change-prefix.remove { color: #FF3B30; }

        .change-label {
            margin-left: 8px;
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 4px;
            background: rgba(52, 199, 89, 0.15);
            color: #34C759;
        }
        .change-label.deleted {
            background: rgba(255, 59, 48, 0.15);
            color: #FF3B30;
        }

        .no-changes {
            font-size: 13px;
            color: #636366;
            font-style: italic;
        }

        /* Compose Script Tab */
        .compose-page { padding: 24px 32px; }
        .compose-toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; gap:16px; flex-wrap:wrap; }
        .compose-syntax-toggle { display:flex; gap:8px; }
        .compose-actions { display:flex; gap:8px; }
        .compose-btn {
            padding:8px 16px; background:#fff; color:#1D1D1F;
            border:1px solid #D2D2D7; border-radius:8px;
            cursor:pointer; font-size:13px; font-weight:500;
        }
        .compose-btn:hover { background:#F5F5F7; }
        .compose-btn.primary { background:#0066CC; color:#fff; border-color:#0066CC; }
        .compose-btn.primary:hover { background:#0051a3; }
        .compose-help {
            background:#F5F5F7; padding:10px 16px; border-radius:10px;
            font-size:12px; color:#3C3C43; margin-bottom:14px; line-height:1.55;
        }
        .compose-help code {
            background:#fff; padding:1px 6px; border-radius:4px; font-size:11px;
            color:#0066CC; font-family:'SF Mono','Consolas',monospace;
        }
        .compose-help kbd {
            background:#fff; border:1px solid #D2D2D7; border-bottom-width:2px;
            border-radius:4px; padding:1px 6px; font-size:11px;
            font-family:'SF Mono','Consolas',monospace;
        }
        #composeEditor {
            height:520px; border:1px solid #E8E8ED; border-radius:12px;
            font-size:14px;
        }
        .compose-status {
            margin-top:14px; padding:12px 16px; border-radius:10px;
            font-size:13px; font-family:'SF Mono','Consolas',monospace;
            display:none; white-space:pre-wrap;
        }
        .compose-status.ok { background:#D1F5D3; color:#1F6F2E; display:block; }
        .compose-status.err { background:#FBDADA; color:#8C1F1F; display:block; }

        /* Schema Inspector Tab */
        .inspector-page { padding: 32px 48px; }
        .gen-layout { display:grid; grid-template-columns: 1fr 1fr; gap:24px; margin-bottom:20px; }
        .gen-editor-panel {
            background:#fff; border-radius:16px; padding:20px; border:1px solid #E8E8ED;
        }
        .gen-target-bar {
            display:flex; align-items:center; gap:12px; flex-wrap:wrap;
            background:#F5F5F7; border-radius:10px; padding:10px 14px;
            margin:14px 0;
        }
        .gen-target-bar + .gen-target-bar { margin-top:-6px; }
        .gen-target-label {
            font-size:12px; color:#86868B; font-weight:600;
            text-transform:uppercase; letter-spacing:0.4px;
            min-width:90px;
        }
        .gen-target-bar .inspector-db-selector { gap:6px; flex:1; }
        .gen-target-panel {
            background:#fff; border-radius:16px; padding:20px; border:1px solid #E8E8ED;
        }
        /* Read-only textarea inside Target Schema panel — visually distinct from editable inputs */
        .gen-target-panel textarea[readonly] {
            background:#F5F5F7; color:#1D1D1F; cursor:default;
        }
        .gen-output-row { display:grid; grid-template-columns: 1fr 1fr; gap:24px; }
        .gen-op-count { font-size:12px; color:#86868B; font-weight:400; margin-left:8px; }
        .generate-btn {
            padding:8px 18px; background:#0066CC; color:#fff; border:none;
            border-radius:8px; cursor:pointer; font-size:13px; font-weight:600;
        }
        .generate-btn:hover { background:#0051a3; }
        .generate-btn:disabled { background:#86868B; cursor:wait; }
        .gen-schema-panel {
            background:#fff; border-radius:16px; padding:20px; border:1px solid #E8E8ED;
        }
        .gen-output-toolbar { display:flex; gap:8px; align-items:center; }
        .inspector-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; }
        .inspector-input-panel, .inspector-result-panel {
            background: #fff; border-radius: 16px; padding: 28px;
            border: 1px solid #E8E8ED;
        }
        .inspector-title { font-size: 18px; font-weight: 600; color: #1D1D1F; margin-bottom: 16px; }
        .inspector-subtitle { font-size: 13px; color: #86868B; margin-bottom: 20px; }
        .inspector-db-selector { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
        .db-type-btn {
            padding: 8px 16px; border-radius: 8px; border: 1px solid #D2D2D7;
            background: #fff; cursor: pointer; font-size: 13px; font-weight: 500;
            transition: all 0.2s;
        }
        .db-type-btn:hover { border-color: #0066CC; color: #0066CC; }
        .db-type-btn.active { background: #0066CC; color: #fff; border-color: #0066CC; }
        .inspector-input-mode { display: flex; gap: 8px; margin-bottom: 12px; }
        .input-mode-btn {
            padding: 6px 14px; border-radius: 6px; border: 1px solid #D2D2D7;
            background: #fff; cursor: pointer; font-size: 12px; transition: all 0.2s;
        }
        .input-mode-btn.active { background: #F5F5F7; border-color: #0066CC; color: #0066CC; }
        .inspector-textarea {
            width: 100%; height: 280px; border: 1px solid #D2D2D7; border-radius: 10px;
            padding: 14px; font-family: 'SF Mono', monospace; font-size: 12px;
            resize: vertical; background: #FAFAFA; box-sizing: border-box;
        }
        .inspector-textarea:focus { outline: none; border-color: #0066CC; background: #fff; }
        .inspector-file-upload {
            border: 2px dashed #D2D2D7; border-radius: 10px; padding: 32px;
            text-align: center; cursor: pointer; transition: all 0.2s; margin-bottom: 12px;
        }
        .inspector-file-upload:hover { border-color: #0066CC; background: #F5F5FF; }
        .inspector-file-upload.dragover { border-color: #0066CC; background: #EBF0FF; }
        .inspector-examples { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
        .example-btn {
            padding: 6px 12px; border-radius: 6px; border: 1px solid #D2D2D7;
            background: #F5F5F7; cursor: pointer; font-size: 11px; color: #666;
            transition: all 0.2s;
        }
        .example-btn:hover { border-color: #0066CC; color: #0066CC; background: #EBF0FF; }
        .inspect-btn {
            width: 100%; padding: 12px; border-radius: 10px; border: none;
            background: #0066CC; color: #fff; font-size: 15px; font-weight: 600;
            cursor: pointer; transition: all 0.2s;
        }
        .inspect-btn:hover { background: #0055AA; }
        .inspect-btn:disabled { background: #D2D2D7; cursor: not-allowed; }

        .inspector-summary { margin-bottom: 20px; }
        .summary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }
        .summary-card {
            background: #F5F5F7; border-radius: 10px; padding: 14px; text-align: center;
        }
        .summary-card .num { font-size: 24px; font-weight: 700; color: #0066CC; }
        .summary-card .label { font-size: 11px; color: #86868B; margin-top: 2px; }

        .entity-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .entity-table th {
            text-align: left; padding: 10px 12px; background: #F5F5F7;
            color: #86868B; font-weight: 600; font-size: 11px; text-transform: uppercase;
        }
        .entity-table td { padding: 10px 12px; border-bottom: 1px solid #E8E8ED; }
        .entity-table tr:hover td { background: #FAFAFA; }
        .entity-kind-badge {
            display: inline-block; padding: 2px 8px; border-radius: 4px;
            font-size: 10px; font-weight: 600; text-transform: uppercase;
        }
        .kind-table { background: #E3F2FD; color: #1565C0; }
        .kind-document { background: #E8F5E9; color: #2E7D32; }
        .kind-embedded { background: #FFF3E0; color: #E65100; }
        .kind-vertex { background: #F3E5F5; color: #7B1FA2; }
        .kind-wide_column_table { background: #FBE9E7; color: #BF360C; }

        .pipe-to-gen-row { display:flex; gap:10px; margin-top:10px; flex-wrap:wrap; }
        .pipe-to-gen-btn {
            flex:1; min-width:160px; padding:10px 14px;
            background:#fff; color:#0066CC; border:1px solid #0066CC;
            border-radius:10px; cursor:pointer; font-size:13px; font-weight:600;
        }
        .pipe-to-gen-btn:hover { background:#EBF0FF; }

        .view-toggle { display: flex; gap: 6px; margin-bottom: 12px; }
        .view-toggle-btn {
            padding: 5px 12px; border-radius: 6px; border: 1px solid #D2D2D7;
            background: #fff; cursor: pointer; font-size: 11px; transition: all 0.2s;
        }
        .view-toggle-btn.active { background: #0066CC; color: #fff; border-color: #0066CC; }
        .json-view {
            background: #1D1D1F; border-radius: 10px; padding: 18px; color: #E8E8ED;
            font-family: 'SF Mono', monospace; font-size: 11px; overflow: auto;
            max-height: 500px; white-space: pre;
        }

        /* Source Schemas Tab */
        .source-schemas-page { padding: 32px 48px; }
        .source-schemas-page .schema-section {
            margin-bottom: 48px;
            padding-bottom: 48px;
            border-bottom: 1px solid #E8E8ED;
        }
        .source-schemas-page .schema-section:last-child { border-bottom: none; margin-bottom: 0; }
        .schema-section-header {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 24px;
        }
        .schema-section-header h2 {
            font-size: 22px;
            font-weight: 600;
            color: #1D1D1F;
        }
        .schema-section-header .schema-badge { font-size: 14px; }
        .schema-section-subtitle {
            font-size: 14px;
            color: #636366;
            margin-bottom: 24px;
        }
        .schema-section .vis-and-code {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
        }
        .schema-section .vis-block,
        .schema-section .code-block-wrapper {
            min-width: 0;
        }
        .schema-section .code-block-wrapper .sql-code-view {
            max-height: 600px;
            overflow-y: auto;
        }
        /* Full-width code block when no side-by-side visualization */
        .schema-section .vis-and-code.full-width { grid-template-columns: 1fr; }

        /* Document tree for MongoDB source schemas */
        .document-tree {
            font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
            font-size: 13px;
            line-height: 1.8;
            color: #1D1D1F;
            background: #F5F5F7;
            border-radius: 16px;
            padding: 24px;
            border: 1px solid #E8E8ED;
            white-space: pre-wrap;
        }
        .document-tree .dt-key { color: #0066CC; font-weight: 600; }
        .document-tree .dt-type { color: #636366; }
        .document-tree .dt-obj { color: #AF52DE; font-weight: 600; }
        .document-tree .dt-arr { color: #BF4800; font-weight: 600; }
        .document-tree .dt-comment { color: #636366; font-style: italic; font-size: 12px; }
    </style>
</head>
<body>
    <header class="header">
        <h1>Schema Migration & Evolution Viewer</h1>
        <p>SMILE - Schema Migration & Evolution Language</p>
    </header>

    <div class="controls">
        <div class="control-group">
            <span class="control-label">Migration Direction</span>
            <div class="dropdown">
                <select id="directionSelect">
                    <!-- DROPDOWN_OPTIONS -->
                </select>
            </div>
        </div>
        <button class="run-btn" onclick="runMigration()">Run</button>
    </div>

    <div class="loading" id="loading">
        <div class="spinner"></div>
        <p>Running schema transformation...</p>
    </div>

    <div class="welcome" id="welcome" style="display:none;">
        <h2>Select migration or evolution and click Run</h2>
        <p>Compare source and target schemas side by side</p>
    </div>

    <nav class="tab-nav show" id="tabNav">
        <button class="tab-btn active" data-tab="schemas">Source Schemas</button>
        <button class="tab-btn" data-tab="inspector">User Transformation</button>
        <button class="tab-btn" data-tab="compare">Schema Comparison</button>
        <button class="tab-btn" data-tab="smile">SMILE Script</button>
        <button class="tab-btn" data-tab="migration">Migration / Evolution Process</button>
    </nav>

    <div class="tab-content active" id="tab-schemas"></div>
    <div class="tab-content" id="tab-inspector">
        <div class="inspector-page">
            <!-- Top row: Source schema (left, with Meta V1) + Generate Script editor (right) -->
            <div class="gen-layout">
                <!-- Source -->
                <div class="gen-schema-panel">
                    <div class="inspector-title">Source Schema</div>
                    <div class="inspector-subtitle">The current/original schema you are migrating from. Click "Inspect" to see its Meta V1 structure.</div>

                    <div class="inspector-title" style="font-size:13px;">Database Type</div>
                    <div class="inspector-db-selector" id="genSrcDbSelector">
                        <button class="db-type-btn active" data-dbtype="relational" onclick="selectGenDbType('src', this)">PostgreSQL</button>
                        <button class="db-type-btn" data-dbtype="document" onclick="selectGenDbType('src', this)">MongoDB</button>
                        <button class="db-type-btn" data-dbtype="graph" onclick="selectGenDbType('src', this)">Neo4j</button>
                        <button class="db-type-btn" data-dbtype="columnar" onclick="selectGenDbType('src', this)">Cassandra</button>
                    </div>

                    <div class="inspector-title" style="font-size:13px;">Input Mode</div>
                    <div class="inspector-input-mode">
                        <button class="input-mode-btn active" onclick="switchGenSrcInputMode('paste', this)">Paste Text</button>
                        <button class="input-mode-btn" onclick="switchGenSrcInputMode('upload', this)">Upload File</button>
                    </div>

                    <div id="genSrcPasteArea">
                        <textarea class="inspector-textarea" id="genSrcText" placeholder="Paste source schema here (.sql / .json / .graphql / .cql)"></textarea>
                    </div>

                    <div id="genSrcUploadArea" style="display:none;">
                        <div class="inspector-file-upload" id="genSrcDropZone"
                             ondragover="event.preventDefault(); this.classList.add('dragover')"
                             ondragleave="this.classList.remove('dragover')"
                             ondrop="handleGenSrcFileDrop(event)">
                            <div style="font-size:24px; margin-bottom:8px;">+</div>
                            <div style="font-size:13px; color:#86868B;">Drop file here or click to browse</div>
                            <div style="font-size:11px; color:#AEAEB2; margin-top:4px;">.sql / .json / .graphql / .cql</div>
                            <input type="file" id="genSrcFileInput" accept=".sql,.json,.graphql,.gql,.cql" style="display:none" onchange="handleGenSrcFileSelect(event)">
                        </div>
                        <div id="genSrcFileInfo" style="font-size:12px; color:#86868B; margin-bottom:12px;"></div>
                    </div>

                    <button class="inspect-btn" id="genSrcInspectBtn" onclick="runGenInspect('src')">Inspect Source → Meta V1</button>
                    <div id="genSrcMetaResult" style="margin-top:16px;"></div>
                </div>

                <!-- Generate Script editor (right side, with Target DB Type selector inside) -->
                <div class="gen-editor-panel">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                        <div>
                            <div class="inspector-title" style="margin:0;">Generate Script <span id="genOpCount" class="gen-op-count"></span></div>
                            <div class="inspector-subtitle" style="margin-top:4px;">
                                Pick a <strong>Target Database Type</strong> below, click <strong>Generate</strong>, then edit the resulting skeleton. <kbd>Ctrl+Space</kbd> for autocomplete; <strong>Validate</strong> parses with ANTLR.
                            </div>
                        </div>
                        <div class="gen-output-toolbar">
                            <button class="view-toggle-btn active" id="genSyntaxBtnSpecific" onclick="toggleGenSyntax('specific', this)">Specific (.smile)</button>
                            <button class="view-toggle-btn" id="genSyntaxBtnGeneralized" onclick="toggleGenSyntax('generalized', this)">Generalized (.smile_gen)</button>
                            <button class="compose-btn primary" onclick="validateComposeScript()">Validate</button>
                            <button class="compose-btn" onclick="copyGenScript()">Copy</button>
                            <button class="compose-btn" onclick="saveAsGenScript()">Save As…</button>
                            <button class="compose-btn" onclick="runComposeScript()">Run ▶</button>
                        </div>
                    </div>

                    <!-- Type + Target DB Type chooser + Generate trigger -->
                    <div class="gen-target-bar">
                        <span class="gen-target-label">Type</span>
                        <div class="inspector-db-selector" id="genKindSelector" style="margin:0;">
                            <button class="db-type-btn active" data-kind="migration" onclick="selectGenKind('migration', this)">Migration</button>
                            <button class="db-type-btn" data-kind="evolution" onclick="selectGenKind('evolution', this)">Evolution</button>
                        </div>
                    </div>
                    <div class="gen-target-bar">
                        <span class="gen-target-label">Target DB</span>
                        <div class="inspector-db-selector" id="genTgtDbSelector" style="margin:0;">
                            <button class="db-type-btn active" data-dbtype="relational" onclick="selectGenDbType('tgt', this)">PostgreSQL</button>
                            <button class="db-type-btn" data-dbtype="document" onclick="selectGenDbType('tgt', this)">MongoDB</button>
                            <button class="db-type-btn" data-dbtype="graph" onclick="selectGenDbType('tgt', this)">Neo4j</button>
                            <button class="db-type-btn" data-dbtype="columnar" onclick="selectGenDbType('tgt', this)">Cassandra</button>
                        </div>
                        <button class="generate-btn" id="genBtn" onclick="runGenerate()">Generate Header</button>
                    </div>

                    <div id="composeEditor"></div>
                    <div id="composeStatus" class="compose-status"></div>
                    <!-- Holds the four-layer validation panel (Layer 0 / 1 / 2 / 3
                         + blame) the backend returns for /api/run_script. Without
                         this hook, runComposeScript would render only a plain-
                         text banner and discard validation_layer0/meta/export/text_diff. -->
                    <div id="composeValidation"></div>
                </div>
            </div>

            <!-- Bottom row: Run output (read-only). Both panels are populated only by Run ▶. -->
            <div class="gen-output-row">
                <!-- Left: Meta V2 — auto-generated, no manual editing -->
                <div class="gen-target-panel">
                    <div class="inspector-title">Meta Schema V2</div>
                    <div id="genMetaV2Result" style="margin-top:10px; min-height:160px;"></div>
                </div>

                <!-- Right: Target Schema — auto-generated, read-only textarea -->
                <div class="gen-target-panel">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                        <div class="inspector-title" style="margin:0;">Target Schema</div>
                        <div class="gen-output-toolbar">
                            <button class="compose-btn" onclick="saveAsTargetSchema()">Save As…</button>
                        </div>
                    </div>
                    <textarea class="inspector-textarea" id="genTgtText" style="height:200px; margin-top:10px;" readonly placeholder=""></textarea>
                </div>
            </div>
        </div>
    </div>
    <div class="tab-content" id="tab-compare"></div>
    <div class="tab-content" id="tab-smile"></div>
    <div class="tab-content" id="tab-migration"></div>

    <footer class="footer">SMILE - Schema Migration & Evolution Language</footer>

    <!-- Dynamic config injection (was inline; now points to /static/smile-app.js) -->
    <script>
        // INJECT_CONFIG
    </script>
    <script src="/static/smile-app.js?v=2"></script>
</body>
</html>'''
    # Inject dynamic content from config.py
    html = html.replace('<!-- DROPDOWN_OPTIONS -->', _build_dropdown_options())
    html = html.replace('// INJECT_CONFIG', _build_config_js())
    return html


def main():
    server = ThreadingHTTPServer(('localhost', PORT), SMILEHandler)
    print(f"\n  SMILE Web Server running at http://localhost:{PORT}")
    print(f"  Press Ctrl+C to stop\n")

    threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{PORT}')).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
