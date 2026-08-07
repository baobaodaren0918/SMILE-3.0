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
        """Send a JSON response.

        No ``Access-Control-Allow-Origin`` header: the page and these APIs are
        served from the same origin (localhost:5601), so CORS is unnecessary.
        Dropping the wildcard also closes the cross-site POST surface (any page
        the user visits could otherwise POST to these state-changing endpoints).
        """
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
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

    def _read_body(self) -> bytes:
        """Read the full request body as bytes (honouring Content-Length)."""
        content_length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(content_length)

    def do_POST(self):
        # Thin dispatcher: each endpoint reads its own body and owns its
        # try/except -> _send_json contract. The outer guard only swallows the
        # client-disconnect errors that are common on Windows.
        routes = {
            '/api/inspect': self._post_inspect,
            '/api/run_script': self._post_run_script,
            '/api/validate_script': self._post_validate_script,
            '/api/generate_script': self._post_generate_script,
            '/api/llm_generate': self._post_llm_generate,
        }
        try:
            handler = routes.get(self.path)
            if handler is None:
                self.send_response(404)
                self.end_headers()
                return
            handler()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def _post_inspect(self):
        body = self._read_body()
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

    def _post_run_script(self):
        body = self._read_body()
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

            # Reuse the same lex→parse→walk helper as the file-based path
            # (parse_smile_auto) so the two never drift.
            from parser.factory import parse_smile_text
            grammar = 'generalized' if syntax == 'generalized' else 'specific'
            _, operations, parse_errors = parse_smile_text(script_text, grammar)
            if parse_errors:
                # Parse failed: emit ``unverifiable`` placeholders so the
                # frontend gets a consistent validation_* shape across endpoints.
                skipped = {"passed": None,
                           "summary": "Other reasons (parse failed)",
                           "details": {}}
                skipped_integrity = {"passed": None,
                                     "summary": "Other reasons (parse failed)",
                                     "violations": []}
                result = {
                    "ok": False, "errors": parse_errors, "stage": "parse",
                    "validation_layer0": skipped,
                    "validation_meta": skipped,
                    "validation_export": skipped,
                    "validation_text_diff": skipped,
                    "validation_integrity": skipped_integrity,
                    "validation_blame": "unverifiable",
                    "validation_summary": "SMILE parse failed",
                }
            else:
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

    def _post_validate_script(self):
        body = self._read_body()
        try:
            data = json.loads(body.decode('utf-8'))
            text = data.get('text', '')
            syntax = data.get('syntax', 'specific')
            errors = _validate_smile_text(text, syntax)
            result = {"errors": errors, "ok": len(errors) == 0}
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)})

    def _post_generate_script(self):
        body = self._read_body()
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

    def _post_llm_generate(self):
        """Generate a SMILE script from a natural-language request via the
        OpenAI-compatible LLM endpoint configured in llm_config.py."""
        body = self._read_body()
        try:
            data = json.loads(body.decode('utf-8'))
            prompt = (data.get('prompt') or '').strip()
            if not prompt:
                raise ValueError("prompt is required (describe the desired transformation)")
            src_type = data.get('source_db_type', '')
            tgt_type = data.get('target_db_type', '')
            if not (src_type and tgt_type):
                raise ValueError("source_db_type and target_db_type are required")
            source_text = data.get('source_text') or ''
            syntax = 'generalized' if data.get('syntax') == 'generalized' else 'specific'
            kind = (data.get('kind') or 'auto').lower()

            src_token = _smile_db_token(src_type)
            tgt_token = _smile_db_token(tgt_type)
            if kind == 'auto':
                is_evolution = (src_token == tgt_token)
            else:
                is_evolution = (kind == 'evolution')

            from script_renderer import render_header_only
            header = render_header_only(
                src_token, tgt_token,
                kind=('evolution' if is_evolution else 'migration'),
                migration_name='llm_generated',
                schema_name='user_schema', version='1.0',
                schema_version_to='2.0', syntax=syntax)

            if source_text.strip():
                schema_block = f"Source schema:\n{source_text}\n\n"
            else:
                schema_block = ("No source schema was provided. Use exactly the "
                                "entity and property names given in the request.\n\n")
            user_prompt = (
                f"Source database type: {src_token}\n"
                f"Target database type: {tgt_token}\n"
                f"Script kind: {'EVOLUTION' if is_evolution else 'MIGRATION'}\n\n"
                "The script must start with exactly this header (copy it "
                f"unchanged, then append the operations):\n{header}\n\n"
                f"{schema_block}"
                f"Request:\n{prompt}\n")
            messages = [
                {"role": "system", "content": _build_llm_system_prompt(syntax)},
                {"role": "user", "content": user_prompt},
            ]

            raw, model_used = _call_llm(messages)
            script = _clean_llm_script(raw)
            errors = _validate_smile_text(script, syntax)
            repaired = False
            if errors:
                # One repair round: feed the ANTLR errors back to the model.
                # Keep the repaired script only if it is strictly better.
                messages.append({"role": "assistant", "content": script})
                messages.append({"role": "user", "content":
                                 "The script fails to parse with these errors:\n"
                                 + "\n".join(errors)
                                 + "\nReturn the corrected full script only, "
                                   "no explanations."})
                raw2, model_used = _call_llm(messages)
                script2 = _clean_llm_script(raw2)
                errors2 = _validate_smile_text(script2, syntax)
                if len(errors2) < len(errors):
                    script, errors, repaired = script2, errors2, True

            self._send_json({
                "ok": len(errors) == 0,
                "script": script,
                "syntax": syntax,
                "validation_errors": errors,
                "repaired": repaired,
                "model": model_used,
            })
        except Exception as e:
            self._send_json({"error": str(e)})

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


def _call_llm(messages):
    """Call the OpenAI-compatible endpoint from llm_config.py.

    Returns (reply_text, model_used). The preferred LLM_MODEL is tried first;
    if the provider rejects it (403 "Model disabled" on models the key's plan
    does not cover), each LLM_FALLBACK_MODELS entry is tried in order so the
    feature stays usable and the UI can display which model actually answered.
    """
    try:
        from llm_config import (LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
                                LLM_FALLBACK_MODELS)
    except ImportError:
        raise RuntimeError(
            "llm_config.py not found. Create it next to web_server.py with "
            "LLM_API_KEY, LLM_BASE_URL, LLM_MODEL and LLM_FALLBACK_MODELS "
            "(it is gitignored).")
    from openai import OpenAI, PermissionDeniedError, NotFoundError
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=180.0)
    candidates = [LLM_MODEL] + [m for m in LLM_FALLBACK_MODELS if m != LLM_MODEL]
    last_err = None
    for model in candidates:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=False,
            )
            return response.choices[0].message.content or "", model
        except (PermissionDeniedError, NotFoundError) as e:
            last_err = e
            continue
    raise RuntimeError(
        f"All configured models were rejected ({', '.join(candidates)}); "
        f"last error: {last_err}")


def _clean_llm_script(text: str) -> str:
    """Strip reasoning blocks and markdown fences from an LLM reply.

    Thinking models may emit inline <think> blocks, and chat models often wrap
    code in ``` fences despite instructions. The parser tolerates neither.
    """
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.DOTALL)
    t = text.strip()
    m = re.match(r'^```[A-Za-z_]*\s*\n(.*?)\n?```\s*$', t, flags=re.DOTALL)
    if m:
        t = m.group(1)
    return t.strip() + '\n'


def _build_llm_system_prompt(syntax: str) -> str:
    """Assemble the /api/llm_generate system prompt from smile_operations.json.

    Deriving the operation reference from the same spec file that drives the
    editor autocomplete keeps the LLM's grammar knowledge from drifting.
    """
    spec_path = Path(__file__).parent / 'grammar' / 'smile_operations.json'
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    key = 'syntax_specific' if syntax == 'specific' else 'syntax_generalized'
    enum_lines = "\n".join(
        f"  {name}: {', '.join(values)}"
        for name, values in spec.get('enums', {}).items())
    op_lines = "\n".join(
        f"  {op[key]}\n      ({op.get('doc', '')})"
        for op in spec.get('operations', {}).values() if op.get(key))
    grammar_label = ('the specific grammar (.smile, underscore keywords like ADD_PROPERTY)'
                     if syntax == 'specific' else
                     'the generalized grammar (.smile_gen, space-separated keywords like ADD PROPERTY)')
    if syntax == 'specific':
        example = """MIGRATION example:1.0
FROM RELATIONAL TO DOCUMENT
USING northwind VERSION 1.0

-- NEST lists the columns to embed after a colon; the FK columns join the rows
NEST categories:category_name,description IN products.category WHERE products.category_id = categories.category_id
DELETE_ENTITY categories
ADD_PROPERTY discount TO products WITH TYPE Double"""
    else:
        example = """MIGRATION example:1.0
FROM RELATIONAL TO DOCUMENT
USING northwind VERSION 1.0

-- NEST lists the columns to embed after a colon; the FK columns join the rows
NEST categories:category_name,description IN products.category WHERE products.category_id = categories.category_id
DELETE ENTITY categories
ADD PROPERTY discount TO products WITH TYPE Double"""
    return f"""You are an expert for SMILE (Schema Migration & Evolution Language), \
a language for intra-model schema evolution and inter-model schema transformation \
across relational (PostgreSQL), document (MongoDB), graph (Neo4j) and wide-column \
(Cassandra) databases. You translate a user's natural-language request into a \
syntactically valid SMILE script using {grammar_label}.

OPERATION REFERENCE (angle brackets = required, square brackets = optional):
{op_lines}

ENUM VALUES:
{enum_lines}

RULES:
1. Output ONLY the raw SMILE script. No markdown fences, no explanations, no
   surrounding prose.
2. Start with the header the user provides, copied exactly, then one operation
   per line. Optional comments start with -- .
3. Use only operations from the reference above. Entity and property names must
   match the source schema exactly (case-sensitive).
4. Respect the data-model paradigms: ADD_FOREIGN_KEY only makes sense when the
   target is RELATIONAL. For DOCUMENT targets prefer NEST / embedding
   operations. For COLUMNAR targets use ADD_PARTITION_KEY / ADD_CLUSTERING_KEY
   instead of primary keys. For GRAPH targets model relations as edges or
   logical reference constraints.
5. Order matters: an operation can only refer to entities and properties that
   still exist at that point in the script.
6. Keep the script minimal: exactly the operations needed for the request,
   nothing speculative.
7. NEST subtree carry: if the entity being nested already contains embedded
   sub-objects (from an earlier NEST or UNFLATTEN), you MUST list them in
   brace syntax with their fields, e.g. address{{street, city}} or
   product{{product_name, category{{category_name}}}}. A bare sub-object name
   does NOT carry the subtree and it will be lost.
8. NEST WHERE orientation: the left side of the WHERE must be the FOREIGN-KEY
   column, the right side the key it references, regardless of which entity is
   the nest parent. E.g. both NEST categories:... IN products.category WHERE
   products.category_id = categories.category_id (FK on the parent) and
   NEST order_details:... IN orders.details WHERE order_details.order_id =
   orders.order_id (FK on the nested entity) are correct. Never put the
   parent's own primary key on the left side, or it gets deleted.
9. For DOCUMENT targets: declare the surviving root collections up front with
   CAST_ENTITY <entity> TO DOCUMENT. If a cross-collection reference should
   remain after DELETE_FOREIGN_KEY, re-declare it explicitly:
   ADD_CONSTRAINT <entity>.<field> AS REFERENCE TO <target>(<key>)
   WITH CARDINALITY <cardinalityType>.

EXAMPLE OF A VALID SCRIPT:
{example}"""


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
    """Return the HTML page, read from templates/index.html.

    The page was a ~1300-line inline triple-quoted string. It now lives in
    templates/index.html and is read at request time. It is served only via
    this function (which performs the two server-side injections below), NOT
    through the /static/ handler, so the unreplaced placeholders are never
    exposed as a raw static file.
    """
    template_path = Path(__file__).parent / 'templates' / 'index.html'
    html = template_path.read_text(encoding='utf-8')
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
