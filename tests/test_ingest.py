"""The Auto Loader configuration matches the spec (§7); the stream itself runs only on Databricks."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from fraud_ingest.contract import SCHEMA_HINTS  # expected hints
from fraud_ingest.ingest import build_autoloader_options, state_paths  # names under test


def test_state_paths_live_under_one_volume_folder():  # verify state paths are organized under one folder
    assert state_paths("/Volumes/workspace/fraud/pipeline_state") == {  # ADR 0001: state on a UC volume
        "schema": "/Volumes/workspace/fraud/pipeline_state/schema",          # schema tracking
        "checkpoint": "/Volumes/workspace/fraud/pipeline_state/checkpoint",  # stream progress
    }  # end state_paths result dict


def test_autoloader_options_match_the_spec():  # verify autoloader options match the spec
    assert build_autoloader_options("/state/schema") == {  # exact option set
        "cloudFiles.format": "json",                          # JSON Lines landing files
        "cloudFiles.schemaLocation": "/state/schema",         # enables inference and evolution
        "cloudFiles.inferColumnTypes": "false",               # default: strings, then hints pin types
        "cloudFiles.schemaHints": SCHEMA_HINTS,               # typed fields -> bad values rescued
        "cloudFiles.schemaEvolutionMode": "addNewColumns",    # new fields join the schema after one restart
    }  # end autoloader options result dict


def test_module_imports_without_pyspark():  # verify pyspark is not imported at module level
    import fraud_ingest.ingest as ingest  # must not import pyspark at module level
    assert callable(ingest.start_bronze_ingest)  # entry point exists
