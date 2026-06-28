"""SMILE CLI - Command Line Interface for Schema Migration & Evolution Language"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core import run_migration
from config import MIGRATION_CONFIGS, DB_TYPE_DISPLAY_NAME, DB_TYPE_EXPORT_LABEL

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Menu choice -> config key mapping (auto-generated from MIGRATION_CONFIGS)
CHOICE_MAP = {str(i): key for i, key in enumerate(MIGRATION_CONFIGS.keys(), 1)}


def print_operations(operations_detail):
    """Print operation execution results."""
    for op in operations_detail:
        keyword = op.get("original_keyword", op["type"])
        if op["status"] == "success":
            print(f"         {GREEN}[OK]{RESET} {keyword}")
        else:
            print(f"         {YELLOW}[SKIP]{RESET} {keyword} (no effect)")


def print_schema_comparison(result):
    """Print source and result schema side by side."""
    source_type = result["source_type"]
    target_type = result["target_type"]
    meta_v1 = result["meta_v1"]
    meta_v2 = result["result"]
    changes = result["changes"]
    col_width = 38

    # Collect highlights from changes
    nest_highlights = set()
    ref_highlights = set()
    new_entities = set()
    for change in changes:
        if change.startswith("NEST:"):
            nest_highlights.add(change[5:])
        elif change.startswith("ADD_REF:"):
            ref_highlights.add(change[8:])
        elif change.startswith("SPLIT:"):
            # SPLIT:customers->customers,customer_tag — new entities after the comma
            parts = change.split("->")
            if len(parts) == 2:
                for name in parts[1].split(","):
                    name = name.strip()
                    if name and name not in parts[0].split(":")[1].strip():
                        new_entities.add(name)

    total_width = col_width * 2 + 3
    print("\n" + "=" * total_width)
    print(f"{BOLD} SCHEMA TRANSFORMATION: {source_type} -> {target_type}{RESET}")
    print("=" * total_width)

    print(f"\n  {GREEN}{BOLD}[EMBED]{RESET} = Embedded   {CYAN}[REF]{RESET} = Reference/FK")
    print()

    headers = ["Meta V1 (Source)", "Meta V2 (Result)"]
    print("-" * total_width)
    print(" | ".join(h.center(col_width) for h in headers))
    print("-" * total_width)

    all_entities = set(
        k for k in list(meta_v1.keys()) + list(meta_v2.keys())
        if not k.startswith('__')
    )
    for entity_name in sorted(all_entities):
        columns = []
        max_lines = 0

        for i, schema in enumerate([meta_v1, meta_v2]):
            entity = schema.get(entity_name)
            if entity:
                lines = [f"  {entity['name']}".ljust(col_width)]
                for attr in entity.get("properties", []):
                    marker = "[PK]" if attr["is_key"] else ("?" if attr["is_optional"] else "")
                    is_highlighted = (i == 1 and entity_name in new_entities)
                    prefix = f"{GREEN}" if is_highlighted else ""
                    suffix = f"{RESET}" if is_highlighted else ""
                    line = f"    {attr['name']}: {attr['type']} {marker}"
                    lines.append(f"{prefix}{line}{suffix}".ljust(col_width + (len(prefix) + len(suffix) if is_highlighted else 0)))
                for ref in entity.get("references", []):
                    ref_key = f"{entity_name}.{ref['name']}"
                    is_highlighted = (i == 1 and ref_key in ref_highlights)
                    prefix = f"{CYAN}" if is_highlighted else ""
                    suffix = f"{RESET}" if is_highlighted else ""
                    line = f"    -> {ref['name']} -> {ref['target']}"
                    lines.append(f"{prefix}{line}{suffix}".ljust(col_width + (len(prefix) + len(suffix) if is_highlighted else 0)))
                for emb in entity.get("embedded", []):
                    emb_key = f"{entity_name}.{emb['name']}"
                    is_highlighted = (i == 1 and emb_key in nest_highlights)
                    prefix = f"{GREEN}{BOLD}" if is_highlighted else ""
                    suffix = f"{RESET}" if is_highlighted else ""
                    line = f"    <> {emb['name']} [{emb['target_end_cardinality']}]"
                    lines.append(f"{prefix}{line}{suffix}".ljust(col_width + (len(prefix) + len(suffix) if is_highlighted else 0)))
            else:
                lines = [f"  {YELLOW}({entity_name} --){RESET}".ljust(col_width + len(YELLOW) + len(RESET))]

            columns.append(lines)
            max_lines = max(max_lines, len(lines))

        for col_lines in columns:
            while len(col_lines) < max_lines:
                col_lines.append(" " * col_width)

        for row in range(max_lines):
            print(" | ".join(columns[j][row] for j in range(2)))
        print("-" * total_width)


def print_exported_target(result):
    """Print the exported Target Schema in native format."""
    target_type = result["target_type"]
    exported = result["exported_target"]

    print()
    print("=" * 80)
    print(f"{BOLD} EXPORTED TARGET SCHEMA ({target_type}){RESET}")
    print("=" * 80)
    print()

    label = DB_TYPE_EXPORT_LABEL.get(target_type, f"{target_type} Schema")
    print(f"{CYAN}{label}:{RESET}")
    print("-" * 80)
    print(exported)
    print("-" * 80)


def print_validation(result):
    """Print three-layer validation results."""
    v_layer0 = result.get("validation_layer0", {})
    v_meta = result.get("validation_meta", {})
    v_export = result.get("validation_export", {})
    v_summary = result.get("validation_summary", "")

    # Detect the validation-crashed state explicitly. The fallback in
    # ``core.run_migration`` sets every layer to ``passed=None`` AND prefixes
    # ``validation_summary`` with ``"validation crashed:"`` — that prefix is
    # the unambiguous signal (a legitimately N/A run just says
    # ``"validation skipped (no expected target file or adapter)"``).
    crashed = (
        v_layer0.get("passed") is None
        and v_meta.get("passed") is None
        and v_export.get("passed") is None
        and v_summary.startswith("validation crashed:")
    )

    # Skip if all three are legitimately N/A (no target file + no adapter)
    # AND we're not in the crashed state. The crashed state still gets a
    # rendered panel below.
    if (not crashed
            and v_layer0.get("passed") is None
            and v_meta.get("passed") is None
            and v_export.get("passed") is None):
        return

    print(f"\n{BOLD}{'=' * 50}")
    print(" VALIDATION")
    print(f"{'=' * 50}{RESET}")

    if crashed:
        print(f"  {RED}{BOLD}VALIDATION CRASHED{RESET}: "
              f"{v_summary[len('validation crashed:'):].strip()}")
        print(f"  {YELLOW}The validation pipeline raised an exception before "
              f"producing layer reports. Treat this run's correctness as "
              f"UNKNOWN, not as a successful validation.{RESET}")
        return

    # ── Script Execution check ────────────────────────────────────────
    # User-facing label is "Script Execution" rather than "Layer 0" —
    # plain English reads better in CLI / Web cards than the internal
    # numbering. The variable name still tracks the layer 0 / 1 / 2
    # ordering for code readability.
    l0_passed = v_layer0.get("passed")
    l0_summary = v_layer0.get("summary", "Other reasons")
    if l0_passed is True:
        print(f"  Script Execution: {GREEN}{BOLD}{l0_summary}{RESET}")
    elif l0_passed is False:
        print(f"  Script Execution: {RED}{BOLD}{l0_summary}{RESET}")
        # List every failed step so the user can locate the SMILE line that
        # broke. ``failed_steps`` is populated by ``derive_layer0`` for both
        # ``error`` (handler exception) and ``skipped`` (deliberate skip)
        # statuses — both are surfaced here because they're both signals
        # the user typically needs to act on.
        for step in v_layer0.get("details", {}).get("failed_steps", []):
            keyword = step.get("original_keyword") or step.get("type", "?")
            status = (step.get("status") or "").upper()
            reason = step.get("reason", "")
            step_idx = step.get("step", "?")
            print(f"    {YELLOW}Step {step_idx}{RESET} [{status}] "
                  f"{keyword}: {reason}")
    else:
        print(f"  Script Execution: {l0_summary}")

    # ── Layer 1 + Layer 2: existing two-layer rendering ────────────────
    for label, v in [("Layer 1 (SMILE Script)", v_meta), ("Layer 2 (Adapter Export)", v_export)]:
        passed = v.get("passed")
        summary = v.get("summary", "Other reasons")
        if passed is True:
            print(f"  {label}: {GREEN}{BOLD}{summary}{RESET}")
        elif passed is False:
            print(f"  {label}: {RED}{BOLD}{summary}{RESET}")
            # Print details for failed validation
            details = v.get("details", {})
            if details.get("missing_entities"):
                print(f"    Missing entities: {', '.join(details['missing_entities'])}")
            if details.get("extra_entities"):
                print(f"    Extra entities: {', '.join(details['extra_entities'])}")
            for ename, ediff in details.get("entity_diffs", {}).items():
                parts = []
                attr_d = ediff.get("properties", {})
                if attr_d.get("missing"):
                    parts.append(f"missing attrs: {attr_d['missing']}")
                if attr_d.get("extra"):
                    parts.append(f"extra attrs: {attr_d['extra']}")
                if attr_d.get("type_mismatches"):
                    for tm in attr_d["type_mismatches"]:
                        parts.append(f"{tm['attr']}: {tm['actual']} != {tm['expected']}")
                if attr_d.get("key_mismatches"):
                    for km in attr_d["key_mismatches"]:
                        parts.append(f"key mismatch: {km}")
                constraint_d = ediff.get("constraints", {})
                if constraint_d.get("missing"):
                    parts.append(f"missing constraints: {len(constraint_d['missing'])}")
                if constraint_d.get("extra"):
                    parts.append(f"extra constraints: {len(constraint_d['extra'])}")
                ref_d = ediff.get("references", {})
                if ref_d.get("missing"):
                    parts.append(f"missing refs: {ref_d['missing']}")
                if ref_d.get("extra"):
                    parts.append(f"extra refs: {ref_d['extra']}")
                emb_d = ediff.get("embedded", {})
                if emb_d.get("missing"):
                    parts.append(f"missing embedded: {emb_d['missing']}")
                if emb_d.get("extra"):
                    parts.append(f"extra embedded: {emb_d['extra']}")
                if parts:
                    print(f"    {YELLOW}{ename}{RESET}: {'; '.join(parts)}")
        else:
            print(f"  {label}: {summary}")

    print()


def main():
    print(f"\n{BOLD}{'=' * 60}")
    print(" SMILE - Schema Migration & Evolution Language")
    print(f"{'=' * 60}{RESET}")
    # Auto-generate menu from MIGRATION_CONFIGS, grouped by direction
    current_direction = None
    for idx, (key, cfg) in enumerate(MIGRATION_CONFIGS.items(), 1):
        direction_key = f"{cfg.source_type}->{cfg.target_type}"
        if direction_key != current_direction:
            current_direction = direction_key
            src = DB_TYPE_DISPLAY_NAME.get(cfg.source_type, cfg.source_type)
            tgt = DB_TYPE_DISPLAY_NAME.get(cfg.target_type, cfg.target_type)
            print(f"\n  {CYAN}{src} -> {tgt}:{RESET}")
        print(f"  [{idx}] {cfg.display_name}")
    print("\n  [0] Exit")

    try:
        choice = input("\nChoice: ").strip()
    except (KeyboardInterrupt, EOFError):
        return 0

    if choice == "0":
        return 0

    direction = CHOICE_MAP.get(choice)
    if not direction:
        print("Invalid choice")
        return 1

    config = MIGRATION_CONFIGS[direction]
    source_type = config.source_type
    target_type = config.target_type
    smile_file = config.smile_file

    for f in [config.source_file, config.smile_file]:
        if not f.exists():
            print(f"{RED}[ERROR] File not found: {f}{RESET}")
            return 1

    print(f"\n{CYAN}[Step 1] Reverse Engineering -> Meta V1{RESET}")
    print(f"\n{CYAN}[Step 2] Transformation: Meta V1 + {smile_file.name} -> Meta V2{RESET}")

    result = run_migration(direction)

    if result.get("error"):
        print(f"{RED}[ERROR] {result['error']}{RESET}")
        return 1

    operations_detail = result.get("operations_detail", [])
    print_operations(operations_detail)

    exec_stats = result.get("execution_stats", {})
    success_count = exec_stats.get("success", 0)
    skipped_count = exec_stats.get("skipped", 0)
    if skipped_count == 0:
        print(f"         {GREEN}{BOLD}All {success_count} operations executed successfully{RESET}")
    else:
        print(f"         {YELLOW}Executed: {success_count}, Skipped: {skipped_count}{RESET}")
    print(f"         Result has {result['stats']['result_count']} entities")

    print(f"\n{CYAN}[Step 3] Forward Engineering: Meta V2 -> Generated {target_type} DDL{RESET}")
    print(f"         Generated {len(result['exported_target'])} characters")

    # Display results
    print_schema_comparison(result)
    print_exported_target(result)

    # Summary
    print(f"\n{BOLD}{'=' * 50}")
    print(" SUMMARY")
    print(f"{'=' * 50}{RESET}")
    print(f"\n  Source: {result['stats']['source_count']} entities ({source_type})")
    print(f"  Result: {result['stats']['result_count']} entities after {result['operations_count']} operations")
    print(f"  Direction: {source_type} -> {target_type}")
    print(f"\n  {GREEN}{BOLD}[OK] TRANSFORMATION COMPLETE{RESET}")
    print(f"  {'=' * 30}")

    # Validation results
    print_validation(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
