# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess

from omnibus import InterconnectBuilder

from tests.filediff import filediff


class TestCorrect:
    """
    Provides generic _test interface for positive tests

    Requires specification of _process(self, ic) which perform processing on interconnect and prints to file

    Requires variable 'directory' to provide directory for golden file
    """

    def _test(self, name, path=None):
        ic = InterconnectBuilder(frontend="yaml")

        ic.read_yaml(f"examples/{name}.yml" if not path else path)

        ic._print_set_output("tests/output.txt")

        self._process(ic)

        assert not filediff(
            "tests/output.txt", f"tests/ideal/process/{self.directory}/{name}.txt"
        )


class TestIncorrect:
    """
    Provides generic _test interface for negative tests

    Requires specification of _process(self, ic) which perform processing on interconnect
    """

    def _test(self, name, err=[], warn=[]):
        ic = InterconnectBuilder(frontend="yaml")

        ic.read_yaml(f"tests/interconnectinvalid/{name}.yml")

        assert len(ic.errors) == 0
        assert len(ic.warns) == 0

        self._process(ic)

        if type(err) is str:
            err = [err]
        assert ic.errors == err

        if type(warn) is str:
            warn = [warn]
        assert ic.warns == warn
