# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import os


def pytest_sessionstart(session):
    os.makedirs("tests/out/src/", exist_ok=True)
