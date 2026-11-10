"""Exact legacy local state reader and maintenance hook from main 3aa3700.

Dependencies are injected by the offline mixed-version tests.
"""
def _auto_update_state(state):
    path = Distribution.ordinary(state, "auto-update.json")
    value = Distribution.json(path.read_bytes()) if path.exists() else {}
    if not isinstance(value, dict) or set(value) - {"last_attempt", "skip_release", "available_release", "available_tree", "available_entries", "available_timer_only"}:
        raise DistributionError("invalid auto-update state; preserve state")
    if 'available_timer_only' in value and type(value['available_timer_only']) is not bool:
        raise DistributionError("invalid timer-only update plan; preserve state")
    if "last_attempt" in value:
        day = value["last_attempt"]
        if not isinstance(day, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):
            raise DistributionError("invalid automatic check day; preserve state")
        Distribution.calendar_day(day.replace("-", "."))
    return value


def auto_update_local(data_dir, enabled, _locked=False, advisory_only=False, started_at=None):
    """Post-data maintenance; its failure never changes the data result."""
    if (enabled is False and not advisory_only) or os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        return
    message = ""
    try:
        import contextlib
        data_dir = Path(data_dir)
        if not _converted_installation(data_dir) or _known_local_identity(data_dir / "section11") is None:
            return
        with (contextlib.nullcontext() if _locked else _distribution_lock(data_dir)), _release_request_budget():
            root = data_dir / "section11"
            if _is_git_checkout(root):
                raise DistributionError("developer checkout; use a separate release installation")
            state = data_dir / ".section11-state"
            saved = _auto_update_state(state)
            now = (started_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
            if now.hour < 4:
                return
            today = now.date().isoformat()
            if saved.get("last_attempt", "") >= today:
                message = "already checked this UTC day (or recorded clock is ahead)"
            else:
                # Claim the day before any request, including unsuccessful checks.
                saved["last_attempt"] = today
                # A failed discovery does not resolve a previously verified plan.
                if not _local_notice_matches(data_dir, saved):
                    for key in ("available_release", "available_tree", "available_entries", "available_timer_only"):
                        saved.pop(key, None)
                _write_install_state(state, "auto-update.json", saved)
                if not isinstance(enabled, bool):
                    raise DistributionError("auto_update must be a JSON boolean")
                raw, files, identity = _fetch_verified_release()
                status = _local_release_status(root, raw, files, identity)
                _ensure_custom(data_dir, files)
                expected = _local_plan(data_dir, raw, files)
                plan = expected['distribution']
                needs_install = _local_install_needed(data_dir, raw, identity, expected)
                if saved.get("skip_release") == identity["tag"]:
                    message = "rolled-back release " + identity["tag"] + " remains skipped"
                elif status["content_ahead"]:
                    message = "installed content is newer than the latest official release; wait for its release or review --update"
                elif not needs_install:
                    message = "already current with " + identity["tag"]
                else:
                    saved.update(available_release=identity["tag"],
                                 available_tree=_ordinary_tree_digest(root),
                                 available_entries=expected['entries'],
                                 available_timer_only=not (_local_managed_needed(root, raw, identity, plan) or
                                                           any(expected['entries'].values())))
                    _write_install_state(state, "auto-update.json", saved)
                    if not enabled:
                        message = "official release " + identity["tag"] + " available; run python3 section11/examples/sync.py --update"
                    else:
                        _install_local(data_dir, raw, files, identity, expected, _locked=True)
                        message = "installed " + status["installed_date"] + " -> " + identity["tag"]
                        if plan["changed"] or plan["removed"]:
                            message += "; replaced/removed: " + ", ".join(plan["changed"] + plan["removed"])
                        if expected['cleanup_names']:
                            message += '; removed outside section11/: ' + ', '.join(expected['cleanup_names'])
                if saved.get("skip_release") == identity["tag"] or status["content_ahead"] or not needs_install:
                    for key in ("available_release", "available_tree", "available_entries", "available_timer_only"):
                        saved.pop(key, None)
                    _write_install_state(state, "auto-update.json", saved)
    except (Exception, KeyboardInterrupt) as exc:
        message = "stopped; sync result retained; " + " ".join(str(exc).split())
    print("Section 11 auto-update: " + message)
