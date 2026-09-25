# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

from rich.console import Console
from rich.syntax import Syntax
import difflib
from pathlib import Path


def filediff(patha, pathb):
    a = Path(patha).read_text().splitlines()
    b = Path(pathb).read_text().splitlines()

    diff_text = "\n".join(difflib.unified_diff(a, b, "test", "test1"))

    Console().print(Syntax(diff_text, "diff", theme="ansi_dark"))

    return len(diff_text)
