import io
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from preview.services.analyze import analyze
from preview.services.parse import ParseError, parse_hris_csv

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "sample_hris.csv"


def _row(source_row, employee_id, name, email, manager_id="", manager_email="", department="Eng"):
    return {
        "source_row": source_row,
        "employee_id": employee_id,
        "employee_name": name,
        "email": email,
        "manager_id": manager_id,
        "manager_email": manager_email,
        "department": department,
    }


class ParseTests(SimpleTestCase):
    def test_quoted_name_bom_and_whitespace(self):
        payload = (
            b"\xef\xbb\xbfemployee_id,employee_name,email,manager_id,manager_email,department\n"
            b'DIV-1,"Alvarez, Renee", DEMO.RENEE@DIV.COM ,,,People\n'
        )
        rows = parse_hris_csv(io.BytesIO(payload))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["employee_name"], "Alvarez, Renee")
        self.assertEqual(rows[0]["email"], "demo.renee@div.com")
        self.assertEqual(rows[0]["source_row"], 2)

    def test_missing_columns_raise_a_clear_error(self):
        payload = b"employee_id,email\nDIV-1,a@x.com\n"
        with self.assertRaises(ParseError) as caught:
            parse_hris_csv(io.BytesIO(payload))
        self.assertIn("Missing required column", str(caught.exception))


class AnalyzeTests(SimpleTestCase):
    def test_sample_file_preview(self):
        with SAMPLE_PATH.open("rb") as handle:
            result = analyze(parse_hris_csv(handle))

        self.assertEqual(result["source_row_count"], 25)
        self.assertEqual(len(result["accepted"]), 25)
        self.assertEqual([row["employee_id"] for row in result["roots"]], ["DIV-1001"])

        error_ids = {item["employee_id"] for item in result["errors"]}
        self.assertEqual(error_ids, {"DIV-1600", "DIV-1601"})

        cycle_ids = {row["employee_id"] for row in result["cycle_members"]}
        self.assertEqual(cycle_ids, {"DIV-1701", "DIV-1702", "DIV-1703"})

        counts = {manager["employee_id"]: count for manager, count in result["managers"]}
        self.assertEqual(counts["DIV-1001"], 4)
        self.assertEqual(counts["DIV-1110"], 3)
        self.assertNotIn("DIV-1600", counts)
        self.assertNotIn("DIV-1601", counts)

        hana = next(row for row in result["accepted"] if row["employee_id"] == "DIV-1113")
        self.assertEqual(hana["email"], "demo.hana.patel@diversio.com")

    def test_duplicate_emails_are_both_dropped_from_hierarchy(self):
        rows = [
            _row(2, "A", "Root", "root@x.com"),
            _row(3, "B", "One", "dup@x.com", manager_id="A"),
            _row(4, "C", "Two", "dup@x.com", manager_id="A"),
            _row(5, "D", "Reports to B", "d@x.com", manager_id="B"),
        ]
        result = analyze(rows)

        accepted_ids = {row["employee_id"] for row in result["accepted"]}
        self.assertEqual(accepted_ids, {"A", "D"})
        self.assertEqual(len(result["roots"]), 1)
        self.assertEqual(result["roots"][0]["employee_id"], "A")
        # B is invalid identity, so D's manager lookup fails. D stays accepted, not a root.
        self.assertEqual(result["managers"], [])
        messages = [item["message"] for item in result["errors"]]
        self.assertTrue(any("duplicate email" in message for message in messages))
        self.assertTrue(any("manager_id 'B' was not found" in message for message in messages))

    def test_cycle_does_not_include_people_who_only_report_into_it(self):
        rows = [
            _row(2, "A", "A", "a@x.com", manager_id="B"),
            _row(3, "B", "B", "b@x.com", manager_id="C"),
            _row(4, "C", "C", "c@x.com", manager_id="A"),
            _row(5, "D", "D", "d@x.com", manager_id="A"),
        ]
        result = analyze(rows)
        cycle_ids = {row["employee_id"] for row in result["cycle_members"]}
        self.assertEqual(cycle_ids, {"A", "B", "C"})
        self.assertNotIn("D", cycle_ids)
        counts = {manager["employee_id"]: count for manager, count in result["managers"]}
        self.assertEqual(counts["A"], 2)


class ViewTests(SimpleTestCase):
    def test_sample_upload_renders_the_preview(self):
        upload = SimpleUploadedFile(
            "sample_hris.csv",
            SAMPLE_PATH.read_bytes(),
            content_type="text/csv",
        )
        response = self.client.post("/", {"hris_file": upload})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Avery Morgan")
        self.assertContains(response, "DIV-1600")
        self.assertContains(response, "Alvarez, Ren")
        self.assertContains(response, "Taylor Brooks")

    def test_malformed_upload_shows_a_clear_error(self):
        upload = SimpleUploadedFile("bad.csv", b"foo,bar\n1,2\n", content_type="text/csv")
        response = self.client.post("/", {"hris_file": upload})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Missing required column")
