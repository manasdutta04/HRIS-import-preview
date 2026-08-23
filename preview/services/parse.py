import csv
import io

REQUIRED_COLUMNS = [
    "employee_id",
    "employee_name",
    "email",
    "manager_id",
    "manager_email",
    "department",
]


class ParseError(Exception):
    """Raised when the upload cannot be read as an HRIS CSV."""


def parse_hris_csv(file_obj):
    """Turn an uploaded CSV into a list of normalized row dicts.

    Source row 1 is the header. The first employee is source row 2,
    matching what Client Success would see in a spreadsheet.
    """
    raw = file_obj.read()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")

    if not raw or not raw.strip():
        raise ParseError("The uploaded file is empty.")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseError("The file is not valid UTF-8.") from exc

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise ParseError("The uploaded file is empty.")

    columns = [_clean_header(value) for value in header]
    missing = [name for name in REQUIRED_COLUMNS if name not in columns]
    if missing:
        raise ParseError("Missing required column(s): " + ", ".join(missing))

    index = {name: position for position, name in enumerate(columns)}
    rows = []

    for source_row, values in enumerate(reader, start=2):
        if _is_blank_csv_record(values):
            continue
        rows.append(
            {
                "source_row": source_row,
                "employee_id": _cell(values, index, "employee_id"),
                "employee_name": _cell(values, index, "employee_name"),
                "email": _cell(values, index, "email").lower(),
                "manager_id": _cell(values, index, "manager_id"),
                "manager_email": _cell(values, index, "manager_email").lower(),
                "department": _cell(values, index, "department"),
            }
        )

    return rows


def _clean_header(value):
    return (value or "").strip().lstrip("\ufeff")


def _cell(values, index, column):
    position = index[column]
    if position >= len(values):
        return ""
    return values[position].strip()


def _is_blank_csv_record(values):
    return not values or all(not (value or "").strip() for value in values)
