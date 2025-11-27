import os


def enable_skip_external():
    os.environ["DOC_ANALYSIS_SKIP_EXTERNAL"] = "1"


def disable_skip_external():
    os.environ.pop("DOC_ANALYSIS_SKIP_EXTERNAL", None)
