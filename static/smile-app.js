        let vizInstance = null;
        let erDiagramCounter = 0;
        let pendingDotRenders = [];
        if (typeof Viz !== 'undefined') {
            Viz.instance().then(viz => { vizInstance = viz; }).catch(e => console.warn('Viz.js init failed:', e));
        }

        function flushDotRenders() {
            if (!vizInstance) {
                Viz.instance().then(viz => {
                    vizInstance = viz;
                    _doFlush();
                }).catch(e => console.warn('Viz.js init failed:', e));
            } else {
                _doFlush();
            }
        }

        function _doFlush() {
            console.log('[DOT] _doFlush called, pending:', pendingDotRenders.length);
            pendingDotRenders.forEach(item => {
                const el = document.getElementById(item.id);
                console.log('[DOT] Rendering', item.id, 'element found:', !!el, 'dot length:', item.dot.length);
                console.log('[DOT] DOT content (first 200):', item.dot.substring(0, 200));
                if (el) {
                    try {
                        const svgEl = vizInstance.renderSVGElement(item.dot);
                        svgEl.style.maxWidth = '100%';
                        svgEl.style.height = 'auto';
                        el.innerHTML = '';
                        el.appendChild(svgEl);
                        // Check if arrows exist in rendered SVG
                        const arrows = svgEl.querySelectorAll('polygon');
                        console.log('[DOT] SVG rendered, arrows (polygon):', arrows.length);
                    } catch (e) {
                        console.error('DOT render error for ' + item.id + ':', e);
                        el.textContent = 'ER diagram render failed';
                    }
                }
            });
            pendingDotRenders = [];
        }

        let migrationData = null;

        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
                if (btn.dataset.tab === 'inspector') {
                    setTimeout(() => { if (typeof initComposeEditor === 'function') initComposeEditor(); }, 50);
                }
            });
        });

        async function runMigration() {
            const direction = document.getElementById('directionSelect').value;
            document.getElementById('welcome').style.display = 'none';
            document.getElementById('loading').classList.add('show');
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            try {
                const response = await fetch('/api/migrate?direction=' + direction + '&t=' + Date.now());
                migrationData = await response.json();
                document.getElementById('loading').classList.remove('show');

                if (migrationData.error) { alert(migrationData.error); return; }

                renderCompareView();
                renderSmileScript();
                renderMigrationProcess();
                document.querySelector('.tab-btn[data-tab="compare"]').click();
            } catch (error) {
                document.getElementById('loading').classList.remove('show');
                alert('Error: ' + error.message);
            }
        }

        function getBadgeClass(sourceType) {
            return sourceType ? sourceType.toLowerCase() : 'document';
        }

        function getPkLabel(dbType) {
            if (dbType === 'Graph') return 'NK';
            if (dbType === 'Document') return '_id';
            return 'PK';
        }

        // Key badge for an entity-card property. Cassandra distinguishes
        // partition vs clustering keys (both are part of the PRIMARY KEY but
        // play different roles), so honour the per-property key_type instead of
        // flattening every key to a generic PK — matching the Chebotko diagram.
        function keyBadge(attr, dbType) {
            if (!attr.is_key) return '';
            if (attr.key_type === 'partition') return '<span class="attr-badge pk">PARTITION</span>';
            if (attr.key_type === 'clustering') return '<span class="attr-badge ck">CLUSTERING</span>';
            return '<span class="attr-badge pk">' + getPkLabel(dbType) + '</span>';
        }

        function isDDLType(sourceType) {
            return sourceType === 'Relational' || sourceType === 'Columnar';
        }

        function renderCompareView() {
            const container = document.getElementById('tab-compare');
            const sourceType = migrationData.source_type;
            const targetType = migrationData.target_type;

            let html = '<div class="schema-compare">';
            html += '<div class="schema-panel">';
            html += '<div class="panel-header"><span class="panel-title">Source Schema</span>';
            html += '<span class="schema-badge ' + getBadgeClass(sourceType) + '">' + sourceType + '</span></div>';

            if (sourceType === 'Relational') {
                // Relational Source: ER Diagram + Original SQL DDL
                const sourceEntities = migrationData.meta_v1 || {};
                html += '<div class="er-section"><div class="section-title">ER Diagram</div>';
                html += '<div class="er-diagram">' + generateERDiagram(sourceEntities) + '</div></div>';
                html += '<div class="sql-section"><div class="section-title">Original DDL</div>';
                html += '<div class="sql-code-view"><pre>' + escapeHtml(migrationData.raw_source) + '</pre></div></div>';
            } else if (sourceType === 'Graph') {
                // Graph Source: Graph Diagram + Original Graph SDL
                const sourceEntities = migrationData.meta_v1 || {};
                html += '<div class="er-section"><div class="section-title">Graph Diagram</div>';
                html += '<div class="er-diagram">' + generateGraphDiagram(sourceEntities, 'source') + '</div></div>';
                html += '<div class="sql-section"><div class="section-title">Neo4j GraphQL SDL</div>';
                html += '<div class="sql-code-view"><pre>' + escapeHtml(migrationData.raw_source) + '</pre></div></div>';
            } else if (sourceType === 'Columnar') {
                // Columnar Source: Chebotko Diagram + Original CQL
                const sourceEntities = migrationData.meta_v1 || {};
                html += '<div class="er-section"><div class="section-title">Chebotko Diagram</div>';
                html += generateChebotkoDiagram(sourceEntities);
                html += '</div>';
                html += '<div class="sql-section"><div class="section-title">Original CQL</div>';
                html += '<div class="sql-code-view"><pre>' + escapeHtml(migrationData.raw_source) + '</pre></div></div>';
            } else {
                // Document Source: Original JSON schema
                html += '<div class="document-view"><div class="json-display">' + syntaxHighlightJSON(migrationData.raw_source) + '</div></div>';
            }
            html += '</div>';

            html += '<div class="schema-panel">';
            html += '<div class="panel-header"><span class="panel-title">Target Schema</span>';
            html += '<span class="schema-badge ' + getBadgeClass(targetType) + '">' + targetType + '</span></div>';

            // Use centralized export label from config (injected by Python)
            const exportLabel = (typeof DB_TYPE_EXPORT_LABEL !== 'undefined' && DB_TYPE_EXPORT_LABEL[targetType])
                ? DB_TYPE_EXPORT_LABEL[targetType]
                : (targetType + ' Schema');

            if (targetType === 'Relational') {
                // Relational Target: ER Diagram + Generated DDL
                const targetEntities = migrationData.target_with_db_types || migrationData.result;
                html += '<div class="er-section"><div class="section-title">ER Diagram</div>';
                html += '<div class="er-diagram">' + generateERDiagram(targetEntities) + '</div></div>';
                html += '<div class="sql-section"><div class="section-title">' + exportLabel + '</div>';
                html += '<div class="sql-code-view"><pre>' + escapeHtml(migrationData.exported_target) + '</pre></div></div>';
            } else if (targetType === 'Graph') {
                // Graph Target: Graph Diagram + Generated Graph SDL
                const targetEntities = migrationData.target_with_db_types || migrationData.result;
                html += '<div class="er-section"><div class="section-title">Graph Diagram</div>';
                html += '<div class="er-diagram">' + generateGraphDiagram(targetEntities, 'target') + '</div></div>';
                html += '<div class="sql-section"><div class="section-title">' + exportLabel + '</div>';
                html += '<div class="sql-code-view"><pre>' + escapeHtml(migrationData.exported_target) + '</pre></div></div>';
            } else if (targetType === 'Columnar') {
                // Columnar Target: Chebotko Diagram + Generated CQL
                const targetEntities = migrationData.target_with_db_types || migrationData.result;
                html += '<div class="er-section"><div class="section-title">Chebotko Diagram</div>';
                html += generateChebotkoDiagram(targetEntities);
                html += '</div>';
                html += '<div class="sql-section"><div class="section-title">' + exportLabel + '</div>';
                html += '<div class="sql-code-view"><pre>' + escapeHtml(migrationData.exported_target) + '</pre></div></div>';
            } else {
                // Document Target: card view + JSON Schema
                const targetNested = filterEntities(migrationData.target_nested || {});
                if (Object.keys(targetNested).length > 0) {
                    html += '<div class="document-view">';
                    Object.values(targetNested).forEach(entity => {
                        html += renderNestedEntityCard(entity);
                    });
                    html += '</div>';
                }
                html += '<div class="document-view"><div class="section-title">' + exportLabel + '</div><div class="json-display">' + syntaxHighlightJSON(migrationData.exported_target) + '</div></div>';
            }
            html += '</div></div>';
            container.innerHTML = html;

            setTimeout(() => flushDotRenders(), 50);
        }

        function renderSmileScript() {
            const container = document.getElementById('tab-smile');
            const smileContent = migrationData.smile_content || '';
            const smileFile = migrationData.smile_file || 'script.smile';
            const operations = migrationData.operations_detail || [];

            let html = '<div class="smile-content">';
            html += '<div class="smile-layout">';

            // Left panel: SMILE Script
            html += '<div class="smile-panel">';
            html += '<div class="smile-panel-header">';
            html += '<span class="smile-panel-title">SMILE Script</span>';
            html += '<span class="smile-file-badge">' + escapeHtml(smileFile) + '</span>';
            html += '</div>';
            html += '<div class="smile-panel-body">';
            html += '<div class="smile-code">' + highlightSmileSyntax(smileContent, migrationData.smile_syntax) + '</div>';
            html += '</div></div>';

            // Right panel: Operations List
            html += '<div class="smile-panel">';
            html += '<div class="smile-panel-header">';
            html += '<span class="smile-panel-title">Parsed Operations</span>';
            // Show execution stats
            const execStats = migrationData.execution_stats || {total: operations.length, success: 0, skipped: 0};
            if (execStats.skipped > 0) {
                html += '<span class="smile-file-badge" style="background:#f39c12;color:#fff;">' + execStats.success + '/' + execStats.total + ' OK</span>';
            } else {
                html += '<span class="smile-file-badge" style="background:#27ae60;color:#fff;">All ' + execStats.total + ' OK</span>';
            }
            html += '</div>';
            html += '<div class="smile-panel-body">';
            html += '<div class="operations-list">';

            operations.forEach((op, index) => {
                const hasChanges = op.changes && op.changes.affected_entities && op.changes.affected_entities.length > 0;
                const isSuccess = op.status === 'success';
                html += '<div class="operation-item">';
                html += '<div class="operation-header">';
                html += '<div class="operation-step">';
                html += '<span class="step-number">' + op.step + '</span>';
                html += '<span class="operation-type">' + (op.original_keyword || op.type) + '</span>';
                html += '</div>';
                // Show execution status instead of entity count
                if (isSuccess) {
                    html += '<span class="operation-badge" style="background:#27ae60;color:#fff;">OK</span>';
                } else {
                    html += '<span class="operation-badge" style="background:#e74c3c;color:#fff;">SKIP</span>';
                }
                html += '</div>';
                html += '<div class="operation-params">';
                html += formatOperationParams(op.type, op.params);
                html += '</div>';

                // Add toggle button and changes detail
                if (hasChanges) {
                    html += '<button class="toggle-btn" onclick="toggleChanges(' + index + ')">';
                    html += '<span class="arrow" id="arrow-' + index + '">▶</span> Show Changes';
                    html += '</button>';
                    html += '<div class="changes-detail" id="changes-' + index + '">';
                    html += renderChangesDetail(op.changes);
                    html += '</div>';
                }

                html += '</div>';
            });

            html += '</div></div></div>';

            // Summary
            html += '<div class="smile-summary">';
            html += '<div class="summary-item"><div class="summary-value">' + ((migrationData.stats || {}).source_count || 0) + '</div><div class="summary-label">Source Entities</div></div>';
            html += '<div class="summary-item"><div class="summary-value">' + operations.length + '</div><div class="summary-label">Operations</div></div>';
            html += '<div class="summary-item"><div class="summary-value">' + ((migrationData.stats || {}).result_count || 0) + '</div><div class="summary-label">Result Entities</div></div>';
            html += '<div class="summary-item"><div class="summary-value">' + migrationData.source_type + ' → ' + migrationData.target_type + '</div><div class="summary-label">Direction</div></div>';
            html += '</div>';

            // Validation Results
            html += renderValidation(migrationData);

            html += '</div></div>';
            container.innerHTML = html;
        }

        // Renders the Verdict-layer banner shown above the per-layer rows.
        // Maps the code-level blame string (smile_script / adapter / ...) to
        // the paper-facing verdict label so that the UI matches the Verdict
        // synthesis in chapter 5 (Table tab:verdict-synthesis): target_meta
        // (Layer 1), round-trip_meta (Layer 2), target_schema (Layer 3),
        // none (unverifiable). Colour follows pass/fail intent: green for ok,
        // deep red for both/script_failed, plain red for single-layer
        // failures, gray for unverifiable.
        function renderVerdictBanner(blame, summary) {
            if (blame == null) return '';
            var paperLabel = {
                'ok': 'OK',
                'smile_script': 'TARGET_META',
                'adapter': 'ROUND-TRIP_META',
                'both': 'BOTH',
                'script_failed': 'SCRIPT_FAILED',
                'text_diff': 'TARGET_SCHEMA',
                'unverifiable': 'NONE'
            }[blame] || blame.toUpperCase();
            var colour = {
                'ok': '#1B873F',
                'smile_script': '#D32F2F',
                'adapter': '#D32F2F',
                'both': '#8B1A1A',
                'script_failed': '#8B1A1A',
                'text_diff': '#E67E22',
                'unverifiable': '#8E8E93'
            }[blame] || '#8E8E93';
            var bg = {
                'ok': '#E6F4EA',
                'smile_script': '#FFEBEE',
                'adapter': '#FFEBEE',
                'both': '#FFCDD2',
                'script_failed': '#FFCDD2',
                'text_diff': '#FDF1E2',
                'unverifiable': '#F2F2F2'
            }[blame] || '#F2F2F2';
            return '<div class="validation-verdict" '
                + 'style="display:flex;align-items:center;gap:10px;'
                + 'padding:8px 12px;margin:6px 0 10px;border-radius:6px;'
                + 'background:' + bg + ';border-left:4px solid ' + colour + ';">'
                + '<span style="font-size:11px;color:#666;font-weight:600;'
                + 'text-transform:uppercase;letter-spacing:0.5px;">Verdict</span>'
                + '<span style="font-size:14px;font-weight:700;color:' + colour + ';">'
                + escapeHtml(paperLabel) + '</span>'
                + '<span style="font-size:12px;color:#555;flex:1;">'
                + escapeHtml(summary || '') + '</span>'
                + '</div>';
        }

        function renderValidation(data) {
            var vLayer0 = data.validation_layer0 || {};
            var vMeta = data.validation_meta || {};
            var vExport = data.validation_export || {};
            var vTextDiff = data.validation_text_diff || {};
            var vSummary = data.validation_summary || '';

            // Detect the validation-crashed state explicitly: all three layers
            // come back with ``passed=null`` AND validation_summary is prefixed
            // with "validation crashed:" (set by the outer try/except in
            // core.run_migration). We surface this loudly instead of silently
            // skipping the panel — otherwise a crashed validation pipeline
            // would look indistinguishable from a successful run, which is
            // exactly the silent-failure mode we don't want.
            var crashed = (vLayer0.passed == null
                && vMeta.passed == null
                && vExport.passed == null
                && vSummary.indexOf('validation crashed:') === 0);

            // Skip if all three are legitimately N/A (no expected target +
            // no adapter, e.g. grammar_completeness suite). Crashed runs are
            // *not* skipped — they get a red error card below.
            if (!crashed
                && vLayer0.passed == null
                && vMeta.passed == null
                && vExport.passed == null) return '';

            var html = '<div class="validation-section">';
            html += '<div class="validation-section-title">Validation</div>';

            // Verdict banner — directly surfaces the Verdict-synthesis
            // categories from chapter 5 (Table tab:verdict-synthesis: ok /
            // target_meta / round-trip_meta / target_schema / none, plus the
            // implementation-only both / script_failed) instead of leaving the
            // user to infer them from per-layer PASS/FAIL badges. The verdict
            // string itself comes from validation/pipeline.derive_blame; the
            // rendered label uses the thesis terminology so the UI matches the
            // thesis description verbatim.
            html += renderVerdictBanner(data.validation_blame, vSummary);

            if (crashed) {
                var errMsg = vSummary.substring('validation crashed:'.length).trim();
                html += '<div class="validation-layer">'
                      + '<span class="validation-layer-label">'
                      + '<strong style="color:#D32F2F;">VALIDATION CRASHED</strong>'
                      + '</span>'
                      + '<span class="validation-badge fail">ERROR</span>'
                      + '<span style="font-size:12px;color:#8E8E93;">'
                      + escapeHtml(errMsg)
                      + '</span>'
                      + '</div>';
                html += '<div class="validation-details" '
                      + 'style="background:#FFF4F4;border-left:3px solid #D32F2F;'
                      + 'padding:8px 12px;color:#8B1A1A;">'
                      + 'The validation pipeline raised an exception before '
                      + 'producing layer reports. Treat this run\'s correctness '
                      + 'as <strong>UNKNOWN</strong> — not as a successful validation.'
                      + '</div>';
                html += '</div>';
                return html;
            }

            // Layer 0 (script execution) is rendered first — failed steps are
            // the user's most actionable signal ("which line of my script
            // broke?"). When Layer 0 fails it dominates blame, but Layer 1
            // and Layer 2 are still rendered below for completeness.
            html += renderValidationLayer0(vLayer0);
            html += renderValidationLayer('Layer 1 — SMILE Script', vMeta);
            html += renderValidationLayer('Layer 2 — Adapter Export', vExport);
            html += renderValidationLayer3(vTextDiff);

            html += '</div>';
            return html;
        }

        function renderValidationLayer0(v) {
            // Backwards-compat: results that pre-date the Layer 0 surfacing
            // arrive without ``validation_layer0``. Render nothing rather than
            // an "N/A" card so older history entries don't gain a confusing
            // blank row when reloaded.
            if (!v || v.passed == null) return '';

            // User-facing label is just "Script Execution" — no "Layer 0"
            // prefix in the UI. Internal data keys still use ``validation_layer0``
            // for code readability, but the visible card title reads cleanly.
            var label = 'Script Execution';
            var badge = v.passed
                ? '<span class="validation-badge pass">PASS</span>'
                : '<span class="validation-badge fail">FAIL</span>';
            var html = '<div class="validation-layer">' +
                '<span class="validation-layer-label">' + label + '</span>' +
                badge +
                '<span style="font-size:12px;color:#8E8E93;">' + escapeHtml(v.summary || '') + '</span>' +
                '</div>';

            // Failed-step listing — the user-facing answer to "where did it
            // fail?". Each row carries: step number, original SMILE keyword,
            // status (ERROR / SKIPPED), and the reason the handler reported.
            // Layer 0 details have a different shape from Layer 1/2 (no
            // missing_entities/entity_diffs), so we render it separately
            // rather than reusing the entity-diff layout.
            if (!v.passed && v.details && v.details.failed_steps && v.details.failed_steps.length) {
                html += '<div class="validation-details">';
                html += '<ul class="vd-item-list">';
                v.details.failed_steps.forEach(function(s) {
                    var keyword = s.original_keyword || s.type || '?';
                    var status = (s.status || '').toUpperCase();
                    var step = (s.step != null ? s.step : '?');
                    var reason = s.reason || '';
                    html += '<li>'
                          + '<strong>Step ' + escapeHtml(String(step)) + '</strong>'
                          + ' [<span class="vd-tag vd-tag-' + (status === 'ERROR' ? 'missing' : 'extra') + '">' + escapeHtml(status) + '</span>]'
                          + ' <code>' + escapeHtml(keyword) + '</code>'
                          + (reason ? ': ' + escapeHtml(reason) : '')
                          + '</li>';
                });
                html += '</ul></div>';
            }
            return html;
        }

        function renderValidationLayer(label, v) {
            if (!v || v.passed == null) {
                // Layer is skipped due to *external* state (no expected target
                // file or no adapter), not because of a script/adapter bug.
                // Use "OTHER" badge text + the descriptive summary so the
                // user immediately sees this is not a failure they caused.
                // CSS class stays "na" for backwards-compatible styling.
                var summaryText = (v && v.summary) ? v.summary : 'Other reasons';
                return '<div class="validation-layer">' +
                    '<span class="validation-layer-label">' + label + '</span>' +
                    '<span class="validation-badge na">OTHER</span>' +
                    '<span style="font-size:12px;color:#8E8E93;">' + escapeHtml(summaryText) + '</span>' +
                    '</div>';
            }
            var badge = v.passed
                ? '<span class="validation-badge pass">PASS</span>'
                : '<span class="validation-badge fail">FAIL</span>';
            var html = '<div class="validation-layer">' +
                '<span class="validation-layer-label">' + label + '</span>' +
                badge +
                '<span style="font-size:12px;color:#8E8E93;">' + escapeHtml(v.summary || '') + '</span>' +
                '</div>';
            // Details for failures — structured, per-entity, item-list layout
            if (!v.passed && v.details) {
                var d = v.details;
                var hasDetails = (d.missing_entities && d.missing_entities.length) ||
                    (d.extra_entities && d.extra_entities.length) ||
                    (d.entity_diffs && Object.keys(d.entity_diffs).length);
                if (hasDetails) {
                    html += '<div class="validation-details">';
                    // Missing/extra entities → compact chip rows
                    if (d.missing_entities && d.missing_entities.length) {
                        html += '<div class="vd-row"><span class="vd-tag vd-tag-missing">Missing entities</span>'
                              + d.missing_entities.map(function(n){return '<code>'+escapeHtml(n)+'</code>';}).join(' ')
                              + '</div>';
                    }
                    if (d.extra_entities && d.extra_entities.length) {
                        html += '<div class="vd-row"><span class="vd-tag vd-tag-extra">Extra entities</span>'
                              + d.extra_entities.map(function(n){return '<code>'+escapeHtml(n)+'</code>';}).join(' ')
                              + '</div>';
                    }
                    // Per-entity diffs → small card with item list
                    if (d.entity_diffs) {
                        Object.keys(d.entity_diffs).forEach(function(ename) {
                            var ed = d.entity_diffs[ename];
                            var items = _collectEntityDiffItems(ed);
                            if (items.length) {
                                html += '<div class="vd-entity-card">'
                                      + '<div class="vd-entity-name">' + escapeHtml(ename) + '</div>'
                                      + '<ul class="vd-item-list">'
                                      + items.map(function(it){return '<li>'+it+'</li>';}).join('')
                                      + '</ul></div>';
                            }
                        });
                    }
                    html += '</div>';
                }
                // Warnings
                var hasWarnings = d.entity_warnings && Object.keys(d.entity_warnings).length;
                if (hasWarnings) {
                    html += renderValidationWarnings(d.entity_warnings);
                }
            }
            // Warnings for passed results
            if (v.passed && v.details && v.details.entity_warnings && Object.keys(v.details.entity_warnings).length) {
                html += renderValidationWarnings(v.details.entity_warnings);
            }
            // Relationship type diffs (graph schemas)
            if (v.details && v.details.relationship_type_diffs) {
                var rtd = v.details.relationship_type_diffs;
                // Errors
                if (rtd.issue_count > 0) {
                    var rtParts = [];
                    if (rtd.missing && rtd.missing.length) rtParts.push('missing: ' + rtd.missing.join(', '));
                    if (rtd.extra && rtd.extra.length) rtParts.push('extra: ' + rtd.extra.join(', '));
                    if (rtd.mismatches && rtd.mismatches.length) {
                        rtd.mismatches.forEach(function(m) {
                            rtParts.push(m.name + ': ' + JSON.stringify(m.diffs));
                        });
                    }
                    if (rtParts.length) {
                        html += '<div class="validation-details"><div class="detail-entity">RelationshipTypes: ' + escapeHtml(rtParts.join('; ')) + '</div></div>';
                    }
                }
                // Cardinality warnings
                if (rtd.cardinality_warnings && rtd.cardinality_warnings.length) {
                    html += '<div class="validation-warnings">';
                    html += '<div style="color:#F39C12;font-weight:600;margin-bottom:4px;">Warnings:</div>';
                    rtd.cardinality_warnings.forEach(function(cw) {
                        html += '<div class="detail-entity">RelType(' + escapeHtml(cw.name) + '): actual=' + escapeHtml(cw.actual) + ' expected=' + escapeHtml(cw.expected) + '</div>';
                    });
                    html += '</div>';
                }
            }
            return html;
        }

        // Build a flat list of HTML items describing one entity's diff.
        // Each item is a single sentence-like fragment; the renderer wraps them in <li>.
        function _collectEntityDiffItems(ed) {
            var items = [];
            var ad = ed.properties || {};
            if (ad.missing && ad.missing.length)
                items.push('Missing properties: ' + ad.missing.map(function(n){return '<code>'+escapeHtml(n)+'</code>';}).join(', '));
            if (ad.extra && ad.extra.length)
                items.push('Extra properties: ' + ad.extra.map(function(n){return '<code>'+escapeHtml(n)+'</code>';}).join(', '));
            (ad.type_mismatches || []).forEach(function(tm) {
                items.push('Type mismatch <code>'+escapeHtml(tm.attr)+'</code>: actual=<code>'+escapeHtml(tm.actual)+'</code>, expected=<code>'+escapeHtml(tm.expected)+'</code>');
            });

            var rd = ed.references || {};
            if (rd.missing && rd.missing.length)
                items.push('Missing references: ' + rd.missing.map(function(n){return '<code>'+escapeHtml(n)+'</code>';}).join(', '));
            if (rd.extra && rd.extra.length)
                items.push('Extra references: ' + rd.extra.map(function(n){return '<code>'+escapeHtml(n)+'</code>';}).join(', '));
            (rd.target_mismatches || []).forEach(function(tm) {
                items.push('Reference <code>'+escapeHtml(tm.name)+'</code> target mismatch: actual=<code>'+escapeHtml(tm.actual_target||'')+'</code>, expected=<code>'+escapeHtml(tm.expected_target||'')+'</code>');
            });
            (rd.attr_mismatches || []).forEach(function(am) {
                items.push('Reference <code>'+escapeHtml(am.name)+'</code> edge_properties differ: actual=<code>'+escapeHtml(JSON.stringify(am.actual))+'</code>, expected=<code>'+escapeHtml(JSON.stringify(am.expected))+'</code>');
            });

            var emd = ed.embedded || {};
            if (emd.missing && emd.missing.length)
                items.push('Missing embedded: ' + emd.missing.map(function(n){return '<code>'+escapeHtml(n)+'</code>';}).join(', '));
            if (emd.extra && emd.extra.length)
                items.push('Extra embedded: ' + emd.extra.map(function(n){return '<code>'+escapeHtml(n)+'</code>';}).join(', '));
            (emd.target_mismatches || []).forEach(function(tm) {
                items.push('Embedded <code>'+escapeHtml(tm.name)+'</code> target mismatch: actual=<code>'+escapeHtml(tm.actual_target||'')+'</code>, expected=<code>'+escapeHtml(tm.expected_target||'')+'</code>');
            });

            var edg = ed.edges || {};
            if (edg.missing && edg.missing.length)
                items.push('Missing edges: ' + edg.missing.map(function(n){return '<code>'+escapeHtml(n)+'</code>';}).join(', '));
            if (edg.extra && edg.extra.length)
                items.push('Extra edges: ' + edg.extra.map(function(n){return '<code>'+escapeHtml(n)+'</code>';}).join(', '));
            (edg.mismatches || []).forEach(function(m) {
                var pairs = Object.keys(m.diffs || {}).map(function(k){
                    var d = m.diffs[k];
                    return k+': actual=<code>'+escapeHtml(d.actual||'')+'</code> expected=<code>'+escapeHtml(d.expected||'')+'</code>';
                });
                items.push('Edge <code>'+escapeHtml(m.name)+'</code>: ' + pairs.join('; '));
            });

            var cd = ed.constraints || {};
            (cd.missing_pk || []).forEach(function(pk) {
                items.push('Missing PK on (' + (pk.columns||[]).map(function(c){return '<code>'+escapeHtml(c)+'</code>';}).join(', ') + ')');
            });
            (cd.extra_pk || []).forEach(function(pk) {
                items.push('Extra PK on (' + (pk.columns||[]).map(function(c){return '<code>'+escapeHtml(c)+'</code>';}).join(', ') + ')');
            });
            return items;
        }

        function renderValidationLayer3(v) {
            // Layer 3: text-level diff between FE-exported native and the
            // hand-written ground truth, under set-based normalization
            // (table/column/required ordering ignored, comments stripped per
            // paradigm). Renders PASS/FAIL/SKIP like Layers 1/2 but the FAIL
            // body is a unified-diff <pre> block instead of structured
            // entity diffs (the comparison is text-level by definition).
            var label = 'Layer 3 — Text-Level Validation';
            if (!v || v.passed == null) {
                var summaryText = (v && v.summary) ? v.summary : 'Other reasons';
                return '<div class="validation-layer">' +
                    '<span class="validation-layer-label">' + label + '</span>' +
                    '<span class="validation-badge na">OTHER</span>' +
                    '<span style="font-size:12px;color:#8E8E93;">' + escapeHtml(summaryText) + '</span>' +
                    '</div>';
            }
            var badge = v.passed
                ? '<span class="validation-badge pass">PASS</span>'
                : '<span class="validation-badge fail">FAIL</span>';
            var html = '<div class="validation-layer">' +
                '<span class="validation-layer-label">' + label + '</span>' +
                badge +
                '<span style="font-size:12px;color:#8E8E93;">' + escapeHtml(v.summary || '') + '</span>' +
                '</div>';

            var d = v.details || {};
            // Show the unified diff preview when L3 fails. Keep it compact —
            // Layer 3 surfaces *style* drift, the user mostly needs to see a
            // few representative diff lines, not the whole file.
            if (!v.passed && d.diff_preview && d.diff_preview.length) {
                html += '<div class="validation-details">';
                if (d.target_file) {
                    html += '<div class="vd-row" style="font-size:11px;color:#666;">'
                          + 'Compared against: <code>' + escapeHtml(d.target_file) + '</code></div>';
                }
                html += '<pre style="background:#1e1e1e;color:#d4d4d4;padding:10px;'
                      + 'border-radius:4px;font-size:11px;line-height:1.4;'
                      + 'overflow-x:auto;max-height:320px;margin-top:6px;">';
                d.diff_preview.forEach(function(line) {
                    var cls = '';
                    if (line.indexOf('+') === 0 && line.indexOf('+++') !== 0) cls = 'color:#6A9955;';
                    else if (line.indexOf('-') === 0 && line.indexOf('---') !== 0) cls = 'color:#F44747;';
                    else if (line.indexOf('@@') === 0) cls = 'color:#569CD6;';
                    html += '<span style="' + cls + '">' + escapeHtml(line) + '</span>\n';
                });
                html += '</pre>';
                html += '</div>';
            }
            return html;
        }

        function renderValidationWarnings(warnings) {
            var html = '<div class="validation-warnings">';
            html += '<div style="color:#F39C12;font-weight:600;margin-bottom:4px;">Warnings:</div>';
            for (var ename in warnings) {
                var w = warnings[ename];
                var parts = [];
                // entity_kind warning (nested under w.warnings)
                var warns = w.warnings || {};
                if (warns.entity_kind) {
                    parts.push('kind: actual=' + warns.entity_kind.actual + ' expected=' + warns.entity_kind.expected);
                }
                // FK constraint warnings (nested under w.warnings.constraints)
                var cons = warns.constraints || {};
                if (cons.fk_warnings && cons.fk_warnings.length) {
                    cons.fk_warnings.forEach(function(fw) {
                        if (fw.extra_fks && fw.extra_fks.length) {
                            fw.extra_fks.forEach(function(fk) {
                                parts.push('extra FK: ' + fk[0] + ' → ' + fk[1]);
                            });
                        }
                        if (fw.missing_fks && fw.missing_fks.length) {
                            fw.missing_fks.forEach(function(fk) {
                                parts.push('missing FK: ' + fk[0] + ' → ' + fk[1]);
                            });
                        }
                    });
                }
                if (cons.pk_type_warnings && cons.pk_type_warnings.length) {
                    cons.pk_type_warnings.forEach(function(pw) {
                        parts.push('PK(' + pw.columns.join(',') + ') types: ' + JSON.stringify(pw.actual) + ' != ' + JSON.stringify(pw.expected));
                    });
                }
                // Reference cardinality warnings (nested under w.references)
                var refs = w.references || {};
                if (refs.cardinality_warnings && refs.cardinality_warnings.length) {
                    refs.cardinality_warnings.forEach(function(cw) {
                        parts.push('ref(' + cw.name + '): actual=' + cw.actual + ' expected=' + cw.expected);
                    });
                }
                // Embedded cardinality warnings
                var emb = w.embedded || {};
                if (emb.cardinality_warnings && emb.cardinality_warnings.length) {
                    emb.cardinality_warnings.forEach(function(cw) {
                        parts.push('embedded(' + cw.name + '): actual=' + cw.actual + ' expected=' + cw.expected);
                    });
                }
                // Property key_type warnings
                var attrs = w.properties || {};
                if (attrs.key_warnings && attrs.key_warnings.length) {
                    attrs.key_warnings.forEach(function(kw) {
                        parts.push(kw.attr + '.' + kw.field + ': actual=' + kw.actual + ' expected=' + kw.expected);
                    });
                }
                // Property is_optional (nullability) warnings
                if (attrs.optional_warnings && attrs.optional_warnings.length) {
                    attrs.optional_warnings.forEach(function(ow) {
                        parts.push(ow.attr + '.is_optional: actual=' + ow.actual + ' expected=' + ow.expected);
                    });
                }
                // Edge cardinality warnings (graph)
                var edges = w.edges || {};
                if (edges.cardinality_warnings && edges.cardinality_warnings.length) {
                    edges.cardinality_warnings.forEach(function(cw) {
                        parts.push('edge(' + cw.name + '): actual=' + cw.actual + ' expected=' + cw.expected);
                    });
                }
                if (parts.length) html += '<div class="detail-entity">' + escapeHtml(ename) + ': ' + escapeHtml(parts.join('; ')) + '</div>';
            }
            html += '</div>';
            return html;
        }

        function highlightSmileSyntax(code, smileSyntax) {
            if (!code) return '';
            let result = escapeHtml(code);

            // Comments (-- ...)
            result = result.replace(/(--[^\n]*)/g, '<span class="smile-comment">$1</span>');

            // Keywords and data types from backend (SMILE_SYNTAX in core/pipeline.py)
            const keywords = (smileSyntax && smileSyntax.keywords) || [];
            keywords.forEach(kw => {
                result = result.replace(new RegExp('\\b' + kw + '\\b', 'g'), '<span class="smile-keyword">' + kw + '</span>');
            });

            const types = (smileSyntax && smileSyntax.types) || [];
            types.forEach(t => {
                result = result.replace(new RegExp('\\b' + t + '\\b', 'g'), '<span class="smile-type">' + t + '</span>');
            });

            // Version numbers
            result = result.replace(/:(\d+\.\d+(\.\d+)?)/g, ':<span class="smile-number">$1</span>');
            result = result.replace(/:(\d+)/g, ':<span class="smile-number">$1</span>');

            return result;
        }

        function toggleChanges(index) {
            const detail = document.getElementById('changes-' + index);
            const arrow = document.getElementById('arrow-' + index);
            const btn = arrow.parentElement;

            if (detail.classList.contains('show')) {
                detail.classList.remove('show');
                arrow.textContent = '▶';
                btn.innerHTML = '<span class="arrow" id="arrow-' + index + '">▶</span> Show Changes';
            } else {
                detail.classList.add('show');
                arrow.textContent = '▼';
                btn.innerHTML = '<span class="arrow" id="arrow-' + index + '">▼</span> Hide Changes';
            }
        }

        function renderChangesDetail(changes) {
            if (!changes || !changes.affected_entities || changes.affected_entities.length === 0) {
                return '<div class="no-changes">No structural changes</div>';
            }

            let html = '';
            changes.affected_entities.forEach(affected => {
                html += '<div class="affected-entity">';

                // Entity name with status
                let nameClass = '';
                let statusLabel = '';
                if (affected.status === 'new') {
                    nameClass = 'new';
                    statusLabel = '<span class="change-label">new</span>';
                } else if (affected.status === 'deleted') {
                    nameClass = 'deleted';
                    statusLabel = '<span class="change-label deleted">deleted</span>';
                }
                html += '<div class="entity-name-header ' + nameClass + '">' + affected.name + ' ' + statusLabel + '</div>';

                if (affected.status === 'new' || affected.status === 'modified') {
                    const entity = affected.entity;

                    // Show properties
                    if (entity.properties && entity.properties.length > 0) {
                        entity.properties.forEach(attr => {
                            const isNew = affected.new_properties && affected.new_properties.some(a => a.name === attr.name);
                            html += '<div class="change-item' + (isNew ? ' new' : '') + '">';
                            html += '<span class="change-prefix' + (isNew ? ' add' : '') + '">' + (isNew ? '+' : ' ') + '</span>';
                            html += attr.name + ': ' + attr.type;
                            if (attr.is_key) html += ' [' + getPkLabel(migrationData.target_type) + ']';
                            if (attr.is_optional) html += ' ?';
                            if (isNew) html += '<span class="change-label">new</span>';
                            html += '</div>';
                        });
                    }

                    // Show new embedded
                    if (affected.new_embedded && affected.new_embedded.length > 0) {
                        affected.new_embedded.forEach(emb => {
                            html += '<div class="change-item new">';
                            html += '<span class="change-prefix add">+</span>';
                            html += '&lt;&gt; ' + emb.name + ' [' + emb.target_end_cardinality + ']';
                            html += '<span class="change-label">new</span>';
                            html += '</div>';
                        });
                    } else if (entity.embedded && entity.embedded.length > 0 && affected.status === 'new') {
                        entity.embedded.forEach(emb => {
                            html += '<div class="change-item new">';
                            html += '<span class="change-prefix add">+</span>';
                            html += '&lt;&gt; ' + emb.name + ' [' + emb.target_end_cardinality + ']';
                            html += '<span class="change-label">new</span>';
                            html += '</div>';
                        });
                    }

                    // Show new references
                    if (affected.new_references && affected.new_references.length > 0) {
                        affected.new_references.forEach(ref => {
                            html += '<div class="change-item new">';
                            html += '<span class="change-prefix add">+</span>';
                            html += '→ ' + ref.name + ' → ' + ref.target;
                            html += '<span class="change-label">new</span>';
                            html += '</div>';
                        });
                    }

                    // Show deleted embedded
                    if (affected.deleted_embedded && affected.deleted_embedded.length > 0) {
                        affected.deleted_embedded.forEach(name => {
                            html += '<div class="change-item deleted">';
                            html += '<span class="change-prefix remove">-</span>';
                            html += '&lt;&gt; ' + name;
                            html += '<span class="change-label deleted">deleted</span>';
                            html += '</div>';
                        });
                    }

                    // Show deleted references
                    if (affected.deleted_references && affected.deleted_references.length > 0) {
                        affected.deleted_references.forEach(name => {
                            html += '<div class="change-item deleted">';
                            html += '<span class="change-prefix remove">-</span>';
                            html += '→ ' + name;
                            html += '<span class="change-label deleted">deleted</span>';
                            html += '</div>';
                        });
                    }

                    // Show type changed properties (for CAST and UNWIND operations)
                    if (affected.type_changed_properties && affected.type_changed_properties.length > 0) {
                        affected.type_changed_properties.forEach(attr => {
                            html += '<div class="change-item" style="color:#AF52DE;">';
                            html += '<span class="change-prefix" style="color:#AF52DE;">~</span>';
                            html += attr.name + ': <s style="color:#636366;">' + attr.old_type + '</s> → ' + attr.new_type;
                            html += '<span class="change-label" style="background:rgba(175,82,222,0.15);color:#AF52DE;">type changed</span>';
                            html += '</div>';
                        });
                    }
                }

                html += '</div>';
            });

            return html;
        }

        function formatOperationParams(type, params) {
            if (!params) return '';
            // Helper: escape HTML to prevent XSS and handle null/undefined
            function esc(v) { return escapeHtml(String(v != null ? v : '')); }
            // Helper: render a WHERE join condition (eq: a = b; edge: a -[:REL]-> b)
            function fmtJoinWhere(jcs) {
                if (!jcs || !jcs.length) return '';
                const parts = jcs.map(function(c) {
                    return c && c.type === 'edge'
                        ? esc(c.from) + ' -[:' + esc(c.rel) + ']-> ' + esc(c.to)
                        : esc(c.left) + ' = ' + esc(c.right);
                });
                return ' <span class="param-key">WHERE</span> <span class="param-value">' + parts.join(' AND ') + '</span>';
            }
            let html = '';

            switch(type) {
                case 'NEST':
                    html = '<span class="param-key">source:</span> <span class="param-value">' + esc(params.source) + '</span> → ';
                    html += '<span class="param-key">target:</span> <span class="param-value">' + esc(params.target) + '</span>';
                    if (params.alias) html += ' <span class="param-key">as:</span> <span class="param-value">' + esc(params.alias) + '</span>';
                    html += fmtJoinWhere(params.join_conditions);
                    break;
                case 'DELETE_FOREIGN_KEY':
                    html = '<span class="param-key">reference:</span> <span class="param-value">' + esc(params.reference) + '</span>';
                    break;
                case 'DELETE_ENTITY':
                    html = '<span class="param-key">entity:</span> <span class="param-value">' + esc(params.name) + '</span>';
                    break;
                case 'RENAME_PROPERTY':
                    html = '<span class="param-key">rename:</span> <span class="param-value">' + esc(params.old_name) + '</span> → <span class="param-value">' + esc(params.new_name) + '</span>';
                    if (params.entity) html += ' <span class="param-key">in:</span> <span class="param-value">' + esc(params.entity) + '</span>';
                    break;
                case 'FLATTEN':
                    html = '<span class="param-key">source:</span> <span class="param-value">' + esc(params.source) + '</span>';
                    html += ' <span style="color:#636366;font-size:12px;">(flatten to same table with prefix)</span>';
                    break;
                case 'UNNEST':
                    html = '<span class="param-value">' + esc(params.source_path) + '</span>';
                    if (params.properties && params.properties.length > 0) {
                        html += ':' + params.properties.map(a => esc(a)).join(',');
                    }
                    html += ' <span class="param-key">AS</span> <span class="param-value">' + esc(params.target) + '</span>';
                    if (params.carry_fields && params.carry_fields.length > 0) {
                        html += ' <span class="param-key">WITH</span> ';
                        html += params.carry_fields.map(cf =>
                            '<span class="param-value">' + esc(cf.source) + '</span> <span class="param-key">TO</span> <span class="param-value">' + esc(cf.target) + '</span>'
                        ).join(', ');
                    }
                    break;
                case 'UNWIND':
                    html = '<span class="param-value">' + esc(params.source) + '</span>';
                    if (params.mode === 'create_table' && params.target) {
                        html += ' → <span class="param-key">INTO</span> <span class="param-value">' + esc(params.target) + '</span>';
                    } else {
                        html += ' <span class="param-key">(expand in place)</span>';
                    }
                    break;
                case 'UNFLATTEN':
                    html = '<span class="param-value">' + esc(params.entity) + '</span>';
                    html += '(' + (params.fields || []).map(f => esc(f)).join(', ') + ')';
                    html += ' <span class="param-key">AS</span> <span class="param-value">' + esc(params.nested_name) + '</span>';
                    break;
                case 'WIND':
                    html = '<span class="param-value">' + esc(params.source) + '</span>';
                    html += ' <span class="param-key">(scalar → array)</span>';
                    break;
                case 'SPLIT':
                case 'SPLIT_FLAT':
                    html = '<span class="param-value">' + esc(params.source) + '</span> <span class="param-key">INTO</span> ';
                    if (params.parts && params.parts.length > 0) {
                        html += params.parts.map(p => '<span class="param-value">' + esc(p.name) + '</span>(' + (p.fields || []).map(f => esc(f)).join(', ') + ')').join(', ');
                    }
                    break;
                case 'ADD_KEY':
                    html = '<span class="param-key">key_type:</span> <span class="param-value">' + esc(params.key_type || 'PRIMARY') + '</span> ';
                    if (params.key_columns) {
                        const cols = params.key_columns.length > 1 ? '(' + params.key_columns.map(c => esc(c)).join(', ') + ')' : esc(params.key_columns[0]);
                        html += '<span class="param-key">columns:</span> <span class="param-value">' + cols + '</span>';
                    }
                    if (params.data_type) html += ' <span class="param-key">AS</span> <span class="param-value">' + esc(params.data_type) + '</span>';
                    if (params.entity) html += ' <span class="param-key">TO</span> <span class="param-value">' + esc(params.entity) + '</span>';
                    break;
                case 'DELETE_KEY':
                    html = '<span class="param-key">key_type:</span> <span class="param-value">' + esc(params.key_type) + '</span> ';
                    if (params.key_columns) {
                        const cols = params.key_columns.length > 1 ? '(' + params.key_columns.map(c => esc(c)).join(', ') + ')' : esc(params.key_columns[0]);
                        html += '<span class="param-key">columns:</span> <span class="param-value">' + cols + '</span>';
                    }
                    if (params.entity) html += ' <span class="param-key">FROM</span> <span class="param-value">' + esc(params.entity) + '</span>';
                    break;
                case 'ADD_FOREIGN_KEY': {
                    // Composite-capable: FK params are list-shaped
                    // (field_names / target_columns). Fall back to the legacy
                    // singular fields for safety if a caller still sends them.
                    const fkCols = (params.field_names && params.field_names.length)
                        ? (params.field_names.length > 1 ? '(' + params.field_names.map(esc).join(', ') + ')' : esc(params.field_names[0]))
                        : esc(params.field_name);
                    const tgtCols = (params.target_columns && params.target_columns.length)
                        ? params.target_columns.map(esc).join(', ')
                        : esc(params.target_column);
                    html = '<span class="param-key">field:</span> <span class="param-value">' + fkCols + '</span> ';
                    if (params.entity) html += '<span class="param-key">TO</span> <span class="param-value">' + esc(params.entity) + '</span> ';
                    html += '<span class="param-key">REFERENCES</span> <span class="param-value">' + esc(params.target_table) + '(' + tgtCols + ')</span>';
                    const fkCard = params.clauses && params.clauses.cardinality;
                    if (fkCard) html += ' <span class="param-key">CARDINALITY</span> <span class="param-value">' + esc(fkCard) + '</span>';
                    break;
                }
                case 'DELETE_EMBEDDED':
                    html = '<span class="param-key">embedded:</span> <span class="param-value">' + esc(params.embedded) + '</span>';
                    break;
                case 'ADD_PROPERTY':
                    html = '<span class="param-key">property:</span> <span class="param-value">' + esc(params.name) + '</span>';
                    if (params.data_type) html += ' <span class="param-key">type:</span> <span class="param-value">' + esc(params.data_type) + '</span>';
                    if (params.entity) html += ' <span class="param-key">TO</span> <span class="param-value">' + esc(params.entity) + '</span>';
                    break;
                case 'ADD_EMBEDDED':
                    html = '<span class="param-key">embedded:</span> <span class="param-value">' + esc(params.name) + '</span>';
                    if (params.entity) html += ' <span class="param-key">TO</span> <span class="param-value">' + esc(params.entity) + '</span>';
                    break;
                case 'ADD_ENTITY':
                    html = '<span class="param-key">entity:</span> <span class="param-value">' + esc(params.name) + '</span>';
                    if (params.source_entity) html += ' <span class="param-key">FROM</span> <span class="param-value">' + esc(params.source_entity) + '</span>';
                    if (params.target_entity) html += ' <span class="param-key">TO</span> <span class="param-value">' + esc(params.target_entity) + '</span>';
                    break;
                case 'ADD_LABEL':
                    html = '<span class="param-key">label:</span> <span class="param-value">' + esc(params.label) + '</span>';
                    if (params.entity) html += ' <span class="param-key">TO</span> <span class="param-value">' + esc(params.entity) + '</span>';
                    break;
                case 'DELETE_PROPERTY':
                    html = '<span class="param-key">target:</span> <span class="param-value">' + esc(params.target) + '</span>';
                    break;
                case 'DELETE_LABEL':
                    html = '<span class="param-key">label:</span> <span class="param-value">' + esc(params.label) + '</span>';
                    if (params.entity) html += ' <span class="param-key">FROM</span> <span class="param-value">' + esc(params.entity) + '</span>';
                    break;
                case 'RENAME_ENTITY':
                    html = '<span class="param-key">rename:</span> <span class="param-value">' + esc(params.old_name) + '</span> → <span class="param-value">' + esc(params.new_name) + '</span>';
                    break;
                case 'COPY_PROPERTY':
                    html = '<span class="param-value">' + esc(params.source) + '</span>';
                    html += ' <span class="param-key">TO</span> <span class="param-value">' + esc(params.target) + '</span>';
                    html += fmtJoinWhere(params.join_conditions);
                    break;
                case 'COPY_ENTITY':
                    html = '<span class="param-key">entity:</span> <span class="param-value">' + esc(params.source) + '</span>';
                    html += ' <span class="param-key">AS</span> <span class="param-value">' + esc(params.target) + '</span>';
                    break;
                case 'MOVE_PROPERTY':
                    html = '<span class="param-value">' + esc(params.source) + '</span>';
                    html += ' <span class="param-key">TO</span> <span class="param-value">' + esc(params.target) + '</span>';
                    html += fmtJoinWhere(params.join_conditions);
                    break;
                case 'MERGE':
                    html = '<span class="param-value">' + esc(params.source1) + '</span>, ';
                    html += '<span class="param-value">' + esc(params.source2) + '</span>';
                    html += fmtJoinWhere(params.join_conditions);
                    html += ' <span class="param-key">INTO</span> <span class="param-value">' + esc(params.target) + '</span>';
                    if (params.alias) html += ' <span class="param-key">AS</span> <span class="param-value">' + esc(params.alias) + '</span>';
                    break;
                case 'CAST_PROPERTY':
                    html = '<span class="param-key">target:</span> <span class="param-value">' + esc(params.target) + '</span>';
                    html += ' <span class="param-key">TO</span> <span class="param-value">' + esc(params.type || params.data_type) + '</span>';
                    break;
                case 'CAST_ENTITY':
                    html = '<span class="param-key">entity:</span> <span class="param-value">' + esc(params.target) + '</span>';
                    html += ' <span class="param-key">TO</span> <span class="param-value">' + esc(params.entity_kind) + '</span>';
                    break;
                case 'CAST_CONSTRAINT':
                    html = '<span class="param-key">target:</span> <span class="param-value">' + esc(params.target) + '</span>';
                    html += ' <span class="param-key">TO</span> <span class="param-value">' + esc(params.constraint_type) + '</span>';
                    break;
                case 'ADD_CONSTRAINT': {
                    // Compact rendering for the three AS-branches. The body
                    // discriminator lives in params.body_kind; per-branch
                    // fields are populated only for that branch.
                    html = '<span class="param-key">target:</span> <span class="param-value">' + esc(params.target) + '</span>';
                    const bodyKind = params.body_kind || '';
                    if (bodyKind === 'REFERENCE') {
                        const cols = (params.ref_target_columns || []).join(', ');
                        html += ' <span class="param-key">AS REFERENCE ' + esc(params.ref_kind || '') + ' TO</span> ';
                        html += '<span class="param-value">' + esc(params.ref_target_table || '') + '(' + esc(cols) + ')</span>';
                        if (params.ref_cardinality) {
                            html += ' <span class="param-key">CARDINALITY</span> <span class="param-value">' + esc(params.ref_cardinality) + '</span>';
                        }
                    } else if (bodyKind === 'CHECK') {
                        // check_expression is a CheckExpr AST node serialized
                        // as a dict; render its top-level kind and a short
                        // summary of the leaf, falling back to JSON for
                        // composite expressions.
                        const expr = params.check_expression || {};
                        let exprStr = '';
                        if (expr.kind === 'cmp') {
                            exprStr = esc(expr.field) + ' ' + esc(expr.op) + ' ' + esc(expr.literal);
                        } else if (expr.kind === 'in') {
                            exprStr = esc(expr.field) + ' IN (' + (expr.values || []).map(esc).join(', ') + ')';
                        } else if (expr.kind === 'between') {
                            exprStr = esc(expr.field) + ' BETWEEN ' + esc(expr.low) + ' AND ' + esc(expr.high);
                        } else if (expr.kind === 'regex') {
                            exprStr = esc(expr.field) + ' MATCHES ' + esc(expr.pattern);
                        } else if (expr.kind === 'isnull') {
                            exprStr = esc(expr.field) + (expr.is_null ? ' IS NULL' : ' IS NOT NULL');
                        } else if (expr.kind === 'raw') {
                            exprStr = 'RAW "' + esc(expr.raw_text) + '"';
                        } else {
                            exprStr = esc(JSON.stringify(expr));
                        }
                        html += ' <span class="param-key">AS CHECK</span> <span class="param-value">' + exprStr + '</span>';
                    } else if (bodyKind === 'EXISTENCE') {
                        html += ' <span class="param-key">AS EXISTENCE</span>';
                    }
                    break;
                }
                case 'DELETE_CONSTRAINT':
                    html = '<span class="param-key">target:</span> <span class="param-value">' + esc(params.target) + '</span>';
                    break;
                case 'RECARD':
                    html = '<span class="param-key">target:</span> <span class="param-value">' + esc(params.target) + '</span>';
                    html += ' <span class="param-key">TO</span> <span class="param-value">' + esc(params.cardinality) + '</span>';
                    break;
                case 'TRANSFORM':
                    html = '<span class="param-key">entity:</span> <span class="param-value">' + esc(params.name) + '</span>';
                    html += ' <span class="param-key">TO</span> <span class="param-value">' + esc(params.target_type) + '</span>';
                    if (params.source_entity) html += ' <span class="param-key">BETWEEN</span> <span class="param-value">' + esc(params.source_entity) + '</span> <span class="param-key">AND</span> <span class="param-value">' + esc(params.target_entity) + '</span>';
                    break;
                default:
                    html = Object.entries(params).map(([k, v]) => {
                        if (typeof v === 'object') return '';
                        return '<span class="param-key">' + esc(k) + ':</span> <span class="param-value">' + esc(v) + '</span>';
                    }).filter(x => x).join(' ');
            }
            return html;
        }

        function escapeHtml(text) {
            if (!text) return '';
            return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }

        // Filter out __relationship_types__ special key from entity dicts
        function filterEntities(entities) {
            if (!entities) return {};
            const filtered = {};
            Object.entries(entities).forEach(([k, v]) => {
                if (!k.startsWith('__')) filtered[k] = v;
            });
            return filtered;
        }

        function generateDOTSyntax(entities) {
            const entityList = Object.values(filterEntities(entities));
            if (entityList.length === 0) return 'digraph { label="No entities" }';

            // Collect all edges (FK references, embedded, graph edges)
            const connections = {};  // entity_name -> Set of connected entity names
            const edgeList = [];
            const addedRels = new Set();
            entityList.forEach(e => { connections[e.name] = new Set(); });

            entityList.forEach(entity => {
                (entity.references || []).forEach(ref => {
                    const key = ref.target + '->' + entity.name + ':' + ref.name;
                    if (!addedRels.has(key)) {
                        addedRels.add(key);
                        if (!connections[ref.target]) connections[ref.target] = new Set();
                        connections[entity.name].add(ref.target);
                        connections[ref.target].add(entity.name);
                        // A FK reference is many-to-one: the referenced (parent/tail) end uses
                        // target_end_cardinality, the referencing (child/head) end uses
                        // source_end_cardinality. Using only target_end_cardinality previously
                        // rendered every NOT NULL FK as 1:1 instead of N:1.
                        const fmt = c => ({ '1..1': '1', '0..n': '0..N', '1..n': '1..N', 'n..m': 'N..M' }[c] || c);
                        const tailLabel = fmt(ref.target_end_cardinality || '1..1');   // parent / referenced end
                        const headLabel = fmt(ref.source_end_cardinality || '0..n');   // child / referencing end
                        edgeList.push({ from: ref.target, to: entity.name, headLabel, tailLabel, label: ref.name });
                    }
                });
                (entity.embedded || []).forEach(emb => {
                    const key = entity.name + '->emb:' + emb.target;
                    if (!addedRels.has(key)) {
                        addedRels.add(key);
                        if (!connections[emb.target]) connections[emb.target] = new Set();
                        connections[entity.name].add(emb.target);
                        connections[emb.target].add(entity.name);
                        const card = emb.target_end_cardinality || '1..1';
                        let headLabel = '1', tailLabel = '1';
                        if (card === '1..n' || card === '0..n' || card === 'n..m') headLabel = 'N';
                        edgeList.push({ from: entity.name, to: emb.target, headLabel, tailLabel, label: 'embedded' });
                    }
                });
                (entity.edges || []).forEach(edge => {
                    const key = entity.name + '->edge:' + edge.target + ':' + edge.name;
                    if (!addedRels.has(key)) {
                        addedRels.add(key);
                        if (!connections[edge.target]) connections[edge.target] = new Set();
                        connections[entity.name].add(edge.target);
                        connections[edge.target].add(entity.name);
                        const card = edge.target_end_cardinality || '1..1';
                        let headLabel = '1', tailLabel = '1';
                        if (card === '1..n' || card === '0..n' || card === 'n..m') headLabel = 'N';
                        edgeList.push({ from: entity.name, to: edge.target, headLabel, tailLabel, label: edge.name });
                    }
                });
            });

            // BFS from center node (most connections) to assign rank layers
            let center = entityList[0].name;
            let maxConn = 0;
            Object.entries(connections).forEach(([name, conns]) => {
                if (conns.size > maxConn) { maxConn = conns.size; center = name; }
            });

            const ranks = {};
            const visited = new Set();
            const queue = [[center, 0]];
            visited.add(center);
            while (queue.length > 0) {
                const [node, rank] = queue.shift();
                ranks[node] = rank;
                (connections[node] || new Set()).forEach(neighbor => {
                    if (!visited.has(neighbor)) {
                        visited.add(neighbor);
                        queue.push([neighbor, rank + 1]);
                    }
                });
            }
            // Any unvisited entities get highest rank
            entityList.forEach(e => { if (!(e.name in ranks)) ranks[e.name] = 99; });

            // Group by rank
            const rankGroups = {};
            Object.entries(ranks).forEach(([name, rank]) => {
                if (!rankGroups[rank]) rankGroups[rank] = [];
                rankGroups[rank].push(name);
            });

            // Build entity map for quick lookup
            const entityMap = {};
            entityList.forEach(e => { entityMap[e.name] = e; });

            // Generate DOT — Apple HIG color palette
            let dot = 'digraph ER {\n';
            dot += '  rankdir=LR;\n';
            dot += '  graph [fontname="Helvetica Neue, Helvetica, Arial", nodesep=0.8, ranksep=1.2, bgcolor="transparent"];\n';
            dot += '  node [shape=plain, fontname="Helvetica Neue, Helvetica, Arial", fontsize=11];\n';
            dot += '  edge [fontname="Helvetica Neue, Helvetica, Arial", fontsize=9, color="#8E8E93", penwidth=1.2];\n\n';

            // Rank constraints
            Object.entries(rankGroups).sort((a,b) => a[0]-b[0]).forEach(([rank, names]) => {
                dot += '  { rank=same; ' + names.map(n => '"' + n + '"').join('; ') + '; }\n';
            });
            dot += '\n';

            // Node definitions with HTML-like labels
            entityList.forEach(entity => {
                const isCenter = entity.name === center;
                const borderColor = isCenter ? '#007AFF' : '#D2D2D7';
                const headerBg = isCenter ? '#007AFF' : '#3A3A3C';
                dot += '  "' + entity.name + '" [label=<\n';
                dot += '    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="' + borderColor + '" BGCOLOR="white">\n';
                dot += '      <TR><TD COLSPAN="3" BGCOLOR="' + headerBg + '" ALIGN="CENTER"><FONT COLOR="white"><B>' + entity.name + '</B></FONT></TD></TR>\n';

                const refNames = new Set((entity.references || []).map(r => r.name));
                entity.properties.forEach(attr => {
                    const isFk = refNames.has(attr.name);
                    let badge = '';
                    const _pkl = getPkLabel(migrationData.target_type);
                    if (attr.is_key && isFk) badge = '<FONT COLOR="#FF9500"> ' + _pkl + ',FK</FONT>';
                    else if (attr.is_key) badge = '<FONT COLOR="#007AFF"> ' + _pkl + '</FONT>';
                    else if (isFk) badge = '<FONT COLOR="#FF3B30"> FK</FONT>';
                    dot += '      <TR><TD ALIGN="LEFT">' + attr.name + '</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">' + attr.type + '</FONT></TD><TD ALIGN="RIGHT">' + badge + '</TD></TR>\n';
                });
                dot += '    </TABLE>\n';
                dot += '  >];\n\n';
            });

            // Edges with cardinality labels + arrow pointing to "many" side
            edgeList.forEach(edge => {
                const isSelfRef = edge.from === edge.to;
                dot += '  "' + edge.from + '" -> "' + edge.to + '" [';
                dot += 'arrowhead=vee, arrowsize=0.8, ';
                dot += 'headlabel="' + edge.headLabel + '", ';
                dot += 'taillabel="' + edge.tailLabel + '", ';
                dot += 'labeldistance=2.2, ';
                if (isSelfRef) dot += 'labelangle=40, ';
                dot += 'label="  ' + edge.label + '  ", ';
                dot += 'fontcolor="#8E8E93"';
                dot += '];\n';
            });

            dot += '}\n';
            return dot;
        }

        function generateERDiagram(entities) {
            const containerId = 'er-dot-' + (erDiagramCounter++);
            const dot = generateDOTSyntax(entities);
            pendingDotRenders.push({ id: containerId, dot: dot });
            return '<div class="er-dot-container" id="' + containerId + '"><div style="color:#8E8E93;font-size:13px;">Loading ER diagram...</div></div>';
        }

        // Dynamic graph props storage (populated by generateGraphDiagram)
        let _dynNodeProps = { source: {}, target: {} };
        let _dynEdgeProps = { source: {}, target: {} };
        // Extra Neo4j labels per node (multi-label), shown in the click card.
        let _dynNodeLabels = { source: {}, target: {} };

        function generateGraphDiagram(entities, origin) {
            origin = origin || 'target';
            const entityList = Object.values(filterEntities(entities));
            if (entityList.length === 0) return '';

            // Build dynamic property lookups from entity data (keyed by origin)
            _dynNodeProps[origin] = {};
            _dynEdgeProps[origin] = {};
            _dynNodeLabels[origin] = {};
            entityList.forEach(entity => {
                _dynNodeProps[origin][entity.name] = (entity.properties || []).map(a => ({
                    n: a.name, t: a.type, k: a.is_key
                }));
                _dynNodeLabels[origin][entity.name] = entity.labels || [];
            });
            const dynRelTypes = entities['__relationship_types__'] || {};
            Object.entries(dynRelTypes).forEach(([name, rt]) => {
                _dynEdgeProps[origin][rt.rel_name || name] = {
                    from: rt.source_entity || '',
                    to: rt.target_entity || '',
                    props: (rt.properties || []).map(a => ({ n: a.name, t: a.type }))
                };
            });

            // ── Step 1: Collect all edges ──
            const allEdges = [];
            const addedEdges = new Set();
            entityList.forEach(entity => {
                (entity.edges || []).forEach(edge => {
                    const key = entity.name + '->' + edge.target + ':' + edge.name;
                    if (!addedEdges.has(key)) {
                        addedEdges.add(key);
                        allEdges.push({ source: entity.name, target: edge.target, name: edge.name });
                    }
                });
            });
            const relTypes = entities['__relationship_types__'] || {};
            Object.entries(relTypes).forEach(([name, rt]) => {
                const key = (rt.source_entity||'') + '->' + (rt.target_entity||'') + ':' + (rt.rel_name||name);
                if (rt.source_entity && rt.target_entity && !addedEdges.has(key)) {
                    addedEdges.add(key);
                    allEdges.push({ source: rt.source_entity, target: rt.target_entity, name: rt.rel_name || name });
                }
            });

            // ── Step 2: Count connections per node ──
            const connCount = {};
            entityList.forEach(e => { connCount[e.name] = 0; });
            allEdges.forEach(e => {
                if (connCount[e.source] !== undefined) connCount[e.source]++;
                if (connCount[e.target] !== undefined) connCount[e.target]++;
            });

            // ── Step 3: Pick hub nodes (top N by connection count) ──
            const sorted = Object.entries(connCount).sort((a, b) => b[1] - a[1]);
            let numHubs = entityList.length >= 10 ? 3 : (entityList.length >= 5 ? 2 : 1);
            numHubs = Math.min(numHubs, sorted.length);
            const hubNames = sorted.slice(0, numHubs).map(e => e[0]);

            // ── Step 4: Assign each non-hub node to its most-connected hub ──
            const clusters = {};
            hubNames.forEach(h => { clusters[h] = []; });

            entityList.forEach(entity => {
                if (hubNames.includes(entity.name)) return;
                let bestHub = hubNames[0];
                let bestScore = -1;
                hubNames.forEach(hub => {
                    let score = 0;
                    allEdges.forEach(edge => {
                        if ((edge.source === entity.name && edge.target === hub) ||
                            (edge.target === entity.name && edge.source === hub)) {
                            score += 2;
                        }
                    });
                    if (score > bestScore || (score === bestScore && clusters[hub].length < clusters[bestHub].length)) {
                        bestScore = score;
                        bestHub = hub;
                    }
                });
                clusters[bestHub].push(entity.name);
            });

            // ── Step 5: Calculate positions ──
            const W = 960, H = entityList.length >= 7 ? 760 : 700;
            const hubR = 30, satR = 22;
            const pos = {};

            const hubCenters = numHubs === 1
                ? [{ x: W/2, y: H/2 }]
                : numHubs === 2
                    ? [{ x: W*0.25, y: H*0.5 }, { x: W*0.75, y: H*0.5 }]
                    : [{ x: W*0.28, y: H*0.50 }, { x: W*0.72, y: H*0.25 }, { x: W*0.72, y: H*0.75 }];

            hubNames.forEach((hub, i) => {
                const hc = hubCenters[i];
                pos[hub] = { x: hc.x, y: hc.y, isHub: true, hubIdx: i };
                const sats = clusters[hub];
                if (sats.length === 0) return;
                const ringR = Math.max(95, Math.min(180, sats.length * 22 + 10));
                sats.forEach((name, j) => {
                    const angle = (2 * Math.PI * j / sats.length) - Math.PI / 2;
                    pos[name] = {
                        x: hc.x + ringR * Math.cos(angle),
                        y: hc.y + ringR * Math.sin(angle),
                        isHub: false, hubIdx: i
                    };
                });
            });

            // ── Step 6: Build SVG ──
            const hubThemes = [
                { fill:'#DBEAFE', stroke:'#3B82F6', text:'#1E40AF', satFill:'#EFF6FF', satStroke:'#93C5FD', satText:'#1E3A5F' },
                { fill:'#FEF3C7', stroke:'#F59E0B', text:'#92400E', satFill:'#FFFBEB', satStroke:'#FCD34D', satText:'#78350F' },
                { fill:'#D1FAE5', stroke:'#10B981', text:'#065F46', satFill:'#ECFDF5', satStroke:'#6EE7B7', satText:'#064E3B' }
            ];
            const interEdge = '#94A3B8';
            const selfEdge = '#E11D48';
            const labelColor = '#475569';

            let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;max-width:960px;height:auto;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">';

            // Arrowhead markers
            svg += '<defs>';
            svg += '<marker id="ahG" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="' + interEdge + '"/></marker>';
            svg += '<marker id="ahS" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="' + selfEdge + '"/></marker>';
            for (let i = 0; i < numHubs; i++) {
                svg += '<marker id="ahC' + i + '" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="' + hubThemes[i].stroke + '" opacity="0.6"/></marker>';
            }
            svg += '</defs>';

            // Cluster background circles (subtle dashed)
            hubNames.forEach((hub, i) => {
                const hc = hubCenters[i];
                const sats = clusters[hub];
                if (sats.length === 0) return;
                const bgR = Math.max(115, sats.length * 20 + 48);
                svg += '<circle cx="' + hc.x + '" cy="' + hc.y + '" r="' + bgR + '" fill="' + hubThemes[i].satFill + '" stroke="' + hubThemes[i].satStroke + '" stroke-width="1" stroke-dasharray="6,3" opacity="0.4"/>';
            });

            // Group edges by pair for parallel offset
            const edgesByPair = {};
            allEdges.forEach(edge => {
                const pairKey = [edge.source, edge.target].sort().join('|');
                if (!edgesByPair[pairKey]) edgesByPair[pairKey] = [];
                edgesByPair[pairKey].push(edge);
            });

            // Draw edges
            allEdges.forEach(edge => {
                const s = pos[edge.source], t = pos[edge.target];
                if (!s || !t) return;
                const isSelf = edge.source === edge.target;
                const sameCluster = s.hubIdx === t.hubIdx;
                let eColor, marker, eOpacity;
                if (isSelf) {
                    eColor = selfEdge; marker = 'url(#ahS)'; eOpacity = '0.8';
                } else if (sameCluster) {
                    eColor = hubThemes[s.hubIdx].stroke; marker = 'url(#ahC' + s.hubIdx + ')'; eOpacity = '0.4';
                } else {
                    eColor = interEdge; marker = 'url(#ahG)'; eOpacity = '0.65';
                }

                const pairKey = [edge.source, edge.target].sort().join('|');
                const pairEdges = edgesByPair[pairKey] || [];
                const edgeIdx = pairEdges.indexOf(edge);

                if (isSelf) {
                    const nodeR = s.isHub ? hubR : satR;
                    const loopR = 25 + edgeIdx * 12;
                    svg += '<path d="M ' + (s.x-8) + ' ' + (s.y-nodeR) + ' C ' + (s.x-loopR*1.2) + ' ' + (s.y-nodeR-loopR*1.5) + ', ' + (s.x+loopR*1.2) + ' ' + (s.y-nodeR-loopR*1.5) + ', ' + (s.x+8) + ' ' + (s.y-nodeR) + '" fill="none" stroke="' + eColor + '" stroke-width="1.3" opacity="' + eOpacity + '" marker-end="' + marker + '"/>';
                    svg += '<text x="' + s.x + '" y="' + (s.y-nodeR-loopR*0.8) + '" text-anchor="middle" font-size="7" fill="' + eColor + '" font-weight="500" style="cursor:pointer" onclick="toggleGraphCard(event,&apos;edge&apos;,&apos;' + escapeHtml(edge.name) + '&apos;,&apos;'+origin+'&apos;)">' + escapeHtml(edge.name) + '</text>';
                } else {
                    const dx = t.x-s.x, dy = t.y-s.y;
                    const dist = Math.sqrt(dx*dx+dy*dy);
                    if (dist < 0.1) return;
                    const nx = dx/dist, ny = dy/dist;
                    const sR = s.isHub ? hubR : satR;
                    const tR = t.isHub ? hubR : satR;
                    const x1 = s.x + nx*(sR+2), y1 = s.y + ny*(sR+2);
                    const x2 = t.x - nx*(tR+10), y2 = t.y - ny*(tR+10);
                    const offset = pairEdges.length > 1 ? (edgeIdx-(pairEdges.length-1)/2)*18 : 0;
                    const mx = (x1+x2)/2 + (-ny)*offset;
                    const my = (y1+y2)/2 + nx*offset;

                    if (Math.abs(offset) > 0.1) {
                        svg += '<path d="M '+x1+' '+y1+' Q '+mx+' '+my+' '+x2+' '+y2+'" fill="none" stroke="'+eColor+'" stroke-width="1.1" opacity="'+eOpacity+'" marker-end="'+marker+'"/>';
                    } else {
                        svg += '<line x1="'+x1+'" y1="'+y1+'" x2="'+x2+'" y2="'+y2+'" stroke="'+eColor+'" stroke-width="1.1" opacity="'+eOpacity+'" marker-end="'+marker+'"/>';
                    }
                    svg += '<text x="'+mx+'" y="'+(my-3)+'" text-anchor="middle" font-size="7" fill="'+labelColor+'" opacity="0.8" style="cursor:pointer" onclick="toggleGraphCard(event,&apos;edge&apos;,&apos;'+escapeHtml(edge.name)+'&apos;,&apos;'+origin+'&apos;)">'+escapeHtml(edge.name)+'</text>';
                }
            });

            // Draw hub nodes (larger, bold colors, clickable)
            hubNames.forEach((hub, i) => {
                const p = pos[hub];
                const th = hubThemes[i];
                const clk = ' style="cursor:pointer" onclick="toggleGraphCard(event,&apos;node&apos;,&apos;'+escapeHtml(hub)+'&apos;,&apos;'+origin+'&apos;)"';
                svg += '<circle cx="'+p.x+'" cy="'+p.y+'" r="'+hubR+'" fill="'+th.fill+'" stroke="'+th.stroke+'" stroke-width="2.5"'+clk+'/>';
                const fs = hub.length > 10 ? 9 : (hub.length > 7 ? 10 : 11);
                svg += '<text x="'+p.x+'" y="'+(p.y+4)+'" text-anchor="middle" font-size="'+fs+'" font-weight="700" fill="'+th.text+'"'+clk+'>'+escapeHtml(hub)+'</text>';
            });

            // Draw satellite nodes (smaller, lighter colors matching their hub, clickable)
            entityList.forEach(entity => {
                if (hubNames.includes(entity.name)) return;
                const p = pos[entity.name];
                if (!p) return;
                const th = hubThemes[p.hubIdx];
                const clk = ' style="cursor:pointer" onclick="toggleGraphCard(event,&apos;node&apos;,&apos;'+escapeHtml(entity.name)+'&apos;,&apos;'+origin+'&apos;)"';
                svg += '<circle cx="'+p.x+'" cy="'+p.y+'" r="'+satR+'" fill="'+th.satFill+'" stroke="'+th.satStroke+'" stroke-width="1.5"'+clk+'/>';
                const fs = entity.name.length > 11 ? 7.5 : (entity.name.length > 8 ? 8.5 : 9.5);
                svg += '<text x="'+p.x+'" y="'+(p.y+3)+'" text-anchor="middle" font-size="'+fs+'" font-weight="600" fill="'+th.satText+'"'+clk+'>'+escapeHtml(entity.name)+'</text>';
            });

            // Summary label at bottom
            svg += '<text x="' + (W/2) + '" y="' + (H-12) + '" text-anchor="middle" font-size="11" fill="#94A3B8" font-weight="500">' + entityList.length + ' Nodes, ' + allEdges.length + ' Relationships — Click node or relationship to view properties</text>';

            svg += '</svg>';
            return '<div class="neo4j-graph-wrap"><div class="graph-svg-container">' + svg + '</div></div>';
        }

        function generateChebotkoDiagram(entities) {
            const entityList = Object.values(filterEntities(entities));
            if (entityList.length === 0) return '';

            let html = '<div class="chebotko-diagram">';
            entityList.forEach(entity => {
                html += '<div class="chebotko-table">';
                html += '<div class="chebotko-header">' + escapeHtml(entity.name) + '</div>';
                html += '<table class="chebotko-cols">';

                (entity.properties || []).forEach(attr => {
                    let marker = '';
                    const keyType = attr.key_type || null;
                    if (keyType === 'partition') {
                        marker = '<span class="ck-marker pk">K&#x2191;</span>';
                    } else if (keyType === 'clustering') {
                        marker = '<span class="ck-marker ck">C&#x2191;</span>';
                    } else if (attr.is_key) {
                        marker = '<span class="ck-marker pk">K&#x2191;</span>';
                    }
                    html += '<tr>';
                    html += '<td class="ck-marker-cell">' + marker + '</td>';
                    html += '<td class="ck-name">' + escapeHtml(attr.name) + '</td>';
                    html += '<td class="ck-type">' + escapeHtml(attr.type) + '</td>';
                    html += '</tr>';
                });

                html += '</table></div>';
            });
            html += '</div>';
            return html;
        }

        function syntaxHighlightJSON(json) {
            if (!json) return '';
            if (typeof json === 'string') { try { json = JSON.stringify(JSON.parse(json), null, 2); } catch (e) {} }
            else { json = JSON.stringify(json, null, 2); }
            return json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
                .replace(/: "([^"]*)"/g, ': <span class="json-string">"$1"</span>')
                .replace(/: (\d+)/g, ': <span class="json-number">$1</span>')
                .replace(/[{}\[\]]/g, '<span class="json-bracket">$&</span>');
        }

        function renderMigrationProcess() {
            const container = document.getElementById('tab-migration');
            const targetType = migrationData.target_type;

            // Meta V1 and Meta V2 entities (must be aligned)
            const metaEntities = new Set([...Object.keys(filterEntities(migrationData.meta_v1 || {})), ...Object.keys(filterEntities(migrationData.result || {}))]);
            const newEntities = new Set((migrationData.changes || []).filter(c => c.startsWith('FLATTEN:') || c.startsWith('NEST:') || c.startsWith('UNWIND:') || c.startsWith('ADD_ENTITY:')).map(c => {
                const p = c.split(':');
                const val = p[1] || '';
                if (val.includes('->')) return val.split('->').pop();
                if (val.includes('.')) return val;
                return val;
            }).filter(x => x));

            let html = '<div class="migration-content"><div class="legend">';
            html += '<div class="legend-item"><span class="legend-dot new"></span>New Entity</div>';
            html += '<div class="legend-item"><span class="legend-dot reference"></span>Reference (FK)</div>';
            html += '<div class="legend-item"><span class="legend-dot embedded"></span>Embedded</div>';
            html += '<div class="legend-item"><span class="legend-dot edge"></span>Edge (Graph)</div>';
            const _pkLegend = migrationData.target_type === 'Graph' ? 'Node Key' : migrationData.target_type === 'Document' ? 'Document ID' : 'Primary Key';
            html += '<div class="legend-item"><span class="legend-dot pk"></span>' + _pkLegend + '</div></div>';

            // Four-column layout (dense for 7+ entities)
            const entityCount = Object.keys(filterEntities(migrationData.result || {})).length;
            const denseClass = entityCount >= 7 ? ' dense-layout' : '';
            html += '<div class="four-column-layout' + denseClass + '">';

            // Column 1: Source Schema (original nested structure before reverse eng)
            html += '<div class="independent-column source-column">';
            html += '<div class="column-header"><h3>Source</h3><div class="subtitle">' + migrationData.source_type + '</div></div>';
            html += '<div class="column-content">';
            const sourceDataRaw = migrationData.original_source && Object.keys(migrationData.original_source).length > 0
                ? migrationData.original_source
                : migrationData.source;
            const sourceData = filterEntities(sourceDataRaw || {});
            Object.values(sourceData).forEach(entity => {
                html += renderNestedEntityCard(entity);
            });
            html += '</div></div>';

            // Column 2 & 3: Meta V1 and Meta V2 (aligned)
            html += '<div class="meta-aligned-columns">';
            html += '<div class="meta-grid">';

            // Headers
            html += '<div class="column-header"><h3>Meta V1</h3><div class="subtitle">Unified Meta</div></div>';
            html += '<div class="column-header"><h3>Meta V2</h3><div class="subtitle">Result</div></div>';

            // Aligned entity rows
            Array.from(metaEntities).sort().forEach(name => {
                // Meta V1 cell
                const v1Entity = (migrationData.meta_v1 || {})[name];
                html += '<div class="grid-cell">';
                if (!v1Entity) {
                    html += '<div class="entity-card placeholder-card"><div class="entity-name placeholder-name">' + name + '</div>';
                    html += '<div class="entity-body placeholder-body">(--)</div></div>';
                } else {
                    html += renderEntityCard(v1Entity, false, true);
                }
                html += '</div>';

                // Meta V2 cell
                const v2Entity = (migrationData.result || {})[name];
                html += '<div class="grid-cell">';
                if (!v2Entity) {
                    html += '<div class="entity-card placeholder-card"><div class="entity-name placeholder-name">' + name + '</div>';
                    html += '<div class="entity-body placeholder-body">(--)</div></div>';
                } else {
                    const isNew = newEntities.has(name);
                    html += renderEntityCard(v2Entity, isNew, false);
                }
                html += '</div>';
            });

            html += '</div></div>';

            // Column 4: Target Schema (Forward Engineering result - Schema format)
            html += '<div class="independent-column target-column">';
            html += '<div class="column-header"><h3>Target</h3><div class="subtitle">' + targetType + '</div></div>';
            html += '<div class="column-content">';
            if (targetType === 'Relational') {
                // Relational: DDL only (ER Diagram is in Schema Comparison tab)
                html += '<div class="schema-view"><pre class="schema-code">' + escapeHtml(migrationData.exported_target) + '</pre></div>';
            } else if (targetType === 'Graph') {
                // Graph: Entity cards + GraphQL SDL (Graph Diagram is in Schema Comparison tab)
                const targetEntities = migrationData.target_with_db_types || migrationData.result;
                const graphEntities = Object.values(filterEntities(targetEntities));
                graphEntities.forEach(entity => {
                    html += renderEntityCard(entity, newEntities.has(entity.name), false);
                });
                html += '<div class="schema-view"><pre class="schema-code">' + escapeHtml(migrationData.exported_target) + '</pre></div>';
            } else if (targetType === 'Columnar') {
                // Columnar: CQL only (Chebotko Diagram is in Schema Comparison tab)
                html += '<div class="schema-view"><pre class="schema-code">' + escapeHtml(migrationData.exported_target) + '</pre></div>';
            } else {
                // Document: card view + JSON Schema
                const targetNested = filterEntities(migrationData.target_nested || {});
                if (Object.keys(targetNested).length > 0) {
                    Object.values(targetNested).forEach(entity => {
                        html += renderNestedEntityCard(entity);
                    });
                } else {
                    html += '<div class="json-view">' + syntaxHighlightJSON(migrationData.exported_target) + '</div>';
                }
            }
            html += '</div></div>';

            html += '</div>'; // end four-column-layout

            html += '<div class="validation"><div class="validation-header"><h2>Transformation Summary</h2>';
            html += '<div class="validation-status passed">Complete</div></div><div class="validation-stats">';
            html += '<div class="stat-card"><div class="stat-value">' + migrationData.operations_count + '</div><div class="stat-label">Operations</div></div>';
            html += '<div class="stat-card"><div class="stat-value">' + ((migrationData.stats || {}).source_count || 0) + '</div><div class="stat-label">Source Entities</div></div>';
            html += '<div class="stat-card"><div class="stat-value">' + ((migrationData.stats || {}).result_count || 0) + '</div><div class="stat-label">Result Entities</div></div>';
            html += '<div class="stat-card"><div class="stat-value">' + targetType + '</div><div class="stat-label">Target Format</div></div>';
            html += '</div></div></div>';
            container.innerHTML = html;

            setTimeout(() => flushDotRenders(), 50);
        }

        function renderEntityCard(entity, isNew, isSource) {
            let html = '<div class="entity-card' + (isNew ? ' new' : '') + '"><div class="entity-name' + (isNew ? ' new' : '') + '">' + entity.name + '</div><div class="entity-body">';

            const refMap = {};
            (entity.references || []).forEach(r => { refMap[r.name] = r.target; });

            // Get key_registry info for this entity (with defensive checks)
            let keyInfo = null;
            try {
                if (migrationData && migrationData.key_registry && migrationData.key_registry[entity.name]) {
                    keyInfo = migrationData.key_registry[entity.name];
                }
            } catch(e) { keyInfo = null; }

            (entity.properties || []).forEach(a => {
                html += '<div class="property"><span class="attr-name">' + a.name + '</span><span class="attr-type">' + a.type;
                // Show key format for PK with generated prefix
                if (a.is_key && keyInfo && keyInfo.generated && keyInfo.prefix) {
                    html += ' <span style="color:#34C759;font-size:10px;">= "' + keyInfo.prefix + '_{uuid6}"</span>';
                }
                // Show reference target for FK
                if (refMap[a.name]) {
                    let targetKeyInfo = null;
                    try {
                        if (migrationData && migrationData.key_registry && migrationData.key_registry[refMap[a.name]]) {
                            targetKeyInfo = migrationData.key_registry[refMap[a.name]];
                        }
                    } catch(e) { targetKeyInfo = null; }
                    if (targetKeyInfo && targetKeyInfo.prefix) {
                        html += ' <span style="color:#007AFF;font-size:10px;">→ ' + refMap[a.name] + ' ("' + targetKeyInfo.prefix + '_...")</span>';
                    } else {
                        html += ' <span style="color:#007AFF;font-size:10px;">→ ' + refMap[a.name] + '</span>';
                    }
                }
                html += '</span>';
                if (a.is_key) html += keyBadge(a, isSource ? migrationData.source_type : migrationData.target_type);
                if (a.is_optional) html += '<span class="attr-badge optional">?</span>';
                html += '</div>';
            });

            (entity.embedded || []).forEach(e => { html += '<div class="embedded-item">&lt;&gt; ' + e.name + ' [' + e.target_end_cardinality + ']</div>'; });

            if (!isSource) {
                (entity.references || []).forEach(r => { html += '<div class="reference-item">' + r.name + ' &rarr; ' + r.target + '</div>'; });
            }
            (entity.edges || []).forEach(e => { html += '<div class="edge-item">&#x2194; ' + e.name + ' &rarr; ' + e.target + ' [' + e.target_end_cardinality + ']</div>'; });
            html += '</div></div>';
            return html;
        }

        function renderNestedEntityCard(entity) {
            // Render entity card with nested structure support (for original source)
            let html = '<div class="entity-card"><div class="entity-name">' + entity.name;
            if (entity.type) html += ' <span class="entity-type-badge">' + entity.type + '</span>';
            html += '</div><div class="entity-body">';

            function renderProperties(attrs, indent) {
                let result = '';
                attrs.forEach(a => {
                    const levelClass = indent > 0 ? ' nested-level-' + Math.min(indent, 3) : '';
                    if (a.nested) {
                        // Nested object or array with nested content
                        const typeLabel = a.type === 'array' ? 'array' : '{object}';
                        result += '<div class="property nested-object' + levelClass + '">';
                        result += '<span class="attr-name">' + a.name + '</span>';
                        result += '<span class="attr-type">' + typeLabel + '</span></div>';
                        // Recursively render nested properties with increased indent
                        result += renderProperties(a.nested, indent + 1);
                    } else {
                        // Regular property
                        result += '<div class="property' + levelClass + '">';
                        result += '<span class="attr-name">' + a.name + '</span>';
                        result += '<span class="attr-type">' + a.type + '</span>';
                        if (a.is_key) result += keyBadge(a, migrationData.source_type);
                        if (a.is_fk) result += '<span class="attr-badge fk">FK</span>';
                        result += '</div>';
                    }
                });
                return result;
            }

            if (entity.properties) {
                html += renderProperties(entity.properties, 0);
            }

            // Fallback for non-nested structure
            if (entity.embedded) {
                entity.embedded.forEach(e => { html += '<div class="embedded-item">&lt;&gt; ' + e.name + ' [' + e.target_end_cardinality + ']</div>'; });
            }
            if (entity.references) {
                entity.references.forEach(r => { html += '<div class="reference-item">' + r.name + ' &rarr; ' + r.target + '</div>'; });
            }
            if (entity.edges) {
                entity.edges.forEach(e => { html += '<div class="edge-item">&#x2194; ' + e.name + ' &rarr; ' + e.target + ' [' + e.target_end_cardinality + ']</div>'; });
            }

            html += '</div></div>';
            return html;
        }
        // ═══════════════════════════════════════════════════════
        // Source Schemas Tab - auto-loaded on page open
        // ═══════════════════════════════════════════════════════
        async function loadSourceSchemas() {
            const container = document.getElementById('tab-schemas');
            container.innerHTML = '<div class="loading show"><div class="spinner"></div><p>Loading schemas...</p></div>';
            try {
                const resp = await fetch('/api/schemas?t=' + Date.now());
                const data = await resp.json();
                renderSourceSchemas(data);
            } catch (e) {
                container.innerHTML = '<div class="welcome"><h2>Failed to load schemas</h2><p>' + e.message + '</p></div>';
            }
        }

        function renderSourceSchemas(data) {
            const container = document.getElementById('tab-schemas');
            const parsed = (data && data.parsed) || {};
            // Counts derived from the parsed Meta V1 structures the server
            // attaches to /api/schemas. The subtitle text never disagrees
            // with the actual schema files because nothing in this page is
            // a hardcoded constant any more.
            const pgStats   = computeSchemaStats(parsed.postgresql, 'relational');
            const mongoStats = computeSchemaStats(parsed.mongodb,   'document');
            const neoStats  = computeSchemaStats(parsed.neo4j,      'graph');
            const cassStats = computeSchemaStats(parsed.cassandra,  'columnar');
            let html = '<div class="source-schemas-page">';

            // ── Section 1: PostgreSQL ──
            html += '<div class="schema-section">';
            html += '<div class="schema-section-header"><h2>PostgreSQL</h2><span class="schema-badge relational">Relational</span></div>';
            html += '<div class="schema-section-subtitle">'
                  + pgStats.entities + ' Tables, '
                  + pgStats.foreign_keys + ' Foreign Keys, '
                  + pgStats.fields + ' Fields — Normalized 3NF Design</div>';
            html += '<div class="vis-and-code">';
            html += '<div class="vis-block"><div class="section-title">ER Diagram</div>';
            html += '<div class="er-diagram">' + getStaticERDiagram() + '</div></div>';
            html += '<div class="code-block-wrapper"><div class="section-title">DDL (SQL)</div>';
            html += '<div class="sql-code-view"><pre>' + escapeHtml(data.postgresql) + '</pre></div></div>';
            html += '</div></div>';

            // ── Section 2: MongoDB ──
            html += '<div class="schema-section">';
            html += '<div class="schema-section-header"><h2>MongoDB</h2><span class="schema-badge document">Document</span></div>';
            html += '<div class="schema-section-subtitle">'
                  + mongoStats.roots + ' Root Collection' + (mongoStats.roots === 1 ? '' : 's')
                  + ' (' + mongoStats.root_names.join(' + ') + '), '
                  + mongoStats.max_depth + '-Level Max Nesting — Cross-collection ObjectId reference</div>';
            html += '<div class="vis-and-code">';
            html += '<div class="vis-block"><div class="section-title">Document Structure</div>';
            html += '<div class="document-tree">' + renderMongoDocTree(parsed.mongodb) + '</div></div>';
            html += '<div class="code-block-wrapper"><div class="section-title">JSON Schema</div>';
            html += '<div class="sql-code-view"><pre>' + syntaxHighlightJSON(data.mongodb) + '</pre></div></div>';
            html += '</div></div>';

            // ── Section 3: Neo4j ──
            html += '<div class="schema-section">';
            html += '<div class="schema-section-header"><h2>Neo4j</h2><span class="schema-badge graph">Graph</span></div>';
            html += '<div class="schema-section-subtitle">'
                  + neoStats.nodes + ' Nodes, '
                  + neoStats.relationships + ' Relationships, '
                  + neoStats.fields + ' Properties — Property Graph Model</div>';
            html += '<div class="vis-and-code">';
            html += '<div class="vis-block"><div class="section-title">Graph Diagram</div>';
            // Carry per-node labels from the parsed Meta V1 so the click card
            // can list a node's extra Neo4j labels (origin 'source' matches the
            // static diagram's onclick handlers).
            _dynNodeLabels['source'] = {};
            Object.keys(parsed.neo4j || {})
                .filter(k => !k.startsWith('__'))
                .forEach(k => { _dynNodeLabels['source'][k] = (parsed.neo4j[k] || {}).labels || []; });
            html += '<div class="er-diagram">' + getStaticGraphDiagram(neoStats) + '</div></div>';
            html += '<div class="code-block-wrapper"><div class="section-title">GraphQL SDL Schema</div>';
            html += '<div class="sql-code-view"><pre>' + escapeHtml(data.neo4j) + '</pre></div></div>';
            html += '</div></div>';

            // ── Section 4: Cassandra ──
            html += '<div class="schema-section">';
            html += '<div class="schema-section-header"><h2>Cassandra</h2><span class="schema-badge columnar">Columnar</span></div>';
            html += '<div class="schema-section-subtitle">'
                  + cassStats.entities + ' Tables, Query-Driven Design, '
                  + cassStats.fields + ' Fields — Denormalized Wide-Column</div>';
            html += '<div class="vis-and-code">';
            html += '<div class="vis-block"><div class="section-title">Chebotko Diagram</div>';
            html += getStaticChebotkoDiagram();
            html += '</div>';
            html += '<div class="code-block-wrapper"><div class="section-title">CQL</div>';
            html += '<div class="sql-code-view"><pre>' + escapeHtml(data.cassandra) + '</pre></div></div>';
            html += '</div></div>';

            html += '</div>';
            container.innerHTML = html;

            setTimeout(() => flushDotRenders(), 50);
        }

        // Counts every Source-Schemas subtitle needs. Walks the parsed
        // Meta V1 dict that /api/schemas attaches per paradigm. Returns 0s
        // when the parse failed (so the page still renders without crashing
        // — counts of 0 are visibly wrong and call out the parse error).
        function computeSchemaStats(parsed, paradigm) {
            const z = { entities: 0, fields: 0, foreign_keys: 0,
                        nodes: 0, relationships: 0,
                        roots: 0, root_names: [], max_depth: 0 };
            if (!parsed || parsed.__error) return z;
            const names = Object.keys(parsed).filter(k => !k.startsWith('__'));
            z.entities = names.length;
            z.fields = names.reduce((n, k) => n + (parsed[k].properties || []).length, 0);

            if (paradigm === 'relational' || paradigm === 'columnar') {
                z.foreign_keys = names.reduce((n, k) =>
                    n + (parsed[k].constraints || []).filter(c => c.type === 'FOREIGN_KEY').length, 0);
            }
            if (paradigm === 'graph') {
                z.nodes = names.filter(k => parsed[k].entity_kind === 'vertex').length;
                // Edges are stored on each vertex's outgoing 'edges' list.
                z.relationships = names.reduce((n, k) =>
                    n + (parsed[k].edges || []).length, 0);
            }
            if (paradigm === 'document') {
                // A root collection is any entity that is not the embedding
                // target of another entity. Same algorithm as the Layer 1
                // _normalize_to_paths normalizer in validation/meta.py.
                const embTargets = new Set();
                names.forEach(k =>
                    (parsed[k].embedded || []).forEach(e => embTargets.add(e.target || '')));
                const roots = names.filter(k => !embTargets.has(k));
                z.roots = roots.length;
                z.root_names = roots.slice().sort();
                // Nesting depth: root = 0, "orders.shipper" = 1,
                // "orders.details.product.category" = 3. This matches the
                // ``Level N`` annotations the dynamic tree walker emits and
                // the historical "N-Level Max Nesting" copy.
                z.max_depth = names.reduce((m, k) => Math.max(m, k.split('.').length - 1), 0);
            }
            return z;
        }

        // ── Static ER Diagram (PostgreSQL Northwind) ──
        // The DOT graph below is hand-laid for visual rank-grouping
        // (orders centred, lookups around it). schema-section-subtitle
        // counts are now derived from the parsed schema in
        // computeSchemaStats(), so the surface drift risk is only in the
        // entity-box LIST itself: adding/removing a table in the .sql
        // file would not be reflected without editing this DOT string.
        function getStaticERDiagram() {
            const containerId = 'er-dot-' + (erDiagramCounter++);
            const dot = `digraph ER {
  rankdir=LR;
  graph [fontname="Helvetica Neue, Helvetica, Arial", nodesep=0.8, ranksep=1.2, bgcolor="transparent"];
  node [shape=plain, fontname="Helvetica Neue, Helvetica, Arial", fontsize=11];
  edge [fontname="Helvetica Neue, Helvetica, Arial", fontsize=9, color="#8E8E93", penwidth=1.2];

  { rank=same; "orders"; }
  { rank=same; "customers"; "employees"; "shippers"; "order_details"; }
  { rank=same; "products"; }
  { rank=same; "categories"; "suppliers"; }

  "orders" [label=<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="#007AFF" BGCOLOR="white">
      <TR><TD COLSPAN="3" BGCOLOR="#007AFF" ALIGN="CENTER"><FONT COLOR="white"><B>orders</B></FONT></TD></TR>
      <TR><TD ALIGN="LEFT">order_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#007AFF"> PK</FONT></TD></TR>
      <TR><TD ALIGN="LEFT">order_date</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">date</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">required_date</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">date</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">shipped_date</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">date</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">freight</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">double</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">ship_name</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">ship_address</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">ship_city</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">ship_region</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">ship_postal_code</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">ship_country</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">customer_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#FF3B30"> FK</FONT></TD></TR>
      <TR><TD ALIGN="LEFT">employee_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#FF3B30"> FK</FONT></TD></TR>
      <TR><TD ALIGN="LEFT">shipper_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#FF3B30"> FK</FONT></TD></TR>
    </TABLE>
  >];

  "customers" [label=<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="#D2D2D7" BGCOLOR="white">
      <TR><TD COLSPAN="3" BGCOLOR="#3A3A3C" ALIGN="CENTER"><FONT COLOR="white"><B>customers</B></FONT></TD></TR>
      <TR><TD ALIGN="LEFT">customer_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#007AFF"> PK</FONT></TD></TR>
      <TR><TD ALIGN="LEFT">company_name</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">contact_name</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">contact_title</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">phone</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">fax</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">street</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">city</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">region</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">postal_code</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">country</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
    </TABLE>
  >];

  "employees" [label=<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="#D2D2D7" BGCOLOR="white">
      <TR><TD COLSPAN="3" BGCOLOR="#3A3A3C" ALIGN="CENTER"><FONT COLOR="white"><B>employees</B></FONT></TD></TR>
      <TR><TD ALIGN="LEFT">employee_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#007AFF"> PK</FONT></TD></TR>
      <TR><TD ALIGN="LEFT">last_name</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">first_name</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">title</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">birth_date</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">date</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">hire_date</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">date</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">phone</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">notes</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">street</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">city</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">region</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">postal_code</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">country</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">reports_to</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#FF3B30"> FK</FONT></TD></TR>
    </TABLE>
  >];

  "shippers" [label=<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="#D2D2D7" BGCOLOR="white">
      <TR><TD COLSPAN="3" BGCOLOR="#3A3A3C" ALIGN="CENTER"><FONT COLOR="white"><B>shippers</B></FONT></TD></TR>
      <TR><TD ALIGN="LEFT">shipper_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#007AFF"> PK</FONT></TD></TR>
      <TR><TD ALIGN="LEFT">company_name</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">phone</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
    </TABLE>
  >];

  "order_details" [label=<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="#D2D2D7" BGCOLOR="white">
      <TR><TD COLSPAN="3" BGCOLOR="#3A3A3C" ALIGN="CENTER"><FONT COLOR="white"><B>order_details</B></FONT></TD></TR>
      <TR><TD ALIGN="LEFT">order_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#FF9500"> PK,FK</FONT></TD></TR>
      <TR><TD ALIGN="LEFT">product_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#FF9500"> PK,FK</FONT></TD></TR>
      <TR><TD ALIGN="LEFT">unit_price</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">double</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">quantity</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">integer</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">discount</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">double</FONT></TD><TD></TD></TR>
    </TABLE>
  >];

  "products" [label=<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="#D2D2D7" BGCOLOR="white">
      <TR><TD COLSPAN="3" BGCOLOR="#3A3A3C" ALIGN="CENTER"><FONT COLOR="white"><B>products</B></FONT></TD></TR>
      <TR><TD ALIGN="LEFT">product_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#007AFF"> PK</FONT></TD></TR>
      <TR><TD ALIGN="LEFT">product_name</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">unit_price</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">double</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">units_in_stock</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">integer</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">discontinued</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">boolean</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">quantity_per_unit</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">supplier_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#FF3B30"> FK</FONT></TD></TR>
      <TR><TD ALIGN="LEFT">category_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#FF3B30"> FK</FONT></TD></TR>
    </TABLE>
  >];

  "categories" [label=<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="#D2D2D7" BGCOLOR="white">
      <TR><TD COLSPAN="3" BGCOLOR="#3A3A3C" ALIGN="CENTER"><FONT COLOR="white"><B>categories</B></FONT></TD></TR>
      <TR><TD ALIGN="LEFT">category_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#007AFF"> PK</FONT></TD></TR>
      <TR><TD ALIGN="LEFT">category_name</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">description</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
    </TABLE>
  >];

  "suppliers" [label=<
    <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="#D2D2D7" BGCOLOR="white">
      <TR><TD COLSPAN="3" BGCOLOR="#3A3A3C" ALIGN="CENTER"><FONT COLOR="white"><B>suppliers</B></FONT></TD></TR>
      <TR><TD ALIGN="LEFT">supplier_id</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD ALIGN="RIGHT"><FONT COLOR="#007AFF"> PK</FONT></TD></TR>
      <TR><TD ALIGN="LEFT">company_name</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">contact_name</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">contact_title</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">phone</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">fax</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">street</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">city</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">region</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">postal_code</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
      <TR><TD ALIGN="LEFT">country</TD><TD ALIGN="LEFT"><FONT COLOR="#8E8E93">string</FONT></TD><TD></TD></TR>
    </TABLE>
  >];

  "customers" -> "orders" [arrowhead=vee, arrowsize=0.8, headlabel="1..N", taillabel="1", labeldistance=2.2, label="  customer_id  ", fontcolor="#8E8E93"];
  "employees" -> "orders" [arrowhead=vee, arrowsize=0.8, headlabel="1..N", taillabel="1", labeldistance=2.2, label="  employee_id  ", fontcolor="#8E8E93"];
  "shippers" -> "orders" [arrowhead=vee, arrowsize=0.8, headlabel="1..N", taillabel="1", labeldistance=2.2, label="  shipper_id  ", fontcolor="#8E8E93"];
  "employees" -> "employees" [arrowhead=vee, arrowsize=0.8, headlabel="0..N", taillabel="0..1", labeldistance=2.2, labelangle=40, label="  reports_to  ", fontcolor="#8E8E93"];
  "orders" -> "order_details" [arrowhead=vee, arrowsize=0.8, headlabel="1..N", taillabel="1", labeldistance=2.2, label="  order_id  ", fontcolor="#8E8E93"];
  "products" -> "order_details" [arrowhead=vee, arrowsize=0.8, headlabel="1..N", taillabel="1", labeldistance=2.2, label="  product_id  ", fontcolor="#8E8E93"];
  "categories" -> "products" [arrowhead=vee, arrowsize=0.8, headlabel="1..N", taillabel="1", labeldistance=2.2, label="  category_id  ", fontcolor="#8E8E93"];
  "suppliers" -> "products" [arrowhead=vee, arrowsize=0.8, headlabel="1..N", taillabel="1", labeldistance=2.2, label="  supplier_id  ", fontcolor="#8E8E93"];
}`;
            pendingDotRenders.push({ id: containerId, dot: dot });
            return '<div class="er-dot-container" id="' + containerId + '"><div style="color:#8E8E93;font-size:13px;">Loading ER diagram...</div></div>';
        }

        // ── Static Graph Diagram (Neo4j Northwind) ──
        // Neo4j property data (from northwind_neo4j.graphql)
        const _neo4jNodeProps = {
            orders: [
                {n:'order_id',t:'string',k:true},{n:'order_date',t:'date'},{n:'required_date',t:'date'},
                {n:'shipped_date',t:'date'},{n:'freight',t:'double'},{n:'ship_name',t:'string'},
                {n:'ship_address',t:'string'},{n:'ship_city',t:'string'},{n:'ship_region',t:'string'},
                {n:'ship_postal_code',t:'string'},{n:'ship_country',t:'string'}
            ],
            products: [
                {n:'product_id',t:'string',k:true},{n:'product_name',t:'string'},{n:'unit_price',t:'double'},
                {n:'units_in_stock',t:'integer'},{n:'discontinued',t:'string'},{n:'quantity_per_unit',t:'string'}
            ],
            customers: [
                {n:'customer_id',t:'string',k:true},{n:'company_name',t:'string'},{n:'contact_name',t:'string'},
                {n:'contact_title',t:'string'},{n:'phone',t:'string'},{n:'fax',t:'string'},
                {n:'street',t:'string'},{n:'city',t:'string'},{n:'region',t:'string'},
                {n:'postal_code',t:'string'},{n:'country',t:'string'}
            ],
            employees: [
                {n:'employee_id',t:'string',k:true},{n:'last_name',t:'string'},{n:'first_name',t:'string'},
                {n:'title',t:'string'},{n:'birth_date',t:'date'},{n:'hire_date',t:'date'},
                {n:'phone',t:'string'},{n:'notes',t:'string'},{n:'street',t:'string'},
                {n:'city',t:'string'},{n:'region',t:'string'},{n:'postal_code',t:'string'},{n:'country',t:'string'}
            ],
            shippers: [
                {n:'shipper_id',t:'string',k:true},{n:'company_name',t:'string'},{n:'phone',t:'string'}
            ],
            categories: [
                {n:'category_id',t:'string',k:true},{n:'category_name',t:'string'},{n:'description',t:'string'}
            ],
            suppliers: [
                {n:'supplier_id',t:'string',k:true},{n:'company_name',t:'string'},{n:'contact_name',t:'string'},
                {n:'contact_title',t:'string'},{n:'phone',t:'string'},{n:'fax',t:'string'},
                {n:'street',t:'string'},{n:'city',t:'string'},{n:'region',t:'string'},
                {n:'postal_code',t:'string'},{n:'country',t:'string'}
            ]
        };
        const _neo4jEdgeProps = {
            CONTAINS: {from:'orders',to:'products',props:[{n:'unit_price',t:'double'},{n:'quantity',t:'integer'},{n:'discount',t:'double'}]},
            PURCHASED: {from:'customers',to:'orders',props:[]},
            SOLD: {from:'employees',to:'orders',props:[]},
            SHIPPED_VIA: {from:'orders',to:'shippers',props:[]},
            SUPPLIES: {from:'suppliers',to:'products',props:[]},
            PART_OF: {from:'products',to:'categories',props:[]},
            REPORTS_TO: {from:'employees',to:'employees',props:[]}
        };

        // Toggle property card on click
        let _activeGraphCard = null;
        function toggleGraphCard(evt, type, name, origin) {
            evt.stopPropagation();
            const wrap = evt.target.closest('.neo4j-graph-wrap');
            if (!wrap) return;
            // Close existing card
            if (_activeGraphCard) {
                _activeGraphCard.remove();
                if (_activeGraphCard._cardName === name && _activeGraphCard._cardType === type) {
                    _activeGraphCard = null;
                    return;
                }
                _activeGraphCard = null;
            }
            // Build card HTML - use origin to determine source vs target
            let html = '';
            if (type === 'node') {
                const dynProps = (_dynNodeProps[origin] || {})[name];
                const props = dynProps || _neo4jNodeProps[name] || [];
                const count = props.length;
                const pkLbl = getPkLabel(origin === 'source' ? migrationData.source_type : migrationData.target_type);
                const labels = (_dynNodeLabels[origin] || {})[name] || [];
                html = '<div class="card-title" style="color:#3B82F6;">:' + name + '</div>';
                if (labels.length) {
                    html += '<div class="card-labels" style="font-size:11px;color:#8B5CF6;margin-top:2px;">'
                        + 'Labels: ' + labels.map(l => ':' + escapeHtml(l)).join(' ') + '</div>';
                }
                html += '<div class="card-subtitle">' + count + ' properties</div>';
                props.forEach(p => {
                    html += '<div class="prop-row"><span class="prop-name">' + p.n
                        + (p.k ? '<span class="prop-key">' + pkLbl + '</span>' : '')
                        + '</span><span class="prop-type">' + p.t + '</span></div>';
                });
            } else {
                const info = (_dynEdgeProps[origin] || {})[name] || _neo4jEdgeProps[name] || {};
                html = '<div class="card-title" style="color:#E11D48;">:' + name + '</div>';
                if (info) {
                    html += '<div class="card-subtitle">' + info.from + ' &rarr; ' + info.to + '</div>';
                    if (info.props.length > 0) {
                        info.props.forEach(p => {
                            html += '<div class="prop-row"><span class="prop-name">' + p.n
                                + '</span><span class="prop-type">' + p.t + '</span></div>';
                        });
                    } else {
                        html += '<div style="color:#9CA3AF;font-size:11px;margin-top:2px;">No properties</div>';
                    }
                }
            }
            // Position card near click
            const rect = wrap.getBoundingClientRect();
            const x = evt.clientX - rect.left + 12;
            const y = evt.clientY - rect.top - 10;
            const card = document.createElement('div');
            card.className = 'neo4j-prop-card';
            card.innerHTML = html;
            card.style.left = x + 'px';
            card.style.top = y + 'px';
            card._cardName = name;
            card._cardType = type;
            wrap.appendChild(card);
            _activeGraphCard = card;
            // Adjust if overflows right edge
            setTimeout(() => {
                const cr = card.getBoundingClientRect();
                const wr = wrap.getBoundingClientRect();
                if (cr.right > wr.right - 8) {
                    card.style.left = (x - cr.width - 24) + 'px';
                }
                if (cr.bottom > wr.bottom - 8) {
                    card.style.top = (y - cr.height) + 'px';
                }
            }, 0);
        }
        // Close card on click outside
        document.addEventListener('click', function(e) {
            if (_activeGraphCard && !e.target.closest('.neo4j-prop-card')) {
                _activeGraphCard.remove();
                _activeGraphCard = null;
            }
        });

        // ── Static Graph Diagram (Neo4j Northwind) ──
        // The graph layout below is hand-laid for visual clarity (orders +
        // products as twin "hub" nodes with satellites around them); the
        // schema-section-subtitle is generated dynamically from the parsed
        // Meta V1, so the only drift risk left is when the graph schema file
        // gains/loses an entity that the static layout would not visualise.
        // Pass the parsed counts in via ``stats`` so the legend annotation
        // at the bottom of the SVG mirrors reality.
        function getStaticGraphDiagram(stats) {
            const W = 960, H = 700;
            const nodes = [
                { name: 'orders', x: W*0.28, y: H*0.45, hub: true, theme: 0 },
                { name: 'products', x: W*0.72, y: H*0.30, hub: true, theme: 1 },
                { name: 'customers', x: W*0.08, y: H*0.20, hub: false, theme: 0 },
                { name: 'employees', x: W*0.08, y: H*0.70, hub: false, theme: 0 },
                { name: 'shippers', x: W*0.42, y: H*0.78, hub: false, theme: 0 },
                { name: 'categories', x: W*0.92, y: H*0.12, hub: false, theme: 1 },
                { name: 'suppliers', x: W*0.92, y: H*0.52, hub: false, theme: 1 },
            ];
            const edges = [
                { from: 'customers', to: 'orders', label: 'PURCHASED' },
                { from: 'employees', to: 'orders', label: 'SOLD' },
                { from: 'orders', to: 'shippers', label: 'SHIPPED_VIA' },
                { from: 'orders', to: 'products', label: 'CONTAINS' },
                { from: 'suppliers', to: 'products', label: 'SUPPLIES' },
                { from: 'products', to: 'categories', label: 'PART_OF' },
                { from: 'employees', to: 'employees', label: 'REPORTS_TO' },
            ];
            const hubR = 30, satR = 22;
            const themes = [
                { fill:'#DBEAFE', stroke:'#3B82F6', text:'#1E40AF', satFill:'#EFF6FF', satStroke:'#93C5FD', satText:'#1E3A5F' },
                { fill:'#FEF3C7', stroke:'#F59E0B', text:'#92400E', satFill:'#FFFBEB', satStroke:'#FCD34D', satText:'#78350F' }
            ];
            const posMap = {};
            nodes.forEach(n => { posMap[n.name] = n; });

            let svg = '<div class="neo4j-graph-wrap"><div class="graph-svg-container"><svg viewBox="0 0 '+W+' '+H+'" style="width:100%;max-width:960px;height:auto;font-family:-apple-system,BlinkMacSystemFont,sans-serif;">';
            svg += '<defs><marker id="ahSS" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#94A3B8"/></marker>';
            svg += '<marker id="ahSelf" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="#E11D48"/></marker></defs>';

            // Draw edges
            edges.forEach(e => {
                const s = posMap[e.from], t = posMap[e.to];
                if (e.from === e.to) {
                    const loopR = 28;
                    svg += '<path d="M '+(s.x-8)+' '+(s.y-satR)+' C '+(s.x-loopR*1.2)+' '+(s.y-satR-loopR*1.5)+', '+(s.x+loopR*1.2)+' '+(s.y-satR-loopR*1.5)+', '+(s.x+8)+' '+(s.y-satR)+'" fill="none" stroke="#E11D48" stroke-width="1.3" opacity="0.8" marker-end="url(#ahSelf)"/>';
                    svg += '<text x="'+s.x+'" y="'+(s.y-satR-loopR*0.8)+'" text-anchor="middle" font-size="8" fill="#E11D48" font-weight="500" style="cursor:pointer" onclick="toggleGraphCard(event,&apos;edge&apos;,&apos;'+e.label+'&apos;,&apos;source&apos;)">'+e.label+'</text>';
                } else {
                    const dx = t.x-s.x, dy = t.y-s.y;
                    const dist = Math.sqrt(dx*dx+dy*dy);
                    const nx = dx/dist, ny = dy/dist;
                    const sR = s.hub ? hubR : satR;
                    const tR = t.hub ? hubR : satR;
                    const x1 = s.x+nx*(sR+2), y1 = s.y+ny*(sR+2);
                    const x2 = t.x-nx*(tR+10), y2 = t.y-ny*(tR+10);
                    const mx = (x1+x2)/2, my = (y1+y2)/2;
                    svg += '<line x1="'+x1+'" y1="'+y1+'" x2="'+x2+'" y2="'+y2+'" stroke="#94A3B8" stroke-width="1.1" opacity="0.65" marker-end="url(#ahSS)"/>';
                    svg += '<text x="'+mx+'" y="'+(my-4)+'" text-anchor="middle" font-size="8" fill="#475569" opacity="0.85" style="cursor:pointer" onclick="toggleGraphCard(event,&apos;edge&apos;,&apos;'+e.label+'&apos;,&apos;source&apos;)">'+e.label+'</text>';
                }
            });

            // Draw nodes (clickable)
            nodes.forEach(n => {
                const th = themes[n.theme];
                const clk = ' style="cursor:pointer" onclick="toggleGraphCard(event,&apos;node&apos;,&apos;'+n.name+'&apos;,&apos;source&apos;)"';
                if (n.hub) {
                    svg += '<circle cx="'+n.x+'" cy="'+n.y+'" r="'+hubR+'" fill="'+th.fill+'" stroke="'+th.stroke+'" stroke-width="2.5"'+clk+'/>';
                    const fs = n.name.length > 7 ? 10 : 11;
                    svg += '<text x="'+n.x+'" y="'+(n.y+4)+'" text-anchor="middle" font-size="'+fs+'" font-weight="700" fill="'+th.text+'"'+clk+'>'+n.name+'</text>';
                } else {
                    svg += '<circle cx="'+n.x+'" cy="'+n.y+'" r="'+satR+'" fill="'+th.satFill+'" stroke="'+th.satStroke+'" stroke-width="1.5"'+clk+'/>';
                    const fs = n.name.length > 8 ? 8.5 : 9.5;
                    svg += '<text x="'+n.x+'" y="'+(n.y+3)+'" text-anchor="middle" font-size="'+fs+'" font-weight="600" fill="'+th.satText+'"'+clk+'>'+n.name+'</text>';
                }
            });

            const annN = (stats && stats.nodes != null) ? stats.nodes : nodes.length;
            const annR = (stats && stats.relationships != null) ? stats.relationships : edges.length;
            svg += '<text x="'+(W/2)+'" y="'+(H-12)+'" text-anchor="middle" font-size="11" fill="#94A3B8" font-weight="500">'
                 + annN + ' Nodes, ' + annR + ' Relationships — Click node or relationship to view properties</text>';
            svg += '</svg></div></div>';
            return svg;
        }

        // ── MongoDB Document Tree ──
        // Renders the parsed Mongo schema as an ASCII tree. Walks the
        // ``parsed`` Meta V1 dict the server attaches to /api/schemas, so
        // adding or restructuring collections in tests/northwind_mongodb.json
        // is reflected here automatically — no hand-edit required. The
        // legacy hardcoded version below is kept as a fallback (used only
        // when the server can't supply ``parsed`` data).
        function renderMongoDocTree(parsedMongo) {
            if (parsedMongo && !parsedMongo.__error) {
                return renderMongoTreeFromParsed(parsedMongo);
            }
            return renderMongoTreeFallback();
        }

        // Walk the parsed Meta V1 dict and emit the same |-- / +-- ASCII tree
        // shape the legacy hand-built version produced. Pure function over
        // the parsed dict; if the schema changes shape the rendering
        // changes automatically.
        function renderMongoTreeFromParsed(parsed) {
            const names = Object.keys(parsed).filter(k => !k.startsWith('__'));
            const embTargets = new Set();
            names.forEach(k => (parsed[k].embedded || [])
                              .forEach(e => embTargets.add(e.target || '')));
            const roots = names.filter(k => !embTargets.has(k)).sort();
            return roots.map((root, i) =>
                walkEntity(parsed, root, true, '', i + 1, roots.length)
            ).join('\n\n');
        }

        function walkEntity(parsed, fullPath, isRoot, prefix, rootIdx, rootTotal) {
            const entity = parsed[fullPath];
            if (!entity) return '';
            const leafName = entity.name || fullPath.split('.').pop();
            const lines = [];
            if (isRoot) {
                lines.push('<span class="dt-key">' + escapeHtml(leafName) + '</span>'
                         + ' <span class="dt-comment">(root collection #' + rootIdx
                         + (rootTotal > 1 ? ' of ' + rootTotal : '') + ')</span>');
            }
            const props = (entity.properties || []).map(p => ({kind:'prop', data:p}));
            const embeds = (entity.embedded || []).map(e => ({kind:'emb', data:e}));
            const items = props.concat(embeds);
            items.forEach((item, idx) => {
                const isLast = idx === items.length - 1;
                const branch = isLast ? '+--' : '|--';
                const childPrefix = prefix + (isLast ? '    ' : '|   ');
                if (item.kind === 'prop') {
                    const p = item.data;
                    const keyTag = p.is_key
                        ? ' <span class="dt-comment">(' + (leafName === 'orders' ? 'order_id' : leafName === 'customers' ? 'customer_id' : 'key') + ', primary key)</span>'
                        : '';
                    lines.push('<span class="dt-key">' + prefix + branch + ' ' + escapeHtml(p.name) + '</span>'
                             + ': <span class="dt-type">' + escapeHtml(p.type || '?') + '</span>' + keyTag);
                } else {
                    const e = item.data;
                    const card = e.target_end_cardinality || '1..1';
                    const isArray = card.endsWith('..n') || card.endsWith('..*') || card.endsWith('..m');
                    const tag = isArray ? '<span class="dt-arr">[array]</span>'
                                        : '<span class="dt-obj">{object}</span>';
                    const childPath = e.target || (fullPath + '.' + e.name);
                    const depth = childPath.split('.').length - 1;
                    lines.push('<span class="dt-key">' + prefix + branch + ' ' + escapeHtml(e.name) + '</span>'
                             + ': ' + tag + ' <span class="dt-comment">Level ' + depth + '</span>');
                    const childTree = walkEntity(parsed, childPath, false, childPrefix, 0, 0);
                    if (childTree) lines.push(childTree);
                }
            });
            return lines.join('\n');
        }

        // Fallback (used only when /api/schemas couldn't provide parsed data).
        function renderMongoTreeFallback() {
            const ordersTree =
                  '<span class="dt-key">orders</span> <span class="dt-comment">(root collection #1)</span>\n'
                + '<span class="dt-key">|-- _id</span>: <span class="dt-type">string</span> <span class="dt-comment">(order_id, primary key)</span>\n'
                + '<span class="dt-key">|-- order_date</span>: <span class="dt-type">date</span>\n'
                + '<span class="dt-key">|-- required_date</span>: <span class="dt-type">date</span>\n'
                + '<span class="dt-key">|-- shipped_date</span>: <span class="dt-type">date</span>\n'
                + '<span class="dt-key">|-- freight</span>: <span class="dt-type">double</span>\n'
                + '<span class="dt-key">|-- ship_name</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|-- customer_id</span>: <span class="dt-type">string</span> <span class="dt-comment">(cross-collection ref &rarr; customers._id)</span>\n'
                + '<span class="dt-key">|-- ship_destination</span>: <span class="dt-obj">{object}</span> <span class="dt-comment">Level 1</span>\n'
                + '<span class="dt-key">|   |-- ship_address</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|   |-- ship_city</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|   |-- ship_region</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|   |-- ship_postal_code</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|   +-- ship_country</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|</span>\n'
                + '<span class="dt-key">|-- employee</span>: <span class="dt-obj">{object}</span> <span class="dt-comment">Level 1, required</span>\n'
                + '<span class="dt-key">|   |-- last_name</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|   |-- first_name</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|   |-- title</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|   |-- birth_date</span>: <span class="dt-type">date</span>\n'
                + '<span class="dt-key">|   |-- hire_date</span>: <span class="dt-type">date</span>\n'
                + '<span class="dt-key">|   |-- phone</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|   |-- notes</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|   |-- reports_to</span>: <span class="dt-type">string</span> <span class="dt-comment">(self-ref)</span>\n'
                + '<span class="dt-key">|   +-- address</span>: <span class="dt-obj">{object}</span> <span class="dt-comment">Level 2</span>\n'
                + '<span class="dt-key">|       |-- street</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|       |-- city</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|       |-- region</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|       |-- postal_code</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|       +-- country</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|</span>\n'
                + '<span class="dt-key">|-- shipper</span>: <span class="dt-obj">{object}</span> <span class="dt-comment">Level 1, required</span>\n'
                + '<span class="dt-key">|   |-- company_name</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|   +-- phone</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|</span>\n'
                + '<span class="dt-key">+-- details</span>: <span class="dt-arr">[array]</span> <span class="dt-comment">Level 1, order line items</span>\n'
                + '<span class="dt-key">    +-- [each item]</span>:\n'
                + '<span class="dt-key">        |-- unit_price</span>: <span class="dt-type">double</span>\n'
                + '<span class="dt-key">        |-- quantity</span>: <span class="dt-type">int</span>\n'
                + '<span class="dt-key">        |-- discount</span>: <span class="dt-type">double</span>\n'
                + '<span class="dt-key">        +-- product</span>: <span class="dt-obj">{object}</span> <span class="dt-comment">Level 2, required</span>\n'
                + '<span class="dt-key">            |-- product_name</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">            |-- unit_price</span>: <span class="dt-type">double</span>\n'
                + '<span class="dt-key">            |-- units_in_stock</span>: <span class="dt-type">int</span>\n'
                + '<span class="dt-key">            |-- discontinued</span>: <span class="dt-type">bool</span>\n'
                + '<span class="dt-key">            |-- quantity_per_unit</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">            |-- category</span>: <span class="dt-obj">{object}</span> <span class="dt-comment">Level 3 (leaf)</span>\n'
                + '<span class="dt-key">            |   |-- category_name</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">            |   +-- description</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">            +-- supplier</span>: <span class="dt-obj">{object}</span> <span class="dt-comment">Level 3 (leaf, flat address)</span>\n'
                + '<span class="dt-key">                |-- company_name</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">                |-- contact_name</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">                |-- contact_title</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">                |-- phone</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">                |-- fax</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">                |-- street</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">                |-- city</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">                |-- region</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">                |-- postal_code</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">                +-- country</span>: <span class="dt-type">string</span>';

            const customersTree =
                  '<span class="dt-key">customers</span> <span class="dt-comment">(root collection #2)</span>\n'
                + '<span class="dt-key">|-- _id</span>: <span class="dt-type">string</span> <span class="dt-comment">(customer_id, primary key)</span>\n'
                + '<span class="dt-key">|-- company_name</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|-- contact_name</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|-- contact_title</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|-- phone</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">|-- fax</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">+-- address</span>: <span class="dt-obj">{object}</span> <span class="dt-comment">Level 1, required</span>\n'
                + '<span class="dt-key">    |-- street</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">    |-- city</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">    |-- region</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">    |-- postal_code</span>: <span class="dt-type">string</span>\n'
                + '<span class="dt-key">    +-- country</span>: <span class="dt-type">string</span>';

            // Two collections rendered side by side, separated by a blank line.
            return ordersTree + '\n\n' + customersTree;
        }

        // ── Static Chebotko Diagram (Cassandra Northwind) ──
        // schema-section-subtitle is now dynamic via computeSchemaStats.
        // The table-cell layout below is still hand-laid for column/key
        // colouring; if the .cql file gains a table, it won't appear here
        // until added explicitly.
        function getStaticChebotkoDiagram() {
            const tables = [
                { name: 'categories', cols: [
                    { name: 'category_id', type: 'TEXT', key: 'pk' },
                    { name: 'category_name', type: 'TEXT', key: '' },
                    { name: 'description', type: 'TEXT', key: '' }
                ]},
                { name: 'suppliers', cols: [
                    { name: 'supplier_id', type: 'TEXT', key: 'pk' },
                    { name: 'company_name', type: 'TEXT', key: '' },
                    { name: 'contact_name', type: 'TEXT', key: '' },
                    { name: 'contact_title', type: 'TEXT', key: '' },
                    { name: 'phone', type: 'TEXT', key: '' },
                    { name: 'fax', type: 'TEXT', key: '' },
                    { name: 'street', type: 'TEXT', key: '' },
                    { name: 'city', type: 'TEXT', key: '' },
                    { name: 'region', type: 'TEXT', key: '' },
                    { name: 'postal_code', type: 'TEXT', key: '' },
                    { name: 'country', type: 'TEXT', key: '' }
                ]},
                { name: 'shippers', cols: [
                    { name: 'shipper_id', type: 'TEXT', key: 'pk' },
                    { name: 'company_name', type: 'TEXT', key: '' },
                    { name: 'phone', type: 'TEXT', key: '' }
                ]},
                { name: 'employees', cols: [
                    { name: 'employee_id', type: 'TEXT', key: 'pk' },
                    { name: 'last_name', type: 'TEXT', key: '' },
                    { name: 'first_name', type: 'TEXT', key: '' },
                    { name: 'title', type: 'TEXT', key: '' },
                    { name: 'birth_date', type: 'DATE', key: '' },
                    { name: 'hire_date', type: 'DATE', key: '' },
                    { name: 'phone', type: 'TEXT', key: '' },
                    { name: 'notes', type: 'TEXT', key: '' },
                    { name: 'street', type: 'TEXT', key: '' },
                    { name: 'city', type: 'TEXT', key: '' },
                    { name: 'region', type: 'TEXT', key: '' },
                    { name: 'postal_code', type: 'TEXT', key: '' },
                    { name: 'country', type: 'TEXT', key: '' },
                    { name: 'reports_to', type: 'TEXT', key: '' }
                ]},
                { name: 'customers', cols: [
                    { name: 'customer_id', type: 'TEXT', key: 'pk' },
                    { name: 'company_name', type: 'TEXT', key: '' },
                    { name: 'contact_name', type: 'TEXT', key: '' },
                    { name: 'contact_title', type: 'TEXT', key: '' },
                    { name: 'phone', type: 'TEXT', key: '' },
                    { name: 'fax', type: 'TEXT', key: '' },
                    { name: 'street', type: 'TEXT', key: '' },
                    { name: 'city', type: 'TEXT', key: '' },
                    { name: 'region', type: 'TEXT', key: '' },
                    { name: 'postal_code', type: 'TEXT', key: '' },
                    { name: 'country', type: 'TEXT', key: '' }
                ]},
                { name: 'products', cols: [
                    { name: 'category_id', type: 'TEXT', key: 'pk' },
                    { name: 'supplier_id', type: 'TEXT', key: 'pk' },
                    { name: 'product_id', type: 'TEXT', key: 'ck' },
                    { name: 'product_name', type: 'TEXT', key: '' },
                    { name: 'unit_price', type: 'DOUBLE', key: '' },
                    { name: 'units_in_stock', type: 'INT', key: '' },
                    { name: 'discontinued', type: 'BOOLEAN', key: '' },
                    { name: 'quantity_per_unit', type: 'TEXT', key: '' }
                ]},
                { name: 'orders', cols: [
                    { name: 'customer_id', type: 'TEXT', key: 'pk' },
                    { name: 'order_date', type: 'DATE', key: 'ck' },
                    { name: 'order_id', type: 'TEXT', key: 'ck' },
                    { name: 'required_date', type: 'DATE', key: '' },
                    { name: 'shipped_date', type: 'DATE', key: '' },
                    { name: 'freight', type: 'DOUBLE', key: '' },
                    { name: 'ship_name', type: 'TEXT', key: '' },
                    { name: 'ship_address', type: 'TEXT', key: '' },
                    { name: 'ship_city', type: 'TEXT', key: '' },
                    { name: 'ship_region', type: 'TEXT', key: '' },
                    { name: 'ship_postal_code', type: 'TEXT', key: '' },
                    { name: 'ship_country', type: 'TEXT', key: '' },
                    { name: 'employee_id', type: 'TEXT', key: '' },
                    { name: 'shipper_id', type: 'TEXT', key: '' }
                ]},
                { name: 'order_details', cols: [
                    { name: 'order_id', type: 'TEXT', key: 'pk' },
                    { name: 'product_id', type: 'TEXT', key: 'pk' },
                    { name: 'unit_price', type: 'DOUBLE', key: '' },
                    { name: 'quantity', type: 'INT', key: '' },
                    { name: 'discount', type: 'DOUBLE', key: '' }
                ]}
            ];
            let html = '<div class="chebotko-diagram">';
            tables.forEach(t => {
                html += '<div class="chebotko-table"><div class="chebotko-header">' + t.name + '</div>';
                html += '<table class="chebotko-cols">';
                t.cols.forEach(c => {
                    let marker = '';
                    if (c.key === 'pk') marker = '<span class="ck-marker pk">K&#x2191;</span>';
                    else if (c.key === 'ck') marker = '<span class="ck-marker ck">C&#x2191;</span>';
                    html += '<tr><td class="ck-marker-cell">' + marker + '</td>';
                    html += '<td class="ck-name">' + c.name + '</td>';
                    html += '<td class="ck-type">' + c.type + '</td></tr>';
                });
                html += '</table></div>';
            });
            html += '</div>';
            return html;
        }

        // ============================================================
        // (Inspect-mode-only JS removed — User Transformation tab is
        //  now a single page with two schema panels + script editor.)
        // ============================================================

        // ============ User Transformation tab ============
        let genState = {
            srcDbType: 'relational',
            tgtDbType: 'relational',
            kind: 'migration',           // 'migration' | 'evolution'
            currentSyntax: 'specific',
            lastResult: null,            // {specific_script, generalized_script, ...}
        };

        function selectGenKind(kind, btn) {
            document.querySelectorAll('#genKindSelector .db-type-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            genState.kind = kind;
        }

        function selectGenDbType(side, btn) {
            const container = btn.parentElement;
            container.querySelectorAll('.db-type-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            if (side === 'src') genState.srcDbType = btn.dataset.dbtype;
            else genState.tgtDbType = btn.dataset.dbtype;
        }

        // ---- Input mode + file upload, generic helper ----
        function _switchGenInputMode(side, mode, btn) {
            const parent = btn.parentElement;
            parent.querySelectorAll('.input-mode-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const prefix = 'gen' + (side === 'src' ? 'Src' : 'Tgt');
            document.getElementById(prefix + 'PasteArea').style.display = mode === 'paste' ? 'block' : 'none';
            document.getElementById(prefix + 'UploadArea').style.display = mode === 'upload' ? 'block' : 'none';
        }
        function switchGenSrcInputMode(mode, btn) { _switchGenInputMode('src', mode, btn); }

        document.addEventListener('DOMContentLoaded', () => {
            const dz = document.getElementById('genSrcDropZone');
            if (dz) dz.addEventListener('click', () => document.getElementById('genSrcFileInput').click());
        });

        function _readGenFile(side, file) {
            const prefix = 'gen' + (side === 'src' ? 'Src' : 'Tgt');
            const reader = new FileReader();
            reader.onload = function(e) {
                document.getElementById(prefix + 'Text').value = e.target.result;
                document.getElementById(prefix + 'FileInfo').textContent = 'Loaded: ' + file.name + ' (' + Math.round(file.size/1024) + ' KB)';
                const ext = file.name.split('.').pop().toLowerCase();
                const extMap = {sql:'relational', json:'document', graphql:'graph', gql:'graph', cql:'columnar'};
                if (extMap[ext]) {
                    if (side === 'src') genState.srcDbType = extMap[ext];
                    else genState.tgtDbType = extMap[ext];
                    document.querySelectorAll('#' + prefix + 'DbSelector .db-type-btn').forEach(b => {
                        b.classList.toggle('active', b.dataset.dbtype === extMap[ext]);
                    });
                }
                // Switch back to paste view to show the loaded content
                document.getElementById(prefix + 'PasteArea').style.display = 'block';
                document.getElementById(prefix + 'UploadArea').style.display = 'none';
                const modeBar = document.getElementById(prefix + 'PasteArea').parentElement.querySelectorAll('.input-mode-btn');
                modeBar.forEach((b, i) => b.classList.toggle('active', i === 0));
            };
            reader.readAsText(file);
        }
        function handleGenSrcFileDrop(e) {
            e.preventDefault();
            document.getElementById('genSrcDropZone').classList.remove('dragover');
            const f = e.dataTransfer.files[0]; if (f) _readGenFile('src', f);
        }
        function handleGenSrcFileSelect(e) { const f = e.target.files[0]; if (f) _readGenFile('src', f); }

        // ---- Inspect Source / Target → Meta V1 ----
        async function runGenInspect(side) {
            const prefix = 'gen' + (side === 'src' ? 'Src' : 'Tgt');
            const text = document.getElementById(prefix + 'Text').value.trim();
            if (!text) { alert('Paste or upload a ' + side + ' schema first.'); return; }
            const btn = document.getElementById(prefix + 'InspectBtn');
            const dbType = side === 'src' ? genState.srcDbType : genState.tgtDbType;
            btn.disabled = true; btn.textContent = 'Inspecting...';
            try {
                const resp = await fetch('/api/inspect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: text, db_type: dbType}),
                });
                const data = await resp.json();
                if (data.error) { alert('Inspect failed: ' + data.error); return; }
                _renderGenMetaResult(side, data);
            } catch (e) {
                alert('Inspect request failed: ' + e.message);
            } finally {
                btn.disabled = false;
                btn.textContent = 'Inspect ' + (side === 'src' ? 'Source' : 'Target') + ' → Meta V1';
            }
        }

        function _renderGenMetaResult(side, data) {
            const c = document.getElementById('gen' + (side === 'src' ? 'Src' : 'Tgt') + 'MetaResult');
            const s = data.summary || {};
            let html = '<div class="inspector-title" style="font-size:14px;">Meta V1 Summary</div>';
            if (data.notice) {
                html += '<div style="margin-bottom:12px;padding:8px 10px;border-radius:6px;'
                     +  'background:#FFF4E5;border:1px solid #FFCC80;color:#8A5A00;font-size:12px;">'
                     +  '⚠ [NOTICE] ' + escapeHtml(data.notice) + '</div>';
            }
            html += '<div class="summary-grid" style="margin-bottom:12px;">';
            html += '<div class="summary-card"><div class="num">' + s.entity_count + '</div><div class="label">Entities</div></div>';
            html += '<div class="summary-card"><div class="num">' + s.property_count + '</div><div class="label">Properties</div></div>';
            html += '<div class="summary-card"><div class="num">' + s.key_count + '</div><div class="label">Keys</div></div>';
            html += '<div class="summary-card"><div class="num">' + s.constraint_count + '</div><div class="label">Constraints</div></div>';
            html += '<div class="summary-card"><div class="num">' + s.relationship_count + '</div><div class="label">Relationships</div></div>';
            html += '</div>';
            html += '<table class="entity-table"><thead><tr><th>Entity</th><th>Kind</th><th>Attrs</th><th>Keys</th><th>Constraints</th><th>Rels</th></tr></thead><tbody>';
            (s.entities || []).forEach(e => {
                const kindClass = 'kind-' + (e.entity_kind || '').replace(/ /g, '_');
                html += '<tr><td><strong>' + escapeHtml(e.name) + '</strong></td>'
                     +  '<td><span class="entity-kind-badge ' + kindClass + '">' + e.entity_kind + '</span></td>'
                     +  '<td>' + e.properties + '</td><td>' + e.keys + '</td>'
                     +  '<td>' + e.constraints + '</td><td>' + e.relationships + '</td></tr>';
            });
            html += '</tbody></table>';

            // The table above only counts things. /api/inspect also returns the
            // full meta-model instance, so show what Meta V1 actually looks
            // like: typed properties, constraints and relationships per entity.
            if (data.meta_schema) {
                genState.lastMeta = genState.lastMeta || {};
                genState.lastMeta[side] = data.meta_schema;
                html += renderMetaDetailBlock('v1_' + side, 'Meta V1 Structure', data.meta_schema);
            }
            c.innerHTML = html;
        }

        // Header + card view + JSON toggle for one meta-model instance.
        function renderMetaDetailBlock(slot, title, meta) {
            metaDetailCache[slot] = meta;
            return '<div class="metav1-toolbar">'
                 + '<div class="inspector-title" style="margin:0;font-size:14px;flex:1;">' + title + '</div>'
                 + '<button class="compose-btn" onclick="toggleMetaJson(\'' + slot + '\')">Toggle JSON</button>'
                 + '</div>'
                 + '<div id="metaCards_' + slot + '">' + renderMetaDetail(meta) + '</div>'
                 + '<div id="metaJson_' + slot + '" class="metav1-json" style="display:none;"></div>';
        }

        const metaDetailCache = {};

        function toggleMetaJson(slot) {
            const cards = document.getElementById('metaCards_' + slot);
            const json = document.getElementById('metaJson_' + slot);
            if (!cards || !json) return;
            const showJson = json.style.display === 'none';
            if (showJson && !json.innerHTML) {
                json.innerHTML = syntaxHighlightJSON(JSON.stringify(metaDetailCache[slot], null, 2));
            }
            json.style.display = showJson ? 'block' : 'none';
            cards.style.display = showJson ? 'none' : 'block';
        }

        // Renders a meta-model instance as entity cards: typed properties with
        // key/optional flags, constraints with their primary-key subtype, and
        // the three relationship kinds.
        //
        // Two serializations reach this function and both must render: the
        // nested Database.to_dict() form (/api/inspect, properties carry a
        // data_type object and constraints reference properties by meta_id)
        // and the flat db_to_dict() form (/api/run_script, properties carry a
        // plain type string and relationships are pre-split into references /
        // embedded / edges). _normalizeMeta folds them into one view model so
        // the rendering below has a single shape to worry about.
        function renderMetaDetail(meta) {
            const entities = _normalizeMeta(meta);
            if (!entities.length) return '<div class="metav1-empty">No entities parsed.</div>';

            let out = '<div class="metav1-grid">';
            entities.forEach(e => {
                out += '<div class="entity-card"><div class="entity-name"><span>' + escapeHtml(e.name) + '</span>'
                     + '<span class="entity-kind-badge kind-' + escapeHtml(e.kind.replace(/ /g, '_')) + '">'
                     + escapeHtml(e.kind) + '</span></div><div class="entity-body">';

                e.labels.forEach(l => {
                    out += '<div class="metav1-constraint">label: ' + escapeHtml(l) + '</div>';
                });

                e.props.forEach(p => {
                    out += '<div class="property"><span class="attr-name">' + escapeHtml(p.name) + '</span>'
                         + '<span class="attr-type">' + p.type + '</span>';
                    if (p.is_key) out += '<span class="attr-badge pk">key</span>';
                    if (p.is_optional) out += '<span class="attr-badge optional">?</span>';
                    if (p.is_auto) out += '<span class="attr-badge ck">auto</span>';
                    out += '</div>';
                });

                if (e.constraints.length) {
                    out += '<div class="metav1-section"><div class="metav1-section-label">Constraints</div>';
                    e.constraints.forEach(c => {
                        out += '<div class="metav1-constraint ' + c.cls + '">' + c.text + '</div>';
                    });
                    out += '</div>';
                }

                if (e.rels.length) {
                    out += '<div class="metav1-section"><div class="metav1-section-label">Relationships</div>';
                    e.rels.forEach(r => {
                        out += '<div class="' + r.cls + '">' + r.text + '</div>';
                    });
                    out += '</div>';
                }

                out += '</div></div>';
            });
            return out + '</div>';
        }

        function _normalizeMeta(meta) {
            if (!meta) return [];
            const nested = meta.entity_types && typeof meta.entity_types === 'object';
            const src = nested ? meta.entity_types : meta;
            const names = Object.keys(src)
                .filter(k => !k.startsWith('__') && src[k] && typeof src[k] === 'object')
                .sort();

            const typeLabel = dt => {
                if (dt == null) return '';
                if (typeof dt === 'string') return escapeHtml(dt);
                if (dt.kind === 'list' || dt.kind === 'set') return dt.kind + '&lt;' + typeLabel(dt.element_type) + '&gt;';
                if (dt.kind === 'map') return 'map&lt;' + typeLabel(dt.key_type) + ',' + typeLabel(dt.value_type) + '&gt;';
                if (dt.kind === 'tuple') return 'tuple&lt;' + (dt.element_types || []).map(typeLabel).join(',') + '&gt;';
                let t = escapeHtml(dt.type || dt.kind || '');
                if (dt.max_length) t += '(' + dt.max_length + ')';
                else if (dt.precision != null) t += '(' + dt.precision + (dt.scale != null ? ',' + dt.scale : '') + ')';
                return t;
            };
            const card = c => c ? ' [' + escapeHtml(c) + ']' : '';

            // Nested form only: resolve the meta_id indirection in constraints.
            const propName = {}, uniqueProp = {};
            if (nested) {
                names.forEach(n => (src[n].properties || []).forEach(p => {
                    propName[p.meta_id] = p.name;
                }));
                names.forEach(n => (src[n].constraints || []).forEach(ct =>
                    (ct.unique_properties || []).forEach(up => {
                        uniqueProp[up.meta_id] = n + '.' + (propName[up.property_id] || '?');
                    })));
            }

            return names.map(name => {
                const e = src[name];
                const out = {
                    name: name,
                    kind: e.entity_kind || '',
                    labels: e.labels || [],
                    props: (e.properties || []).map(p => ({
                        name: p.name,
                        type: typeLabel(nested ? p.data_type : p.type),
                        is_key: !!p.is_key,
                        is_optional: !!p.is_optional,
                        is_auto: !!p.is_auto_generated,
                    })),
                    constraints: [],
                    rels: [],
                };

                (e.constraints || []).forEach(ct => {
                    if (nested) {
                        if (ct.constraint_type === 'unique') {
                            const cols = (ct.unique_properties || []).map(up =>
                                escapeHtml(propName[up.property_id] || up.property_id)
                                + '<span class="metav1-pktype">' + escapeHtml(up.primary_key_type || '')
                                + (up.clustering_order ? ' ' + escapeHtml(up.clustering_order) : '')
                                + '</span>').join(', ');
                            out.constraints.push({cls: '', text: (ct.is_primary_key ? 'primary key' : 'unique') + ': ' + cols});
                        } else if (ct.constraint_type === 'foreign_key') {
                            const cols = (ct.foreign_key_properties || []).map(fp =>
                                escapeHtml(propName[fp.property_id] || fp.property_id) + ' &rarr; '
                                + escapeHtml(uniqueProp[fp.points_to_unique_property_id]
                                             || fp.points_to_unique_property_id || '?')).join(', ');
                            out.constraints.push({cls: 'fk', text: 'foreign key: ' + cols});
                        } else {
                            out.constraints.push({cls: 'chk', text: escapeHtml(ct.constraint_type || 'constraint')});
                        }
                    } else {
                        const kind = (ct.type || '').toLowerCase().replace(/_/g, ' ');
                        if (ct.type === 'FOREIGN_KEY') {
                            out.constraints.push({cls: 'fk', text: 'foreign key: ' + escapeHtml(ct.column || '')
                                + ' &rarr; ' + escapeHtml(ct.references_entity || '')
                                + '.' + escapeHtml(ct.references_property || '')});
                        } else {
                            const cols = (ct.columns || []).map(escapeHtml).join(', ');
                            out.constraints.push({cls: kind.indexOf('key') >= 0 ? '' : 'chk',
                                                  text: kind + (cols ? ': ' + cols : '')});
                        }
                    }
                });

                if (nested) {
                    (e.relationships || []).forEach(r => {
                        if (r.kind === 'embedded') {
                            out.rels.push({cls: 'embedded-item', text: '&lt;&gt; ' + escapeHtml(r.aggr_name || '')
                                + ' &rarr; ' + escapeHtml(r.aggregates || '') + card(r.target_end_cardinality)});
                        } else if (r.kind === 'edge') {
                            out.rels.push({cls: 'edge-item', text: '&#x2194; ' + escapeHtml(r.rel_type_name || '')
                                + ' &rarr; ' + escapeHtml(r.target_entity || '') + card(r.target_end_cardinality)});
                        } else {
                            out.rels.push({cls: 'reference-item', text: escapeHtml(r.ref_name || '')
                                + ' &rarr; ' + escapeHtml(r.refs_to || '') + card(r.target_end_cardinality)
                                + (r.is_enforced === false ? ' (logical)' : '')});
                        }
                    });
                } else {
                    (e.references || []).forEach(r => out.rels.push({cls: 'reference-item',
                        text: escapeHtml(r.name || '') + ' &rarr; ' + escapeHtml(r.target || '')
                              + card(r.target_end_cardinality)}));
                    (e.embedded || []).forEach(r => out.rels.push({cls: 'embedded-item',
                        text: '&lt;&gt; ' + escapeHtml(r.name || '') + ' &rarr; ' + escapeHtml(r.target || '')
                              + card(r.target_end_cardinality)}));
                    (e.edges || []).forEach(r => out.rels.push({cls: 'edge-item',
                        text: '&#x2194; ' + escapeHtml(r.name || '') + ' &rarr; ' + escapeHtml(r.target || '')
                              + card(r.target_end_cardinality)}));
                }
                return out;
            });
        }

        // ---- Generate the SMILE header (user fills in operations themselves) ----
        async function runGenerate() {
            const btn = document.getElementById('genBtn');
            btn.disabled = true; btn.textContent = 'Generating...';
            try {
                const resp = await fetch('/api/generate_script', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        source_db_type: genState.srcDbType,
                        target_db_type: genState.tgtDbType,
                        kind: genState.kind,
                    }),
                });
                const data = await resp.json();
                if (data.error) { alert('Generation failed: ' + data.error); return; }
                genState.lastResult = data;
                document.getElementById('genOpCount').textContent =
                    '(' + data.source_token + ' → ' + data.target_token + ', ' + data.kind + ')';
                initComposeEditor();
                const text = genState.currentSyntax === 'specific' ? data.specific_script : data.generalized_script;
                if (composeEditor && text != null) composeEditor.setValue(text, -1);
            } catch (e) {
                alert('Request failed: ' + e.message);
            } finally {
                btn.disabled = false; btn.textContent = 'Generate Header';
            }
        }

        // ---- Natural language → SMILE script via the configured LLM ----
        async function runLlmGenerate() {
            const prompt = document.getElementById('llmPrompt').value.trim();
            if (!prompt) { alert('Describe the desired transformation first.'); return; }
            const btn = document.getElementById('llmGenBtn');
            const status = document.getElementById('composeStatus');
            btn.disabled = true; btn.textContent = 'Generating…';
            status.className = 'compose-status';
            status.textContent = 'Asking the LLM… (thinking models can take up to a minute)';
            try {
                const resp = await fetch('/api/llm_generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        prompt: prompt,
                        source_text: document.getElementById('genSrcText').value,
                        source_db_type: genState.srcDbType,
                        target_db_type: genState.tgtDbType,
                        kind: genState.kind,
                        syntax: genState.currentSyntax,
                    }),
                });
                const data = await resp.json();
                if (data.error) {
                    status.className = 'compose-status err';
                    status.textContent = 'AI generation failed: ' + data.error;
                    return;
                }
                initComposeEditor();
                if (composeEditor && data.script != null) composeEditor.setValue(data.script, -1);
                // Invalidate the header-only cache so a later syntax toggle
                // doesn't silently overwrite the AI-generated script.
                genState.lastResult = null;
                document.getElementById('genOpCount').textContent = '(AI: ' + data.model + ')';
                if (data.validation_errors && data.validation_errors.length) {
                    status.className = 'compose-status err';
                    status.textContent = '⚠ Script generated by ' + data.model
                        + ' but it still has parse errors — fix before running:\n'
                        + data.validation_errors.join('\n');
                } else {
                    status.className = 'compose-status ok';
                    status.textContent = '✓ Script generated by ' + data.model
                        + ' and validated with ANTLR. Review it, then Run ▶.';
                }
            } catch (e) {
                status.className = 'compose-status err';
                status.textContent = 'AI request failed: ' + e.message;
            } finally {
                btn.disabled = false; btn.textContent = 'Generate with AI';
            }
        }

        // ---- Editor toolbar (syntax toggle / copy / download / validate) ----
        function toggleGenSyntax(syntax, btn) {
            document.querySelectorAll('#tab-inspector .gen-output-toolbar .view-toggle-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            genState.currentSyntax = syntax;
            composeSyntax = syntax;
            const r = genState.lastResult;
            if (r && composeEditor) {
                const text = syntax === 'specific' ? r.specific_script : r.generalized_script;
                composeEditor.setValue(text, -1);
            }
        }

        function copyGenScript() {
            const text = composeEditor ? composeEditor.getValue() : '';
            if (!text) { alert('Editor is empty.'); return; }
            navigator.clipboard.writeText(text).then(
                () => { /* silent success */ },
                err => alert('Copy failed: ' + err)
            );
        }

        // Run the script against the source schema. Validation must pass first
        // — if it fails, refuse to run and show parse errors.
        async function runComposeScript() {
            if (!composeEditor) return;
            const status = document.getElementById('composeStatus');
            const valHost = document.getElementById('composeValidation');
            // Clear any stale validation panel from a previous run before
            // starting — otherwise users would see the old run's verdict
            // alongside the new run's status banner, which is misleading.
            if (valHost) valHost.innerHTML = '';
            const text = composeEditor.getValue();
            if (!text.trim()) { alert('Editor is empty.'); return; }
            const srcText = document.getElementById('genSrcText').value.trim();
            if (!srcText) { alert('Paste/upload a source schema in the left panel first.'); return; }
            // Gate: must pass validate before run
            const v = await _doValidate(text);
            if (!v || !v.ok) {
                status.className = 'compose-status err';
                status.textContent = 'Cannot run — script has parse errors:\n'
                    + ((v && v.errors) || []).join('\n');
                return;
            }
            try {
                const resp = await fetch('/api/run_script', {
                    method: 'POST',
                    headers: {'Content-Type':'application/json'},
                    body: JSON.stringify({
                        script: text,
                        source_text: srcText,
                        source_db_type: genState.srcDbType,
                        target_db_type: genState.tgtDbType,
                        syntax: composeSyntax,
                    })
                });
                const data = await resp.json();
                if (data.error || data.ok === false) {
                    status.className = 'compose-status err';
                    status.textContent = 'Run failed: ' + (data.error || (data.errors || []).join('\n'));
                    return;
                }
                // Pipe the exported real target DDL into the bottom Target Schema textarea
                if (data.exported_target != null) {
                    document.getElementById('genTgtText').value = data.exported_target;
                }
                // Render Meta V2 summary (entities, properties, keys, ...) in the M-Model panel
                if (data.meta_v2_summary) {
                    _renderMetaV2(data.meta_v2_summary, data.meta_v2);
                }
                let msg = '✓  Run successful: ' + data.operations_applied + ' / ' + data.operations_total
                        + ' operations applied. Source: ' + data.source_entity_count + ' entities → '
                        + 'Result: ' + data.result_entity_count + ' entities ('
                        + data.target_db_type + ').'
                        + '\nMeta V2 + real target DDL written to the panels below.';
                if (data.operations_skipped && data.operations_skipped.length) {
                    msg += '\n\nSkipped (handler chose not to apply, e.g. entity not found):\n'
                         + data.operations_skipped.join('\n');
                }
                // Errors are handler bugs — separated from skipped since 2026-04-29.
                // Surface them red so users can spot a real defect in their script,
                // not a deliberate handler skip.
                const hasErrors = data.operations_errors && data.operations_errors.length;
                if (hasErrors) {
                    msg += '\n\nERRORS (handler bugs — investigate):\n'
                         + data.operations_errors.join('\n');
                }
                status.className = hasErrors ? 'compose-status err' : 'compose-status ok';
                status.textContent = msg;

                // Render the three-layer validation panel (Script Execution +
                // Layer 1 + Layer 2 + blame). The backend always returns these
                // fields for /api/run_script — without this call they were
                // previously discarded, making the Compose tab silent about
                // validation outcomes. The same renderValidation helper that
                // /api/migrate uses keeps the rendering identical between the
                // canned-Northwind path and the user-script path.
                const valHost = document.getElementById('composeValidation');
                if (valHost) {
                    valHost.innerHTML = renderValidation(data) || '';
                }
            } catch (e) {
                status.className = 'compose-status err';
                status.textContent = 'Run request failed: ' + e.message;
                const valHost = document.getElementById('composeValidation');
                if (valHost) valHost.innerHTML = '';
            }
        }

        function _renderMetaV2(summary, meta) {
            const c = document.getElementById('genMetaV2Result');
            if (!summary) { c.innerHTML = ''; return; }
            let html = '<div class="summary-grid" style="margin-bottom:12px;">';
            html += '<div class="summary-card"><div class="num">' + summary.entity_count + '</div><div class="label">Entities</div></div>';
            html += '<div class="summary-card"><div class="num">' + summary.property_count + '</div><div class="label">Properties</div></div>';
            html += '<div class="summary-card"><div class="num">' + summary.key_count + '</div><div class="label">Keys</div></div>';
            html += '<div class="summary-card"><div class="num">' + summary.constraint_count + '</div><div class="label">Constraints</div></div>';
            html += '<div class="summary-card"><div class="num">' + summary.relationship_count + '</div><div class="label">Relationships</div></div>';
            html += '</div>';
            html += '<table class="entity-table"><thead><tr><th>Entity</th><th>Kind</th><th>Attrs</th><th>Keys</th><th>Constraints</th><th>Rels</th></tr></thead><tbody>';
            (summary.entities || []).forEach(e => {
                const kindClass = 'kind-' + (e.entity_kind || '').replace(/ /g, '_');
                html += '<tr><td><strong>' + escapeHtml(e.name) + '</strong></td>'
                     +  '<td><span class="entity-kind-badge ' + kindClass + '">' + e.entity_kind + '</span></td>'
                     +  '<td>' + e.properties + '</td><td>' + e.keys + '</td>'
                     +  '<td>' + e.constraints + '</td><td>' + e.relationships + '</td></tr>';
            });
            html += '</tbody></table>';
            if (meta) html += renderMetaDetailBlock('v2', 'Meta V2 Structure', meta);
            c.innerHTML = html;
        }

        function saveAsTargetSchema() {
            const text = document.getElementById('genTgtText').value;
            if (!text.trim()) { alert('Target schema is empty.'); return; }
            // File extension follows the selected Target DB type
            const extByType = {relational:'.sql', document:'.json', graph:'.graphql', columnar:'.cql'};
            const defaultExt = extByType[genState.tgtDbType] || '.txt';
            const defaultName = 'target_' + genState.tgtDbType + defaultExt;
            let filename = prompt('Save target schema as:', defaultName);
            if (!filename) return;
            filename = filename.trim();
            if (!filename) return;
            if (!/\.(sql|json|graphql|gql|cql|txt)$/i.test(filename)) filename += defaultExt;
            const blob = new Blob([text], {type: 'text/plain'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = filename;
            document.body.appendChild(a); a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        async function saveAsGenScript() {
            const text = composeEditor ? composeEditor.getValue() : '';
            if (!text) { alert('Editor is empty.'); return; }
            // Gate: must pass validate before save
            const status = document.getElementById('composeStatus');
            const v = await _doValidate(text);
            if (!v || !v.ok) {
                status.className = 'compose-status err';
                status.textContent = 'Cannot save — script has parse errors:\n'
                    + ((v && v.errors) || []).join('\n');
                return;
            }
            const isSpec = genState.currentSyntax === 'specific';
            const defaultExt = isSpec ? '.smile' : '.smile_gen';
            const flavor = (genState.kind === 'evolution') ? 'evolution' : 'migration';
            const defaultName = (flavor + '_' + genState.srcDbType + '_to_' + genState.tgtDbType + defaultExt)
                                  .replace(/__+/g, '_');
            let filename = prompt('Save script as:', defaultName);
            if (!filename) return;  // user cancelled
            filename = filename.trim();
            if (!filename) return;
            // Force one of the SMILE extensions if user typed something else
            if (!filename.endsWith('.smile') && !filename.endsWith('.smile_gen')) {
                filename += defaultExt;
            }
            const blob = new Blob([text], {type: 'text/plain'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = filename;
            document.body.appendChild(a); a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        // ============ Compose Script Tab — Ace Editor + SMILE autocomplete ============
        let composeEditor = null;
        let composeSyntax = 'specific';
        let opsSpec = null;            // /api/operations_spec result, cached
        let lastInspectorScripts = null;  // to support "Import from Inspector"

        async function ensureOpsSpec() {
            if (opsSpec) return opsSpec;
            const resp = await fetch('/api/operations_spec');
            opsSpec = await resp.json();
            return opsSpec;
        }

        function initComposeEditor() {
            if (composeEditor || typeof ace === 'undefined') return;
            ace.require('ace/ext/language_tools');
            composeEditor = ace.edit('composeEditor');
            composeEditor.setTheme('ace/theme/textmate');
            composeEditor.session.setMode('ace/mode/sql');  // close-enough highlighting
            composeEditor.setOptions({
                enableBasicAutocompletion: true,
                enableLiveAutocompletion: true,
                enableSnippets: true,
                fontSize: '13px',
                showPrintMargin: false,
                wrap: false,
                useSoftTabs: true,
                tabSize: 2,
            });
            // Replace default completers with our two SMILE completers:
            //   opKeywordCompleter — handles multi-word op keywords (space-aware prefix)
            //   smileCompleter      — handles clauses + enum values (default prefix)
            composeEditor.completers = [opKeywordCompleter, smileCompleter];
            // Seed with header skeleton
            composeEditor.setValue(
                'MIGRATION my_migration:1.0\nFROM RELATIONAL TO RELATIONAL\nUSING my_schema VERSION 1.0\n\n',
                -1
            );
            // Pre-load the operation spec so first keystroke is fast
            ensureOpsSpec();
        }

        function switchComposeSyntax(syntax, btn) {
            document.querySelectorAll('.compose-syntax-toggle .view-toggle-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            composeSyntax = syntax;
        }

        function clearComposeEditor() {
            if (composeEditor) composeEditor.setValue('', -1);
        }

        function loadComposeFromInspector() {
            const r = genState.lastResult;
            if (!r) { alert('No script available — generate one in the Inspector tab first.'); return; }
            const text = composeSyntax === 'specific' ? r.specific_script : r.generalized_script;
            if (!composeEditor) initComposeEditor();
            composeEditor.setValue(text, -1);
        }

        function downloadComposeScript() {
            if (!composeEditor) return;
            const text = composeEditor.getValue();
            const ext = composeSyntax === 'specific' ? '.smile' : '.smile_gen';
            const blob = new Blob([text], {type: 'text/plain'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = 'script' + ext;
            document.body.appendChild(a); a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        // _doValidate(text) returns {ok: true} or {ok: false, errors: [...]}.
        // Used both by the Validate button and as a gate before Run / Save As.
        async function _doValidate(text) {
            const resp = await fetch('/api/validate_script', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({text: text, syntax: composeSyntax})
            });
            return await resp.json();
        }

        async function validateComposeScript() {
            if (!composeEditor) return null;
            const text = composeEditor.getValue();
            const status = document.getElementById('composeStatus');
            try {
                const data = await _doValidate(text);
                if (data.error) {
                    status.className = 'compose-status err';
                    status.textContent = 'Validation request failed: ' + data.error;
                    return null;
                }
                if (data.ok) {
                    status.className = 'compose-status ok';
                    status.textContent = '✓  Script parses cleanly under ' + composeSyntax + ' grammar.';
                    return data;
                } else {
                    status.className = 'compose-status err';
                    status.textContent = (data.errors.length + ' parse error(s):\n') + data.errors.join('\n');
                    return data;
                }
            } catch (e) {
                status.className = 'compose-status err';
                status.textContent = 'Request failed: ' + e.message;
                return null;
            }
        }

        // ---- The SMILE completer for Ace ----
        // Strategy:
        //   1. If text-before-cursor (within current line/operation) starts with a known
        //      operation keyword, suggest the clauses defined for that op + enum values
        //      based on the most recent clause keyword.
        //   2. Otherwise (line-start context), suggest all 38 operation keywords as
        //      snippets that expand the whole skeleton.
        // === Completer A: operation keywords (space-inclusive prefix) ===
        // Handles multi-word generalized keywords like "ADD FOREIGN KEY".
        // Ace's default prefix scanner stops at any non-word char, so "ADD FOREIGN"
        // would scan as prefix="FOREIGN" — and the caption "ADD FOREIGN KEY" then
        // gets filtered out. Including space in the scanner lets the full multi-word
        // prefix flow through to filtering.
        const opKeywordCompleter = {
            identifierRegexps: [/[a-zA-Z_0-9 ]/],
            getCompletions: async function(editor, session, pos, prefix, callback) {
                try {
                    const spec = await ensureOpsSpec();
                    const ops = spec.operations || {};
                    const completions = [];
                    for (const opKey of Object.keys(ops)) {
                        const info = ops[opKey];
                        const kw = composeSyntax === 'specific' ? info.specific : info.generalized;
                        const snip = composeSyntax === 'specific'
                            ? (info.snippet_specific || kw + ' $0')
                            : (info.snippet_generalized || kw + ' $0');
                        completions.push({
                            caption: kw,
                            snippet: snip,
                            meta: info.category || 'op',
                            docText: info.doc + '\n\n' +
                                     (composeSyntax === 'specific'
                                        ? (info.syntax_specific || '')
                                        : (info.syntax_generalized || '')),
                            score: 900,
                        });
                    }
                    completions.push({caption: 'MIGRATION', snippet: spec.header.migration.snippet, meta: 'header', score: 1000});
                    completions.push({caption: 'EVOLUTION', snippet: spec.header.evolution.snippet, meta: 'header', score: 1000});
                    callback(null, completions);
                } catch (e) {
                    callback(null, []);
                }
            },
            getDocTooltip: function(item) {
                if (item.docText) {
                    item.docHTML = '<pre style="font-size:11px;line-height:1.4;white-space:pre-wrap;max-width:480px;">'
                        + (item.docText || '').replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</pre>';
                }
            },
        };

        // === Completer B: clauses + enum values (default prefix) ===
        const smileCompleter = {
            getCompletions: async function(editor, session, pos, prefix, callback) {
                try {
                    const spec = await ensureOpsSpec();
                    const ops = spec.operations || {};
                    const enums = spec.enums || {};
                    const text = session.getValue();
                    const cursorOffset = session.doc.positionToIndex(pos);
                    const textBefore = text.slice(0, cursorOffset);

                    // Find the most recent operation keyword (by scanning backwards
                    // through the current "operation" — bounded by blank lines or
                    // start-of-doc). For simplicity: scan back to the previous newline
                    // followed by another newline OR start.
                    const lastBlank = textBefore.lastIndexOf('\n\n');
                    const opChunk = lastBlank >= 0 ? textBefore.slice(lastBlank + 2) : textBefore;
                    const trimmed = opChunk.trimStart();

                    // Detect the leading operation keyword
                    let activeOp = null;
                    for (const opKey of Object.keys(ops)) {
                        const info = ops[opKey];
                        const kw = composeSyntax === 'specific' ? info.specific : info.generalized;
                        if (trimmed.toUpperCase().startsWith(kw.toUpperCase() + ' ') ||
                            trimmed.toUpperCase() === kw.toUpperCase()) {
                            activeOp = {opKey, info, kw};
                            break;
                        }
                    }

                    const completions = [];

                    // Branch 1: inside an active operation — suggest its clauses + enum values
                    if (activeOp) {
                        const lastTok = trimmed.toUpperCase().trim();
                        // Enum-value position: text ends with "WITH CARDINALITY", "AS", "TO", etc.
                        if (lastTok.endsWith('WITH CARDINALITY')) {
                            for (const v of (enums.cardinalityType || [])) {
                                completions.push({caption: v, value: v, meta: 'cardinality', score: 1000});
                            }
                        } else if (lastTok.endsWith(' TO') &&
                                   (activeOp.opKey === 'CAST_ENTITY' || activeOp.opKey === 'CAST_PROPERTY' ||
                                    activeOp.opKey === 'CAST_CONSTRAINT' || activeOp.opKey === 'RECARD')) {
                            const enumKey = (activeOp.opKey === 'CAST_ENTITY')
                                ? 'databaseType'
                                : (activeOp.opKey === 'CAST_CONSTRAINT')
                                    ? 'constraintKeyType'
                                    : (activeOp.opKey === 'RECARD')
                                        ? 'cardinalityType'
                                        : 'dataType';
                            for (const v of (enums[enumKey] || [])) {
                                completions.push({caption: v, value: v, meta: 'enum', score: 1000});
                            }
                        } else if (lastTok.endsWith(' AS') &&
                                   (activeOp.opKey === 'ADD_PRIMARY_KEY' || activeOp.opKey === 'ADD_UNIQUE_KEY' ||
                                    activeOp.opKey === 'ADD_PARTITION_KEY' || activeOp.opKey === 'ADD_CLUSTERING_KEY')) {
                            for (const v of (enums.dataType || [])) {
                                completions.push({caption: v, value: v, meta: 'type', score: 1000});
                            }
                        } else if (lastTok.endsWith('WITH TYPE')) {
                            for (const v of (enums.dataType || [])) {
                                completions.push({caption: v, value: v, meta: 'type', score: 1000});
                            }
                        } else {
                            // Suggest clauses
                            const clauses = activeOp.info.clauses || [];
                            for (const c of clauses) {
                                const cap = c.name;
                                let val;
                                if (c.snippet) val = c.snippet;
                                else if (c.values_ref) val = c.name + ' ${1|' + (enums[c.values_ref] || []).join(',') + '|}$0';
                                else val = c.name;
                                completions.push({
                                    caption: cap + (c.optional ? ' (optional)' : ''),
                                    snippet: val,
                                    meta: 'clause',
                                    docText: c.doc || '',
                                    score: 800,
                                });
                            }
                        }
                    }
                    // Else branch (no active op): operation keywords are served by
                    // opKeywordCompleter — this completer stays silent here.

                    callback(null, completions);
                } catch (e) {
                    console.warn('smileCompleter failed:', e);
                    callback(null, []);
                }
            },
            // Show docs in the popup tooltip
            getDocTooltip: function(item) {
                if (item.docText) {
                    item.docHTML = '<pre style="font-size:11px;line-height:1.4;white-space:pre-wrap;max-width:480px;">'
                        + (item.docText || '').replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</pre>';
                }
            },
        };

        // Load Source Schemas on page load
        loadSourceSchemas();
