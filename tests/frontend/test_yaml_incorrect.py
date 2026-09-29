# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess

from omnibus import InterconnectBuilder


# These tests check whether yaml frontend reports errors
class TestYaml:
    def _test(self, name, errors=[], warns=[], backend="topwrap_pulpplatform"):
        ic = InterconnectBuilder(frontend="yaml", backend=backend)

        ic.read_yaml(f"tests/specinvalid/{name}.yml")

        if type(errors) == str:
            assert len(ic.errors) == 1
            assert errors == ic.errors[0]
        else:
            assert errors == ic.errors

        if type(warns) == str:
            assert len(ic.warns) == 1
            assert warns == ic.warns[0]
        else:
            assert warns == ic.warns

    def test_nofile(self):
        self._test(
            "this_file_will_never_exist",
            "ERROR: file 'tests/specinvalid/this_file_will_never_exist.yml' does not exist or is not readable",
        )

    def test_yaml_structure(self):
        self._test(
            "yaml_duplicate",
            [
                "ERROR: invalid yaml provided",
                'found duplicate key "desc_version" with value "1.2" (original value: "1.0")',
                '  in "tests/specinvalid/yaml_duplicate.yml", line 5, column 1',
            ],
        )
        self._test(
            "yaml_indentation",
            [
                "ERROR: invalid yaml provided",
                "mapping values are not allowed here",
                '  in "tests/specinvalid/yaml_indentation.yml", line 8, column 15',
            ],
        )

    def test_desc_version(self):
        self._test(
            "desc_version_arr",
            [
                "tests/specinvalid/desc_version_arr.yml: ERROR: in top level, 'ports' is a required property",
                "tests/specinvalid/desc_version_arr.yml: ERROR: in top level, 'address_map' is a required property",
                "tests/specinvalid/desc_version_arr.yml:4:1: ERROR: in 'desc_version', 1.0 was expected",
            ],
        )
        self._test(
            "desc_version_dict",
            [
                "tests/specinvalid/desc_version_dict.yml: ERROR: in top level, 'ports' is a required property",
                "tests/specinvalid/desc_version_dict.yml: ERROR: in top level, 'address_map' is a required property",
                "tests/specinvalid/desc_version_dict.yml:4:1: ERROR: in 'desc_version', 1.0 was expected",
            ],
        )
        self._test(
            "desc_version_no",
            [
                "tests/specinvalid/desc_version_no.yml: ERROR: in top level, 'desc_version' is a required property",
                "tests/specinvalid/desc_version_no.yml: ERROR: in top level, 'ports' is a required property",
                "tests/specinvalid/desc_version_no.yml: ERROR: in top level, 'address_map' is a required property",
            ],
        )
        self._test(
            "desc_version_null",
            [
                "tests/specinvalid/desc_version_null.yml: ERROR: in top level, 'ports' is a required property",
                "tests/specinvalid/desc_version_null.yml: ERROR: in top level, 'address_map' is a required property",
                "tests/specinvalid/desc_version_null.yml:4:1: ERROR: in 'desc_version', 1.0 was expected",
            ],
        )

    def test_version(self):
        self._test(
            "version_arr",
            "tests/specinvalid/version_arr.yml:6:1: ERROR: in 'version', expected an integer or a string, got a list ([1, 3])",
        )
        self._test(
            "version_dict",
            "tests/specinvalid/version_dict.yml:6:1: ERROR: in 'version', expected an integer or a string, got a mapping ({a: 1, b: 3})",
        )
        self._test(
            "version_null",
            "tests/specinvalid/version_null.yml:6:1: ERROR: in 'version', expected an integer or a string, got nothing",
        )

    def test_name(self):
        self._test(
            "name_arr",
            "tests/specinvalid/name_arr.yml:6:1: ERROR: in 'name', expected a string, got a list ([3, 4])",
        )
        self._test(
            "name_dict",
            "tests/specinvalid/name_dict.yml:6:1: ERROR: in 'name', expected a string, got a mapping ({a: 3, b: 4})",
        )
        self._test(
            "name_null",
            "tests/specinvalid/name_null.yml:6:1: ERROR: in 'name', expected a string, got nothing",
        )
        self._test(
            "name_int",
            "tests/specinvalid/name_int.yml:6:1: ERROR: in 'name', expected a string, got an integer (3)",
        )
        self._test(
            "name_empty",
            "tests/specinvalid/name_empty.yml:5:1: ERROR: in 'name', must not be empty",
        )

    def test_global(self):
        self._test(
            "global_arr",
            "tests/specinvalid/global_arr.yml:6:1: ERROR: in 'global', expected a mapping or nothing, got a list ([3, 4])",
        )
        self._test(
            "global_int",
            "tests/specinvalid/global_int.yml:6:1: ERROR: in 'global', expected a mapping or nothing, got an integer (3)",
        )

    def test_global_unkown(self):
        self._test(
            "global_missing_field",
            warns="WARNING: 'this_field_must_never_and_will_never_exist' not in the list of known globals",
        )

    def test_global_addr_width(self):
        self._test(
            "global_addr_width_arr",
            "tests/specinvalid/global_addr_width_arr.yml:7:3: ERROR: in 'global.addr_width', expected an integer, got a list ([3, 4])",
        )
        self._test(
            "global_addr_width_dict",
            "tests/specinvalid/global_addr_width_dict.yml:7:3: ERROR: in 'global.addr_width', expected an integer, got a mapping ({a: 3, b: 4})",
        )
        self._test(
            "global_addr_width_null",
            "tests/specinvalid/global_addr_width_null.yml:7:3: ERROR: in 'global.addr_width', expected an integer, got nothing",
        )
        self._test(
            "global_addr_width_str",
            "tests/specinvalid/global_addr_width_str.yml:7:3: ERROR: in 'global.addr_width', expected an integer, got a string ('13')",
        )
        self._test(
            "global_addr_width_zero",
            "tests/specinvalid/global_addr_width_zero.yml:7:3: ERROR: in 'global.addr_width', 0 is less than the minimum of 1",
        )

    def test_default(self):
        self._test(
            "default_arr",
            "tests/specinvalid/default_arr.yml:6:1: ERROR: in 'default', expected a mapping or nothing, got a list ([3, 4])",
        )
        self._test(
            "default_int",
            "tests/specinvalid/default_int.yml:6:1: ERROR: in 'default', expected a mapping or nothing, got an integer (3)",
        )

    def test_default_unkown(self):
        self._test(
            "default_missing_field",
            warns="WARNING: 'this_field_must_never_and_will_never_exist' not in the list of known defaults",
        )

    # backend parameters are validated by the backend's schema extension, and only
    # with that backend; others report them as unknown
    def test_default_backend_param(self):
        self._test(
            "backend_param",
            "tests/specinvalid/backend_param.yml:12:3: ERROR: in 'default.axi_max_reads', 0 is less than the minimum of 1",
        )
        self._test(
            "backend_param",
            warns="WARNING: 'axi_max_reads' not in the list of known defaults",
            backend="graphviz",
        )

    def test_default_data_width(self):
        self._test(
            "default_data_width_arr",
            "tests/specinvalid/default_data_width_arr.yml:7:3: ERROR: in 'default.data_width', expected an integer, got a list ([3, 4])",
        )
        self._test(
            "default_data_width_dict",
            "tests/specinvalid/default_data_width_dict.yml:7:3: ERROR: in 'default.data_width', expected an integer, got a mapping ({a: 3, b: 4})",
        )
        self._test(
            "default_data_width_null",
            "tests/specinvalid/default_data_width_null.yml:7:3: ERROR: in 'default.data_width', expected an integer, got nothing",
        )
        self._test(
            "default_data_width_str",
            "tests/specinvalid/default_data_width_str.yml:7:3: ERROR: in 'default.data_width', expected an integer, got a string ('13')",
        )
        self._test(
            "default_data_width_zero",
            "tests/specinvalid/default_data_width_zero.yml:7:3: ERROR: in 'default.data_width', 0 is less than the minimum of 1",
        )

    def test_default_protocol(self):
        self._test(
            "default_protocol_arr",
            "tests/specinvalid/default_protocol_arr.yml:7:3: ERROR: in 'default.protocol', expected a string, got a list ([3, 4])",
        )
        self._test(
            "default_protocol_dict",
            "tests/specinvalid/default_protocol_dict.yml:7:3: ERROR: in 'default.protocol', expected a string, got a mapping ({a: 3, b: 4})",
        )
        self._test(
            "default_protocol_null",
            "tests/specinvalid/default_protocol_null.yml:7:3: ERROR: in 'default.protocol', expected a string, got nothing",
        )
        self._test(
            "default_protocol_int",
            "tests/specinvalid/default_protocol_int.yml:7:3: ERROR: in 'default.protocol', expected a string, got an integer (13)",
        )
        self._test(
            "default_protocol_unknown",
            "tests/specinvalid/default_protocol_unknown.yml:7:3: ERROR: in 'default.protocol', invalid protocol 'aix', expected one of [axi4, ahb3, apb3, axi4lite]",
        )

    def test_default_clock(self):
        self._test(
            "default_clock_arr",
            "tests/specinvalid/default_clock_arr.yml:7:3: ERROR: in 'default.clock', expected a string, got a list ([3, 4])",
        )
        self._test(
            "default_clock_dict",
            "tests/specinvalid/default_clock_dict.yml:7:3: ERROR: in 'default.clock', expected a string, got a mapping ({a: 3, b: 4})",
        )
        self._test(
            "default_clock_null",
            "tests/specinvalid/default_clock_null.yml:7:3: ERROR: in 'default.clock', expected a string, got nothing",
        )
        self._test(
            "default_clock_int",
            "tests/specinvalid/default_clock_int.yml:7:3: ERROR: in 'default.clock', expected a string, got an integer (3)",
        )
        self._test(
            "default_clock_empty",
            "tests/specinvalid/default_clock_empty.yml:9:3: ERROR: in 'default.clock', must not be empty",
        )

    def test_default_frequency(self):
        self._test(
            "default_frequency_arr",
            "tests/specinvalid/default_frequency_arr.yml:7:3: ERROR: in 'default.frequency', expected a number or a string, got a list ([3, 4])",
        )
        self._test(
            "default_frequency_dict",
            "tests/specinvalid/default_frequency_dict.yml:7:3: ERROR: in 'default.frequency', expected a number or a string, got a mapping ({a: 3, b: 4})",
        )
        self._test(
            "default_frequency_null",
            "tests/specinvalid/default_frequency_null.yml:7:3: ERROR: in 'default.frequency', expected a number or a string, got nothing",
        )
        self._test(
            "default_frequency_str_empty",
            "tests/specinvalid/default_frequency_str_empty.yml:7:3: ERROR: in 'default.frequency', invalid frequency '', must be a positive number, or a positive integer with an optional Hz/k/kHz/M/MHz/G/GHz suffix, or 'n/a'",
        )
        self._test(
            "default_frequency_str",
            "tests/specinvalid/default_frequency_str.yml:7:3: ERROR: in 'default.frequency', invalid frequency '13X', must be a positive number, or a positive integer with an optional Hz/k/kHz/M/MHz/G/GHz suffix, or 'n/a'",
        )

    def test_clocks_field(self):
        self._test(
            "clocks_arr",
            "tests/specinvalid/clocks_arr.yml:6:1: ERROR: in 'clocks', expected a mapping, got a list ([3, 4])",
        )
        self._test(
            "clocks_int",
            "tests/specinvalid/clocks_int.yml:6:1: ERROR: in 'clocks', expected a mapping, got an integer (3)",
        )
        self._test(
            "clocks_empty",
            "tests/specinvalid/clocks_empty.yml:6:1: ERROR: in 'clocks', expected at least 1 entry, got none",
        )

    def test_clocks_err(self):
        self._test(
            "clocks_errors",
            [
                "tests/specinvalid/clocks_errors.yml:13:3: ERROR: in 'clocks', clock name must not be empty",
                "tests/specinvalid/clocks_errors.yml:16:5: ERROR: in 'clocks.a.frequency', invalid frequency '0', must be a positive number, or a positive integer with an optional Hz/k/kHz/M/MHz/G/GHz suffix, or 'n/a'",
                "tests/specinvalid/clocks_errors.yml:19:5: ERROR: in 'clocks.b.frequency', invalid frequency '-3', must be a positive number, or a positive integer with an optional Hz/k/kHz/M/MHz/G/GHz suffix, or 'n/a'",
                "tests/specinvalid/clocks_errors.yml:22:5: ERROR: in 'clocks.c.frequency', invalid frequency 'str', must be a positive number, or a positive integer with an optional Hz/k/kHz/M/MHz/G/GHz suffix, or 'n/a'",
                "tests/specinvalid/clocks_errors.yml:25:5: ERROR: in 'clocks.d.frequency', invalid frequency '3e8MHz', must be a positive number, or a positive integer with an optional Hz/k/kHz/M/MHz/G/GHz suffix, or 'n/a'",
                "tests/specinvalid/clocks_errors.yml:28:5: ERROR: in 'clocks.e.frequency', expected a number, a string or nothing, got a list ([3, 4])",
                "tests/specinvalid/clocks_errors.yml:33:5: ERROR: in 'clocks.f.frequency', expected a number, a string or nothing, got a mapping ({a: 3, b: 4})",
            ],
        )

    # passes the schema, so the checks after it run: default clock that isn't in 'clocks'
    def test_default_clock_missing(self):
        self._test(
            "default_clock_missing",
            "ERROR: default clock provided ('clk'), but no such entry in 'clocks'",
        )

    def test_clocks_warn(self):
        self._test(
            "clocks_warns",
            warns="WARNING: clock 'clk' has no assigned frequency and no default was provided, defaulting to 'n/a', features depending on clock frequency will be unavailable",
        )

    def test_ports_field(self):
        self._test(
            "ports_arr",
            "tests/specinvalid/ports_arr.yml:12:1: ERROR: in 'ports', expected a mapping, got a list ([1, 2])",
        )
        self._test(
            "ports_int",
            "tests/specinvalid/ports_int.yml:12:1: ERROR: in 'ports', expected a mapping, got an integer (1)",
        )
        self._test(
            "ports_null",
            "tests/specinvalid/ports_null.yml:12:1: ERROR: in 'ports', expected a mapping, got nothing",
        )
        self._test(
            "ports_lack",
            "tests/specinvalid/ports_lack.yml: ERROR: in top level, 'ports' is a required property",
        )

    def test_ports_err(self):
        self._test(
            "ports_errors",
            [
                "tests/specinvalid/ports_errors.yml:11:3: ERROR: in 'ports.a', expected a mapping, got nothing",
                "tests/specinvalid/ports_errors.yml:13:3: ERROR: in 'ports.b', expected a mapping, got a list ([1, 2])",
                "tests/specinvalid/ports_errors.yml:17:3: ERROR: in 'ports.c', expected a mapping, got an integer (1)",
                "tests/specinvalid/ports_errors.yml:19:3: ERROR: in 'ports.d', expected a mapping, got nothing",
                "tests/specinvalid/ports_errors.yml:24:5: ERROR: in 'ports.e.clock', expected a string, got an integer (12)",
                "tests/specinvalid/ports_errors.yml:25:5: ERROR: in 'ports.e.data_width', expected an integer, got a string ('asd')",
                "tests/specinvalid/ports_errors.yml:23:5: ERROR: in 'ports.e.protocol', invalid protocol 'AXI4Liter', did you mean 'axi4lite'?, expected one of [axi4, ahb3, apb3, axi4lite]",
                "tests/specinvalid/ports_errors.yml:22:5: ERROR: in 'ports.e.role', 'both' is not one of ['subordinate', 'manager']",
                "tests/specinvalid/ports_errors.yml:32:5: ERROR: in 'ports.f', unknown field 'unknown_field', allowed ones are ['clock', 'data_width', 'protocol', 'role']",
            ],
        )
        self._test(
            "ports_single",
            [
                "tests/specinvalid/ports_single.yml:9:1: ERROR: in 'ports', expected at least 2 entries, got 1 ('a')",
                "tests/specinvalid/ports_single.yml:9:1: ERROR: in 'ports', at least one subordinate port must be provided",
            ],
        )
        self._test(
            "ports_nomanager",
            "tests/specinvalid/ports_nomanager.yml:9:1: ERROR: in 'ports', at least one manager port must be provided",
        )
        self._test(
            "ports_nosubordinate",
            "tests/specinvalid/ports_nosubordinate.yml:9:1: ERROR: in 'ports', at least one subordinate port must be provided",
        )
        self._test(
            "ports_clock_empty",
            "tests/specinvalid/ports_clock_empty.yml:14:5: ERROR: in 'ports.a.clock', must not be empty",
        )

    # passes the schema, so the checks after it run: ports that can't be completed: no values and no defaults
    def test_ports_no_default(self):
        self._test(
            "ports_no_default",
            [
                "ERROR: top level port 'a' parameter 'clock' has no value and no default was provided",
                "ERROR: top level port 'a' parameter 'protocol' has no value and no default was provided",
                "ERROR: top level port 'a' parameter 'data_width' has no value and no default was provided",
                "ERROR: top level port 'b' parameter 'clock' has no value and no default was provided",
                "ERROR: top level port 'b' parameter 'protocol' has no value and no default was provided",
                "ERROR: top level port 'b' parameter 'data_width' has no value and no default was provided"
            ],
            warns="WARNING: clock 'clock' has no assigned frequency and no default was provided, defaulting to 'n/a', features depending on clock frequency will be unavailable",
        )

    def test_crossbars_field(self):
        self._test(
            "crossbars_arr",
            [
                "tests/specinvalid/crossbars_arr.yml:24:1: ERROR: in top level, 'connections' is a dependency of 'crossbars'",
                "tests/specinvalid/crossbars_arr.yml:24:1: ERROR: in 'crossbars', expected a mapping, got a list ([1, 2])",
            ],
        )
        self._test(
            "crossbars_int",
            [
                "tests/specinvalid/crossbars_int.yml:24:1: ERROR: in top level, 'connections' is a dependency of 'crossbars'",
                "tests/specinvalid/crossbars_int.yml:24:1: ERROR: in 'crossbars', expected a mapping, got an integer (1)",
            ],
        )
        self._test(
            "crossbars_null",
            [
                "tests/specinvalid/crossbars_null.yml:24:1: ERROR: in top level, 'connections' is a dependency of 'crossbars'",
                "tests/specinvalid/crossbars_null.yml:24:1: ERROR: in 'crossbars', expected a mapping, got nothing",
            ],
        )

    def test_crossbars_err(self):
        self._test(
            "crossbars_err",
            [
                "tests/specinvalid/crossbars_err.yml:24:1: ERROR: in top level, 'connections' is a dependency of 'crossbars'",
                "tests/specinvalid/crossbars_err.yml:26:3: ERROR: in 'crossbars.a', expected a mapping, got nothing",
                "tests/specinvalid/crossbars_err.yml:29:5: ERROR: in 'crossbars.b.ports', expected a mapping, got a list ([1, 2])",
                "tests/specinvalid/crossbars_err.yml:34:5: ERROR: in 'crossbars.c.ports', expected at least 2 entries, got 1 ('ca')",
                "tests/specinvalid/crossbars_err.yml:34:5: ERROR: in 'crossbars.c.ports', at least one manager port must be provided",
                "tests/specinvalid/crossbars_err.yml:39:5: ERROR: in 'crossbars.d.ports', expected at least 2 entries, got 1 ('da')",
                "tests/specinvalid/crossbars_err.yml:39:5: ERROR: in 'crossbars.d.ports', at least one subordinate port must be provided",
                "tests/specinvalid/crossbars_err.yml:49:5: ERROR: in 'crossbars.e', unknown field 'thisfieldmustnotexist', allowed ones are ['clock', 'ports']",
                "tests/specinvalid/crossbars_err.yml:44:5: ERROR: in 'crossbars.e.ports', at least one subordinate port must be provided",
                "tests/specinvalid/crossbars_err.yml:52:5: ERROR: in 'crossbars.f.ports', at least one subordinate port must be provided",
                "tests/specinvalid/crossbars_err.yml:55:9: ERROR: in 'crossbars.f.ports.fa', unknown field 'protocol', allowed ones are ['role']",
                "tests/specinvalid/crossbars_err.yml:58:9: ERROR: in 'crossbars.f.ports.fb', unknown field 'clock', allowed ones are ['role']",
            ],
        )
        self._test(
            "crossbars_clock_empty",
            "tests/specinvalid/crossbars_clock_empty.yml:24:5: ERROR: in 'crossbars.main.clock', must not be empty",
        )

    def test_connections_field(self):
        self._test(
            "connections_arr",
            "tests/specinvalid/connections_arr.yml:32:1: ERROR: in 'connections', expected a mapping, got a list ([1, 2])",
        )
        self._test(
            "connections_int",
            "tests/specinvalid/connections_int.yml:32:1: ERROR: in 'connections', expected a mapping, got an integer (1)",
        )
        self._test(
            "connections_null",
            "tests/specinvalid/connections_null.yml:32:1: ERROR: in 'connections', expected a mapping, got nothing",
        )

    def test_connections_err(self):
        self._test(
            "connections_err",
            [
                "tests/specinvalid/connections_err.yml:36:3: ERROR: in 'connections', invalid connection '', expected format 'a -> b'",
                "tests/specinvalid/connections_err.yml:38:3: ERROR: in 'connections', invalid connection 'a b', expected format 'a -> b'",
                "tests/specinvalid/connections_err.yml:46:3: ERROR: in 'connections.a -> b', expected a mapping or nothing, got a list ([1, 2])",
            ],
        )

    # passes the schema, so the checks after it run: connections to nonexistent ports, unknown parameter
    def test_connections_ref(self):
        self._test(
            "connections_ref_err",
            [
                "ERROR: cannot connect 'f' to 'b', 'f' does not exist",
                "ERROR: cannot connect 'a' to 'f', 'f' does not exist",
            ],
            warns="WARNING: while connecting 'a' to 'c', unknown parameter 'unknown'",
        )

    # passes the schema, so the checks after it run: a top level port without a connection
    def test_connections_insufficient(self):
        self._test(
            "connections_insufficient",
            "ERROR: insufficient number of connections, each top level port must include connection",
        )

    def test_address_map_field(self):
        self._test(
            "address_map_arr",
            "tests/specinvalid/address_map_arr.yml:18:1: ERROR: in 'address_map', expected a mapping, got a list ([1, 2])",
        )
        self._test(
            "address_map_int",
            "tests/specinvalid/address_map_int.yml:18:1: ERROR: in 'address_map', expected a mapping, got an integer (1)",
        )
        self._test(
            "address_map_null",
            "tests/specinvalid/address_map_null.yml:18:1: ERROR: in 'address_map', expected a mapping, got nothing",
        )

    def test_address_map_err(self):
        self._test(
            "address_map_err",
            [
                "tests/specinvalid/address_map_err.yml:25:3: ERROR: in 'address_map.a', expected a mapping, got nothing",
                "tests/specinvalid/address_map_err.yml:28:5: ERROR: in 'address_map.b.to', expected a string, got an integer (11)",
                "tests/specinvalid/address_map_err.yml:33:5: ERROR: in 'address_map.c.from', expected a string or a list, got an integer (11)",
                "tests/specinvalid/address_map_err.yml:39:5: ERROR: in 'address_map.d.from', must be a port name or a list of port names",
                "tests/specinvalid/address_map_err.yml:46:5: ERROR: in 'address_map.e.base', expected an integer, got a string ('str')",
                "tests/specinvalid/address_map_err.yml:52:5: ERROR: in 'address_map.f.size', expected an integer, got a string ('str')",
            ],
        )

    # passes the schema, so the checks after it run: nonexistent source/destination ports, range beyond addr_width
    def test_address_map_ref(self):
        self._test(
            "address_map_ref_err",
            [
                "ERROR: in 'address_map' entry 'g', 'e' is not a valid source port, must be a subordinate top level port",
                "ERROR: in 'address_map' entry 'h', 'i' is not a valid destination port, must be a manager top level port",
                "ERROR: in 'address_map' entry 'i', end address exceeds available range, end address is 1199999999 while range ends at 15",
            ],
        )

    def test_connections_data_width(self):
        self._test(
            "connections_data_width_err",
            [
                "tests/specinvalid/connections_data_width_err.yml:40:5: ERROR: in 'connections.a -> b.data_width', expected an integer, got a boolean (false)",
                "tests/specinvalid/connections_data_width_err.yml:42:5: ERROR: in 'connections.a -> c.data_width', expected an integer, got a list ([1, 2])",
                "tests/specinvalid/connections_data_width_err.yml:46:5: ERROR: in 'connections.a -> d.data_width', expected an integer, got a string ('str')",
                "tests/specinvalid/connections_data_width_err.yml:48:5: ERROR: in 'connections.a -> e.data_width', -3 is less than the minimum of 1",
            ],
        )

    def test_connections_protocol(self):
        self._test(
            "connections_protocol_err",
            [
                "tests/specinvalid/connections_protocol_err.yml:38:5: ERROR: in 'connections.a -> b.protocol', expected true or false, got an integer (3)",
                "tests/specinvalid/connections_protocol_err.yml:40:5: ERROR: in 'connections.a -> c.protocol', expected true or false, got a list ([1, 2])",
                "tests/specinvalid/connections_protocol_err.yml:44:5: ERROR: in 'connections.a -> d.protocol', expected true or false, got a string ('str')",
            ],
        )

    def test_connections_axi_max_reads(self):
        self._test(
            "connections_axi_max_reads_err",
            [
                "tests/specinvalid/connections_axi_max_reads_err.yml:40:5: ERROR: in 'connections.a -> b.axi_max_reads', expected an integer, got a boolean (false)",
                "tests/specinvalid/connections_axi_max_reads_err.yml:42:5: ERROR: in 'connections.a -> c.axi_max_reads', expected an integer, got a list ([1, 2])",
                "tests/specinvalid/connections_axi_max_reads_err.yml:46:5: ERROR: in 'connections.a -> d.axi_max_reads', expected an integer, got a string ('str')",
                "tests/specinvalid/connections_axi_max_reads_err.yml:48:5: ERROR: in 'connections.a -> e.axi_max_reads', -3 is less than the minimum of 1",
            ],
        )

    def test_connections_cdc(self):
        self._test(
            "connections_cdc_err",
            [
                "tests/specinvalid/connections_cdc_err.yml:38:5: ERROR: in 'connections.a -> b.cdc', expected true or false, got an integer (3)",
                "tests/specinvalid/connections_cdc_err.yml:40:5: ERROR: in 'connections.a -> c.cdc', expected true or false, got a list ([1, 2])",
                "tests/specinvalid/connections_cdc_err.yml:44:5: ERROR: in 'connections.a -> d.cdc', expected true or false, got a string ('str')",
            ],
        )

    def test_connections_registers(self):
        self._test(
            "connections_registers_err",
            [
                "tests/specinvalid/connections_registers_err.yml:40:5: ERROR: in 'connections.a -> b.registers', expected an integer, got a boolean (false)",
                "tests/specinvalid/connections_registers_err.yml:42:5: ERROR: in 'connections.a -> c.registers', expected an integer, got a list ([1, 2])",
                "tests/specinvalid/connections_registers_err.yml:46:5: ERROR: in 'connections.a -> d.registers', expected an integer, got a string ('str')",
                "tests/specinvalid/connections_registers_err.yml:48:5: ERROR: in 'connections.a -> e.registers', -3 is less than the minimum of 1",
            ],
        )

    def test_hints(self):
        self._test(
            "hints_top_level",
            [
                "tests/specinvalid/hints_top_level.yml: ERROR: in top level, 'ports' is a required property",
                "tests/specinvalid/hints_top_level.yml: ERROR: in top level, 'address_map' is a required property",
                "tests/specinvalid/hints_top_level.yml:12:1: ERROR: in top level, unknown field 'prots', did you mean 'ports'?, allowed ones are ['address_map', 'clocks', 'connections', 'crossbars', 'default', 'desc_version', 'global', 'name', 'ports', 'version']",
                "tests/specinvalid/hints_top_level.yml:18:1: ERROR: in top level, unknown field 'adress_map', did you mean 'address_map'?, allowed ones are ['address_map', 'clocks', 'connections', 'crossbars', 'default', 'desc_version', 'global', 'name', 'ports', 'version']",
            ],
        )
        self._test(
            "hints_nested",
            [
                "tests/specinvalid/hints_nested.yml:33:3: ERROR: in 'address_map.b', 'base' is a required property",
                "tests/specinvalid/hints_nested.yml:35:5: ERROR: in 'address_map.b', unknown field 'bse', did you mean 'base'?, allowed ones are ['base', 'from', 'size', 'to']",
                "tests/specinvalid/hints_nested.yml:21:5: ERROR: in 'crossbars.main', unknown field 'clocks', did you mean 'clock'?, allowed ones are ['clock', 'ports']",
                "tests/specinvalid/hints_nested.yml:25:7: ERROR: in 'crossbars.main.ports.b', 'role' is a required property",
                "tests/specinvalid/hints_nested.yml:26:9: ERROR: in 'crossbars.main.ports.b', unknown field 'rol', did you mean 'role'?, allowed ones are ['role']",
                "tests/specinvalid/hints_nested.yml:15:5: ERROR: in 'ports.a', unknown field 'datawidth', did you mean 'data_width'?, allowed ones are ['clock', 'data_width', 'protocol', 'role']",
            ],
        )
