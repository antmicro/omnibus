# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess


# These tests check whether code quality satisfies some standard
class TestLint:
    def test_codespell(self):
        assert 0 == subprocess.call(
            "codespell omnibus/*py omnibus/*/*py", shell=True
        )

    def test_ruff(self):
        assert 0 == subprocess.call(
            "ruff check omnibus/*py omnibus/*/*py", shell=True
        )

    def test_formatruff(self):
        assert 0 == subprocess.call(
            "ruff format --check omnibus/*py omnibus/*/*py", shell=True
        )
