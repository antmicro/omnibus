# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess

from omnibus import InterconnectBuilder


# These tests check whether yaml frontend reports errors
class TestYaml:
    def _test(self, name, errors=[], warns=[]):
        ic = InterconnectBuilder(frontend="yaml")

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
        err = "ERROR: specification version invalid or not provided"
        self._test("desc_version_arr", err)
        self._test("desc_version_dict", err)
        self._test("desc_version_no", err)
        self._test("desc_version_null", err)

    def test_version(self):
        err = "ERROR: invalid version, must be a string of nonzero length or integer"
        self._test("version_arr", err)
        self._test("version_dict", err)
        self._test("version_null", err)

    def test_name(self):
        err = "ERROR: invalid name, must be a string of nonzero length"
        self._test("name_arr", err)
        self._test("name_dict", err)
        self._test("name_null", err)
        self._test("name_int", err)

    def test_global(self):
        err = "ERROR: field 'global' must contain dictionary of globals or be empty"
        self._test("global_arr", err)
        self._test("global_int", err)

    def test_global_unkown(self):
        self._test(
            "global_missing_field",
            warns="WARNING: 'this_field_must_never_and_will_never_exist' not in the list of known globals",
        )

    def test_global_addr_width(self):
        err = "ERROR: in 'global', 'addr_width' takes positive int as an argument"
        self._test("global_addr_width_arr", err)
        self._test("global_addr_width_dict", err)
        self._test("global_addr_width_null", err)
        self._test("global_addr_width_str", err)
        self._test("global_addr_width_zero", err)

    def test_default(self):
        err = "ERROR: field 'default' must contain dictionary of defaults or be empty"
        self._test("default_arr", err)
        self._test("default_int", err)

    def test_default_unkown(self):
        self._test(
            "default_missing_field",
            warns="WARNING: 'this_field_must_never_and_will_never_exist' not in the list of known defaults",
        )

    def test_default_data_width(self):
        err = "ERROR: in 'default', 'data_width' takes positive int as an argument"
        self._test("default_data_width_arr", err)
        self._test("default_data_width_dict", err)
        self._test("default_data_width_null", err)
        self._test("default_data_width_str", err)
        self._test("default_data_width_zero", err)

    def test_default_protocol(self):
        err = "ERROR: in 'default', 'protocol' name must be a string"
        self._test("default_protocol_arr", err)
        self._test("default_protocol_dict", err)
        self._test("default_protocol_null", err)
        self._test("default_protocol_int", err)

        err = "ERROR: in 'default', invalid 'protocol' name, expected one of [axi4, ahb3, apb3, axi4lite]"
        self._test("default_protocol_unknown", err)

    def test_default_clock(self):
        err = "ERROR: in 'default', 'clock' must be a string of nonzero length"
        self._test("default_clock_arr", err)
        self._test("default_clock_dict", err)
        self._test("default_clock_null", err)
        self._test("default_clock_int", err)

    def test_default_frequency(self):
        err = "ERROR: in 'default', invalid 'frequency' value"
        self._test("default_frequency_arr", err)
        self._test("default_frequency_dict", err)
        self._test("default_frequency_null", err)

        err = "ERROR: in 'default', invalid 'frequency' value, cannot be empty string"
        self._test("default_frequency_str_empty", err)

        err = "ERROR: in 'default', invalid 'frequency' suffix, must be one of [Hz, k, kHz, M, MHz, G, GHz]"
        self._test("default_frequency_str", err)

    def test_clocks_field(self):
        err = [
            "ERROR: field 'clocks' must contain dictionary of clocks",
            "ERROR: default clock provided ('clk'), but no such entry in 'clocks'",
        ]
        self._test("clocks_arr", err)
        self._test("clocks_int", err)

        err = [
            "ERROR: at least one clock has to be created",
            "ERROR: default clock provided ('clk'), but no such entry in 'clocks'",
        ]
        self._test("clocks_empty", err)

    def test_clocks_err(self):
        err = [
            "ERROR: clock name must not be empty",
            "ERROR: in clock 'a', invalid 'frequency' value, must be positive",
            "ERROR: in clock 'b', invalid 'frequency' value, must be positive",
            "ERROR: in clock 'c', invalid 'frequency' suffix, must be one of [Hz, k, kHz, M, MHz, G, GHz]",
            "ERROR: in clock 'd', invalid 'frequency' suffix, must be one of [Hz, k, kHz, M, MHz, G, GHz]",
            "ERROR: in clock 'e', invalid 'frequency' value",
            "ERROR: in clock 'f', invalid 'frequency' value",
            "ERROR: default clock provided ('clk'), but no such entry in 'clocks'",
        ]
        self._test("clocks_errors", err)

    def test_clocks_warn(self):
        warn = "WARNING: clock 'clk' has no assigned frequency and no default was provided, defaulting to 'n/a', features depending on clock frequency will be unavailable"
        self._test("clocks_warns", warns=warn)

    def test_ports_field(self):
        err = [
            "ERROR: field 'ports' must contain dictionary of ports",
            "ERROR: at least two valid top level ports must be provided",
            "ERROR: at least one subordinate top level port must be provided",
            "ERROR: at least one manager top level port must be provided",
        ]
        self._test("ports_arr", err)
        self._test("ports_int", err)
        self._test("ports_null", err)

        err = [
            "ERROR: lack of 'ports' field",
            "ERROR: at least two valid top level ports must be provided",
            "ERROR: at least one subordinate top level port must be provided",
            "ERROR: at least one manager top level port must be provided",
        ]
        self._test("ports_lack", err)

    def test_ports_err(self):
        err = [
            "ERROR: top level port 'a' does not have dictionary of attributes",
            "ERROR: top level port 'a' parameter 'clock' has no value and no default was provided",
            "ERROR: top level port 'a' parameter 'protocol' has no value and no default was provided",
            "ERROR: top level port 'a' parameter 'data_width' has no value and no default was provided",
            "ERROR: top level port 'a' 'role' must be 'subordinate' or 'manager', instead found 'none'",
            "ERROR: top level port 'b' does not have dictionary of attributes",
            "ERROR: top level port 'b' parameter 'clock' has no value and no default was provided",
            "ERROR: top level port 'b' parameter 'protocol' has no value and no default was provided",
            "ERROR: top level port 'b' parameter 'data_width' has no value and no default was provided",
            "ERROR: top level port 'b' 'role' must be 'subordinate' or 'manager', instead found 'none'",
            "ERROR: top level port 'c' does not have dictionary of attributes",
            "ERROR: top level port 'c' parameter 'clock' has no value and no default was provided",
            "ERROR: top level port 'c' parameter 'protocol' has no value and no default was provided",
            "ERROR: top level port 'c' parameter 'data_width' has no value and no default was provided",
            "ERROR: top level port 'c' 'role' must be 'subordinate' or 'manager', instead found 'none'",
            "ERROR: top level port 'd' does not have dictionary of attributes",
            "ERROR: top level port 'd' parameter 'clock' has no value and no default was provided",
            "ERROR: top level port 'd' parameter 'protocol' has no value and no default was provided",
            "ERROR: top level port 'd' parameter 'data_width' has no value and no default was provided",
            "ERROR: top level port 'd' 'role' must be 'subordinate' or 'manager', instead found 'none'",
            "ERROR: in top level port 'e', 'clock' must be a string of nonzero length",
            "ERROR: in top level port 'e', invalid 'protocol' name, expected one of [axi4, ahb3, apb3, axi4lite]",
            "ERROR: in top level port 'e', 'data_width' takes positive int as an argument",
            "ERROR: top level port 'e' 'role' must be 'subordinate' or 'manager', instead found 'both'",
            "ERROR: top level port 'f' parameter 'unknown_field' undefined",
            "ERROR: at least two valid top level ports must be provided",
            "ERROR: at least one subordinate top level port must be provided",
        ]
        self._test("ports_errors", err)

        err = [
            "ERROR: at least two valid top level ports must be provided",
            "ERROR: at least one subordinate top level port must be provided",
        ]
        self._test("ports_single", err)

        err = [
            "ERROR: at least one manager top level port must be provided",
        ]
        self._test("ports_nomanager", err)

        err = [
            "ERROR: at least one subordinate top level port must be provided",
        ]
        self._test("ports_nosubordinate", err)

    def test_crossbars_field(self):
        err = [
            "ERROR: 'crossbars' and 'connections' must be both either defined or left for inference",
            "ERROR: field 'crossbars' must contain dictionary of crossbars",
            "ERROR: insufficient number of connections, each top level port must include connection",
        ]
        self._test("crossbars_arr", err)
        self._test("crossbars_int", err)
        self._test("crossbars_null", err)

    def test_crossbars_err(self):
        err = [
            "ERROR: 'crossbars' and 'connections' must be both either defined or left for inference",
            "ERROR: crossbar 'a' does not have dictionary of attributes",
            "ERROR: crossbar 'a' lacks required field 'ports'",
            "ERROR: crossbar 'b' field 'ports' must be a dictionary of ports",
            "ERROR: crossbar 'c' does not have enough valid ports, must be at least 2",
            "ERROR: crossbar 'c' does not have enough valid manager ports, must be at least 1",
            "ERROR: crossbar 'd' does not have enough valid ports, must be at least 2",
            "ERROR: crossbar 'd' does not have enough valid subordinate ports, must be at least 1",
            "ERROR: crossbar 'e' has invalid field 'thisfieldmustnotexist', allowed ones are ['clock', 'ports']",
            "ERROR: in crossbar 'f' port 'f_fa' parameter 'protocol' undefined",
            "ERROR: in crossbar 'f' port 'f_fb' parameter 'clock' undefined",
            "ERROR: crossbar 'f' does not have enough valid ports, must be at least 2",
            "ERROR: crossbar 'f' does not have enough valid subordinate ports, must be at least 1",
            "ERROR: crossbar 'f' does not have enough valid manager ports, must be at least 1",
            "ERROR: insufficient number of connections, each top level port must include connection",
        ]

        self._test("crossbars_err", err)

    def test_connections_field(self):
        err = ["ERROR: field 'connections' must contain dictionary of connections"]
        self._test("connections_arr", err)
        self._test("connections_int", err)
        self._test("connections_null", err)

    def test_connections_err(self):
        err = [
            "ERROR: entry in 'connections' '' invalid: expected format 'a -> b'",
            "ERROR: entry in 'connections' 'a b' invalid: expected format 'a -> b'",
            "ERROR: cannot connect 'f' to 'b', 'f' does not exist",
            "ERROR: cannot connect 'a' to 'f', 'f' does not exist",
            "ERROR: connection 'a -> b' should include dictionary of parameters",
        ]
        warn = [
            "WARNING: while connecting 'a' to 'c', unknown parameter 'unknown'",
        ]

        self._test("connections_err", err, warn)

    def test_address_map_field(self):
        err = ["ERROR: field 'address_map' must contain dictionary of mappings"]
        self._test("address_map_arr", err)
        self._test("address_map_int", err)
        self._test("address_map_null", err)

    def test_address_map_err(self):
        err = [
            "ERROR: 'address_map' entry 'a' should include dictionary of fields",
            "ERROR: 'address_map' entry 'b' does not point to a valid port name - must be a single string",
            "ERROR: 'address_map' entry 'c' does not start from valid ports name, must be either string or list of strings",
            "ERROR: in 'address_map' entry 'd', '11' is not a valid source port, must be a subordinate top level port",
            "ERROR: in 'address_map' entry 'd', '12' is not a valid source port, must be a subordinate top level port",
            "ERROR: 'address_map' entry 'e' 'base' is not an integer",
            "ERROR: 'address_map' entry 'f' 'size' is not an integer",
            "ERROR: in 'address_map' entry 'g', 'e' is not a valid source port, must be a subordinate top level port",
            "ERROR: in 'address_map' entry 'h', 'i' is not a valid destination port, must be a manager top level port",
            "ERROR: in 'address_map' entry 'i', end address exceeds available range, end address is 1199999999 while range ends at 15",
        ]
        self._test("address_map_err", err)

    def test_connections_data_width(self):
        err = [
            "ERROR: insufficient number of connections, each top level port must include connection",
            "ERROR: in 'connections' from 'a' to 'b', 'data_width' takes positive int as an argument",
            "ERROR: in 'connections' from 'a' to 'c', 'data_width' takes positive int as an argument",
            "ERROR: in 'connections' from 'a' to 'd', 'data_width' takes positive int as an argument",
            "ERROR: in 'connections' from 'a' to 'e', 'data_width' takes positive int as an argument",
        ]
        self._test("connections_data_width_err", err)

    def test_connections_protocol(self):
        err = [
            "ERROR: insufficient number of connections, each top level port must include connection",
            "ERROR: in 'connections' from 'a' to 'b', 'protocol' must be 'True' or 'False'",
            "ERROR: in 'connections' from 'a' to 'c', 'protocol' must be 'True' or 'False'",
            "ERROR: in 'connections' from 'a' to 'd', 'protocol' must be 'True' or 'False'",
        ]
        self._test("connections_protocol_err", err)

    def test_connections_axi_max_reads(self):
        err = [
            "ERROR: insufficient number of connections, each top level port must include connection",
            "ERROR: in 'connections' from 'a' to 'b', 'axi_max_reads' takes positive int as an argument",
            "ERROR: in 'connections' from 'a' to 'c', 'axi_max_reads' takes positive int as an argument",
            "ERROR: in 'connections' from 'a' to 'd', 'axi_max_reads' takes positive int as an argument",
            "ERROR: in 'connections' from 'a' to 'e', 'axi_max_reads' takes positive int as an argument",
        ]
        self._test("connections_axi_max_reads_err", err)

    def test_connections_cdc(self):
        err = [
            "ERROR: insufficient number of connections, each top level port must include connection",
            "ERROR: in 'connections' from 'a' to 'b', 'cdc' must be 'True' or 'False'",
            "ERROR: in 'connections' from 'a' to 'c', 'cdc' must be 'True' or 'False'",
            "ERROR: in 'connections' from 'a' to 'd', 'cdc' must be 'True' or 'False'",
        ]
        self._test("connections_cdc_err", err)

    def test_connections_registers(self):
        err = [
            "ERROR: insufficient number of connections, each top level port must include connection",
            "ERROR: in 'connections' from 'a' to 'b', 'registers' takes positive int as an argument",
            "ERROR: in 'connections' from 'a' to 'c', 'registers' takes positive int as an argument",
            "ERROR: in 'connections' from 'a' to 'd', 'registers' takes positive int as an argument",
            "ERROR: in 'connections' from 'a' to 'e', 'registers' takes positive int as an argument",
        ]
        self._test("connections_registers_err", err)
