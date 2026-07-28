# -*- coding: utf-8 -*-
try:
    import docx
    import docxtpl
except ImportError as error:
    raise ImportError(
        f"Required Python dependencies 'docxtpl' and 'python-docx' are missing: {error}. "
        "Please ensure docxtpl==0.20.2 and python-docx==1.2.0 are installed."
    ) from error

from . import controllers
from . import models
