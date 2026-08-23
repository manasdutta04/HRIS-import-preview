from django.shortcuts import render

from preview.services.analyze import analyze
from preview.services.parse import ParseError, parse_hris_csv


def index(request):
    context = {"result": None, "error": None, "filename": ""}

    if request.method != "POST":
        return render(request, "preview/index.html", context)

    upload = request.FILES.get("hris_file")
    if not upload:
        context["error"] = "Please choose a CSV file."
        return render(request, "preview/index.html", context)

    context["filename"] = upload.name
    try:
        rows = parse_hris_csv(upload)
        context["result"] = analyze(rows)
    except ParseError as exc:
        context["error"] = str(exc)

    return render(request, "preview/index.html", context)
