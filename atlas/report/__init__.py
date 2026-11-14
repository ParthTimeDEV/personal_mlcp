"""PDF and PPTX report built from one run's OutputEnvelope (sachi2.md Part B). Owner: Sachi.

Use from the frontend or a shell:
    from atlas.report import build_report, write_report
    write_report(run_id, "pptx")   # uploads reports/report_<run_id>.pptx, returns the Volume path
    build_report(envelope, "pdf")  # bytes only, for a download button
"""
from atlas.report.build import PersonalDataError, build_report, compute, write_report

__all__ = ["PersonalDataError", "build_report", "compute", "write_report"]
