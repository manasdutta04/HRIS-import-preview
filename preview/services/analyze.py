from collections import Counter


def analyze(rows):
    """Validate identity, resolve managers, then inspect the reporting graph.

    Identity problems drop a row from analysis entirely. Manager problems
    keep the employee but do not create a reporting relationship and do
    not make them a root.
    """
    identity_errors, accepted = _split_identity(rows)
    by_id = {row["employee_id"]: row for row in accepted}
    by_email = {row["email"]: row for row in accepted}

    manager_errors, manager_of, roots = _resolve_managers(accepted, by_id, by_email)
    managers = _direct_report_counts(manager_of, by_id)
    cycle_ids = _cycle_members(manager_of)

    accepted_sorted = sorted(accepted, key=lambda row: row["source_row"])
    roots_sorted = sorted(roots, key=lambda row: row["source_row"])
    cycle_members = sorted(
        (by_id[employee_id] for employee_id in cycle_ids),
        key=lambda row: row["employee_id"],
    )

    return {
        "source_row_count": len(rows),
        "accepted": accepted_sorted,
        "errors": identity_errors + manager_errors,
        "roots": roots_sorted,
        "managers": managers,
        "cycle_members": cycle_members,
    }


def _split_identity(rows):
    id_counts = Counter(row["employee_id"] for row in rows if row["employee_id"])
    email_counts = Counter(row["email"] for row in rows if row["email"])

    errors = []
    accepted = []

    for row in rows:
        row_errors = []
        if not row["employee_id"]:
            row_errors.append("employee_id is required")
        if not row["email"]:
            row_errors.append("email is required")
        if row["employee_id"] and id_counts[row["employee_id"]] > 1:
            row_errors.append(f"duplicate employee_id '{row['employee_id']}'")
        if row["email"] and email_counts[row["email"]] > 1:
            row_errors.append(f"duplicate email '{row['email']}'")

        if row_errors:
            for message in row_errors:
                errors.append(_error(row, message))
        else:
            accepted.append(row)

    return errors, accepted


def _resolve_managers(accepted, by_id, by_email):
    errors = []
    manager_of = {}
    roots = []

    for row in accepted:
        manager_id = row["manager_id"]
        manager_email = row["manager_email"]

        if not manager_id and not manager_email:
            roots.append(row)
            continue

        resolved, lookup_errors = _lookup_manager(
            row, manager_id, manager_email, by_id, by_email
        )
        if lookup_errors:
            errors.extend(lookup_errors)
            continue

        if resolved["employee_id"] == row["employee_id"]:
            errors.append(_error(row, "employee cannot manage themselves"))
            continue

        manager_of[row["employee_id"]] = resolved["employee_id"]

    return errors, manager_of, roots


def _lookup_manager(row, manager_id, manager_email, by_id, by_email):
    """Return (resolved_employee, errors). Invalid identity rows are not in the maps."""
    if manager_id and manager_email:
        by_id_hit = by_id.get(manager_id)
        by_email_hit = by_email.get(manager_email)
        errors = []
        if by_id_hit is None:
            errors.append(_error(row, f"manager_id '{manager_id}' was not found"))
        if by_email_hit is None:
            errors.append(_error(row, f"manager_email '{manager_email}' was not found"))
        if by_id_hit is not None and by_email_hit is not None:
            if by_id_hit["employee_id"] != by_email_hit["employee_id"]:
                errors.append(
                    _error(
                        row,
                        "manager_id and manager_email refer to different employees "
                        f"('{by_id_hit['employee_id']}' vs '{by_email_hit['employee_id']}')",
                    )
                )
            elif not errors:
                return by_id_hit, []
        return None, errors

    if manager_id:
        found = by_id.get(manager_id)
        if found is None:
            return None, [_error(row, f"manager_id '{manager_id}' was not found")]
        return found, []

    found = by_email.get(manager_email)
    if found is None:
        return None, [_error(row, f"manager_email '{manager_email}' was not found")]
    return found, []


def _direct_report_counts(manager_of, by_id):
    counts = Counter(manager_of.values())
    managers = [(by_id[employee_id], count) for employee_id, count in counts.items()]
    managers.sort(key=lambda item: (-item[1], item[0]["employee_id"]))
    return managers


def _cycle_members(manager_of):
    """People who sit on a reporting loop, not people who only report into one.

    Each accepted employee has at most one manager, so the graph is a
    collection of chains into a root, or chains into a cycle. Walking each
    chain once is enough: a node is cyclic only if it appears twice on the
    same walk.
    """
    processed = set()
    on_cycle = set()

    for start in manager_of:
        if start in processed:
            continue

        path = []
        index_on_path = {}
        current = start

        while current is not None:
            if current in index_on_path:
                on_cycle.update(path[index_on_path[current] :])
                break
            if current in processed:
                break
            index_on_path[current] = len(path)
            path.append(current)
            current = manager_of.get(current)

        processed.update(path)

    return on_cycle


def _error(row, message):
    return {
        "source_row": row["source_row"],
        "employee_id": row["employee_id"],
        "message": message,
    }
