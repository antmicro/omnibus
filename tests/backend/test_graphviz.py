# Copyright (c) 2026 Antmicro
# SPDX-License-Identifier: Apache-2.0

import subprocess

from omnibus import InterconnectBuilder


#These tests check whether graphviz backend operates properly with all examples and some options
class TestGraphviz:
    def test_simple(self):
        ic = InterconnectBuilder(frontend="yaml", backend="graphviz") 

        ic.read_yaml("examples/simple.yml")
        ic.process()
        ic.generate(
            "tests/out/", 
            color_by="protocol", 
            color_scheme="paired12", 
            display_full_name=False)
        
        assert 0 == subprocess.call("diff -y tests/out/simple.gv tests/ideal/backend/graphviz/simple.gv", shell=True)

    def test_spec(self):
        ic = InterconnectBuilder(frontend="yaml", backend="graphviz") 

        ic.read_yaml("examples/spec.yml")
        ic.process()
        ic.generate(
            "tests/out/", 
            color_by="clock", 
            color_scheme="brbg10", 
            display_full_name=True)
        
        assert 0 == subprocess.call("diff -y tests/out/MyInterconnect.gv tests/ideal/backend/graphviz/spec.gv", shell=True)

    def test_butterfly(self):
        ic = InterconnectBuilder(frontend="yaml", backend="graphviz") 

        ic.read_yaml("examples/butterfly.yml")
        ic.process()
        ic.generate(
            "tests/out/") 
        
        assert 0 == subprocess.call("diff -y tests/out/butterfly.gv tests/ideal/backend/graphviz/butterfly.gv", shell=True)
        
    def test_asoca(self):
        ic = InterconnectBuilder(frontend="yaml", backend="graphviz") 

        ic.read_yaml("examples/asoca.yml")
        ic.process()
        ic.generate(
            "tests/out/", 
            color_by="data_width", 
            color_scheme="reds3") 
        
        assert 0 == subprocess.call("diff -y tests/out/ASoCaInt.gv tests/ideal/backend/graphviz/asoca.gv", shell=True)

    def test_idwidth(self):
        ic = InterconnectBuilder(frontend="yaml", backend="graphviz") 

        ic.read_yaml("tests/spec/idwidth_butterflyish.yml")
        ic.process()
        ic.generate(
            "tests/out/", 
            color_by="id_width") 
        
        assert 0 == subprocess.call("diff -y tests/out/butterflyish.gv tests/ideal/backend/graphviz/idwidth_butterflyish.gv", shell=True)
