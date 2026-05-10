"""Helper to patch vibecode/indexer/__init__.py with check_index_freshness."""
import pathlib

path = pathlib.Path(r"C:\DATA\PROJECTS\VibecodeApp\vibecode\indexer\__init__.py")
original = path.read_text(encoding="utf-8")

# Step 1: Add the import after the classifier import
original = original.replace(
    "from vibecode.indexer.classifier import FileRecord, classify\n",
    "from vibecode.indexer.classifier import FileRecord, classify\nfrom vibecode.git_state import current_git_commit\n"
)

# Step 2: Add to __all__
original = original.replace(
    '    "write_entrypoints",\n]',
    '    "write_entrypoints",\n    "check_index_freshness",\n]'
)

# Step 3: Add check_index_freshness function before cmd_index
func = (
    "\n\ndef check_index_freshness("
    "\n    repo_root: Path,"
    "\n    max_age_seconds: float = 300.0,"
    "\n) -> tuple[bool, str]:"
    "\n    \"\"\"Check whether the existing index is fresh enough to use."
    "\n"
    "\n    The index is considered stale if it does not exist, if it was"
    "\n    built more than *max_age_seconds* ago, or if the git HEAD changed"
    "\n    since the index was built."
    "\n"
    "\n    Returns"
    "\n    -------"
    "\n    (fresh, detail_message)"
    "\n        *fresh* is True when the index looks current; False otherwise."
    "\n        *detail_message* explains why it is stale (or \"fresh\")."
    "\n"
    "\n    \"\"\""
    "\n    index_path = repo_root / \".vibecode\" / \"current\" / \"last_index.json\""
    "\n"
    "\n    if not index_path.exists():"
    "\n        return False, \"No index found -- run 'vibecode index' first.\""
    "\n"
    "\n    try:"
    "\n        record = json.loads(index_path.read_text(encoding=\"utf-8\"))"
    "\n    except (json.JSONDecodeError, OSError) as exc:"
    "\n        return False, \"Cannot parse last index record: {exc}\".format(exc=exc)"
    "\n"
    "\n    # Check age."
    "\n    started_at = record.get(\"started_at\", \"\")"
    "\n    if started_at:"
    "\n        from datetime import datetime as _dt, timezone as _tz"
    "\n        started_dt = _dt.fromisoformat(started_at)"
    "\n        age = (_dt.now(tz=_tz.utc) - started_dt).total_seconds()"
    "\n        if age > max_age_seconds:"
    "\n            return False, ("
    "\n                \"Index is {age:.0f}s old (>{max_age_seconds:.0f}s) \""
    "\n                \"-- run 'vibecode index' to refresh.\""
    "\n            ).format(age=age, max_age_seconds=max_age_seconds)"
    "\n"
    "\n    # Check git commit."
    "\n    recorded_commit = record.get(\"git_commit\")"
    "\n    if recorded_commit and recorded_commit != \"unknown\":"
    "\n        current_commit = current_git_commit(repo_root)"
    "\n        if current_commit != \"unknown\" and current_commit != recorded_commit:"
    "\n            return False, ("
    "\n                \"Index was built for commit {recorded_commit}, \""
    "\n                \"but HEAD is now {current_commit} -- re-index.\""
    "\n            ).format(recorded_commit=recorded_commit, current_commit=current_commit)"
    "\n"
    "\n    return True, \"fresh\""
)

original = original.replace("def cmd_index(args)", func + "\ndef cmd_index(args)")

path.write_text(original, encoding="utf-8")
print("File written successfully")
print("Length:", len(original))
print("Has check_index_freshness:", "check_index_freshness" in original)
print("Has import:", "from vibecode.git_state import current_git_commit" in original)