# -*- coding: utf-8 -*-
"""Freeze of the v0.9.7 extractor release."""
import hashlib
import json
import unittest
from pathlib import Path

from biblioref.core.config import (
    ADAPTIVE_ANALYSIS_VERSION,
    ALGORITHM_VERSION,
    BASE_VERSION,
    RESCUE_ROUTER_VERSION,
    SOFTWARE_VERSION,
    STABLE_ENGINE_VERSION,
)

ROOT = Path(__file__).resolve().parent.parent
BASE_MODULE = ROOT / "biblioref_v0_2.py"
CORE = ROOT / "EXTRACTION_CORE_NONREGRESSION_V097_SHA256.json"
EQUIV = ROOT / "EXTRACTION_EQUIVALENCE_V097.json"
PARSER = ROOT / "biblioref/parsing/v09.py"

# Los algoritmos 0.6.9 y 0.6.10 cambian deliberadamente ``biblioref_v0_2.py``:
# el calificador de ``referencias`` y el umbral de evidencia de un estilo de
# marcador.  Estan declarados en EXTRACTION_CORE_NONREGRESSION_V069_SHA256.json
# y EXTRACTION_CORE_NONREGRESSION_V0610_SHA256.json con su equivalencia sobre el
# corpus completo.  SHA anteriores:
#   0.6.8  8683e68c23773f113b27cb2453b48d7539c1ca9147d470baaf1de306d6d775fa
#   0.6.9  9be0752d0245c961610ffaef209c374c11b38860f8a715576cef4189d8b98b06
#   0.6.11 07a96793c4147961ad8484913d69839287f8a5b056e004dc3d58fbd49ff78789
# 0.6.12 agrega «Lista de referencias» (EXTRACTION_CORE_NONREGRESSION_V0612_SHA256.json).
# 0.6.14 exige que cada nivel de la numeración del encabezado sea un token entero
# y el test de encabezado bibliográfico acepta enumeradores «7)», «G)», «A.»
# (EXTRACTION_CORE_NONREGRESSION_V0614_SHA256.json).
#   0.6.14 c2fb7d193dba50ff9ba29675ab79a86b7133184143e1428f094d53bea1b42fc8
# 0.6.15 acepta «[1 ]» y «( 2 )» como marcador numérico
# (EXTRACTION_CORE_NONREGRESSION_V0615_SHA256.json).
#   0.6.15 c1c15dab1450337b9d7c205b5b7b8ac334eed5c3935a7320ab0c9be926b27542
# 0.6.20 hace perder el estilo «viñetas» contra el triple de inicios de autor
# (EXTRACTION_CORE_NONREGRESSION_V0620_SHA256.json).
BASE_MODULE_SHA = "34ed0b1cf3f2976f235d6145165fc70a70b589f5dac8848901b742e3be1c15d0"
PARSER_V09_SHA = "4148701452aba620ec3538477010fc5f6c442a153be4a05063a43e7bb0c43320"


class TestV097Freeze(unittest.TestCase):
    def test_version_authorities(self):
        self.assertEqual("0.9.10-rc2", SOFTWARE_VERSION)
        self.assertEqual("0.6.21", ALGORITHM_VERSION)
        # unchanged authorities
        self.assertEqual("0.6.1", BASE_VERSION)
        self.assertEqual("0.4.5", STABLE_ENGINE_VERSION)
        self.assertEqual("0.8.10-shadow23", ADAPTIVE_ANALYSIS_VERSION)
        self.assertEqual("0.9.4-selective-router3-plausibility", RESCUE_ROUTER_VERSION)

    def test_base_module_source_freeze(self):
        self.assertEqual(
            BASE_MODULE_SHA, hashlib.sha256(BASE_MODULE.read_bytes()).hexdigest()
        )

    def test_parser_v09_is_carried_unchanged(self):
        self.assertEqual(
            PARSER_V09_SHA, hashlib.sha256(PARSER.read_bytes()).hexdigest()
        )

    def test_zone_and_segmentation_modules_are_byte_identical_to_v096(self):
        d = json.loads(CORE.read_text(encoding="utf-8"))
        self.assertTrue(d["all_identical"])
        self.assertTrue(all(f["identical"] for f in d["files"]))
        self.assertEqual(
            {"biblioref_v0_2.py", "biblioref/core/config.py"},
            {f["file"] for f in d["deliberately_changed"]},
        )

    def test_two_unrelated_theses_extract_identically_to_v096(self):
        d = json.loads(EQUIV.read_text(encoding="utf-8"))
        unchanged = [x for x in d["documents"] if x["identical"]]
        self.assertEqual(2, len(unchanged))
        for doc in unchanged:
            self.assertEqual(
                doc["v0_9_6"]["records_zones_sha256"],
                doc["v0_9_7"]["records_zones_sha256"],
                doc["id"],
            )

    def test_parser_remains_downstream_of_extraction_pipeline(self):
        source = (ROOT / "biblioref/pipeline.py").read_text(encoding="utf-8")
        self.assertNotIn("biblioref.parsing", source)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
