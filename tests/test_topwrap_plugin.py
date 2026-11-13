# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("topwrap")

EXAMPLE = Path(__file__).parent.parent / "examples" / "topwrap"


def generate(tmp_path, file="interconnect.yml", old="", new=""):
    shutil.copytree(
        EXAMPLE, tmp_path, dirs_exist_ok=True, ignore=shutil.ignore_patterns("build")
    )
    edited = tmp_path / file
    edited.write_text(edited.read_text().replace(old, new))
    return subprocess.run(
        [
            Path(sys.executable).parent / "topwrap",
            "generate",
            "--verilog",
            "--fusesoc",
            "design.yaml",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )


def test_generate(tmp_path):
    res = generate(tmp_path)
    assert res.returncode == 0, res.stdout + res.stderr
    src = tmp_path / "build" / "src"
    for f in [
        "omnibus_example.sv",
        "axi_crossbar_main.sv",
        "axi_prconv_axi_axilite.sv",
    ]:
        assert (src / f).is_file()
    assert "pulp-platform.org::axi" in (src / "axi_ic.core").read_text()
    assert (
        "antmicro.com:omnibus:axi_ic:1.0" in (src / "omnibus_example.core").read_text()
    )


@pytest.mark.parametrize(
    "old, new, message",
    [
        (
            "data_width: 32",
            "data_width: 64",
            "DATA_WIDTH is 64 in the interconnect, 32",
        ),
        (
            "    protocol: AXI4Lite\n",
            "",
            "uses protocol axi4, peripheral uses axi4lite",
        ),
        (
            'role: "subordinate"\n',
            'role: "subordinate"\n    protocol: AXI4Lite\n',
            "component 'main' generated with port 'main_from_manager' of protocol 'axi4lite'",
        ),
    ],
)
def test_mismatch_error(tmp_path, old, new, message):
    res = generate(tmp_path, old=old, new=new)
    assert res.returncode != 0
    assert message in res.stdout + res.stderr


def test_mismatch_warning(tmp_path):
    res = generate(
        tmp_path, "sources/manager_axi4.yaml", "ID_WIDTH: '1'", "ID_WIDTH: '2'"
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert (
        "ID_WIDTH is 1 in the interconnect, 2 in the peripheral"
        in res.stdout + res.stderr
    )


def test_options_error(tmp_path):
    res = generate(
        tmp_path, "design.yaml", "spec: interconnect.yml", "spec: missing.yml"
    )
    assert res.returncode != 0
    assert "IP 'axi_ic' (provider 'omnibus'): spec file" in res.stdout + res.stderr
