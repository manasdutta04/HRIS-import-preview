# HRIS import preview

Small Django app for the Diversio Engineer I exercise. Client Success can upload an HRIS CSV and see whether the file is usable before anything is written to the platform. Nothing is saved to a database.

## Setup

Python 3.11+ (I ran this on 3.13). From the repo root:

```
python -m venv .venv
```

Activate the venv, then:

```
pip install -r requirements.txt
python manage.py runserver
```

Open http://127.0.0.1:8000/ and upload `sample_hris.csv` from this folder.

## Tests

```
python manage.py test preview
```

The tests hit `parse_hris_csv` and `analyze` directly. They do not drive a browser.

## How the preview is built

1. `preview/services/parse.py` reads UTF-8 CSV (with or without a BOM), trims fields, and lowercases emails. `employee_id` stays case-sensitive. Quoted names such as `Alvarez, Renée` are kept as one value.
2. `preview/services/analyze.py` does identity checks first. Missing or duplicated IDs/emails drop those rows from analysis. Manager lookup only sees accepted rows.
3. Manager resolution follows the spec: both fields blank is a root; one field is a lookup; both fields must point at the same person. A manager error keeps the employee but does not create a relationship and does not make them a root.
4. Each person has at most one manager, so the reporting graph is chains into a root or chains into a cycle. Cycle members are people who appear twice on the same walk. Someone who only reports into a cycle is not marked cyclic.

Time and space are both linear in the number of rows. For ~100,000 employees that is a few dicts in memory, which is fine for a preview. I did not stream the file because we need the whole set to resolve managers who appear later than their reports.

## Assumptions and limits

- Source row 1 is the header. The first employee is source row 2.
- Completely blank CSV records are skipped and do not count toward the source row total.
- Extra columns are ignored.
- Duplicate identity rows are all invalid, not just the second one.
- If `manager_id` points at a row that failed identity checks, that is a "not found" manager error.
- The UI is a single page. No login, no persistence, no deploy.

## Time spent

About 70 minutes on the implementation, not counting the walkthrough recording.

## AI tools

I used Cursor while building this. It helped with the Django project layout and the HTML page. I wrote and checked the parse/analyze rules myself against the sample file.

I accepted help on the upload view boilerplate. I changed the cycle detection: an early suggestion used a generic graph SCC approach, which is heavier than this problem needs, since each employee has at most one manager. I rejected adding database models. The exercise asks for a preview before any employee data is written, and persistence would have hidden mistakes instead of making the logic easier to test.
