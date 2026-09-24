"""Consumer: one Auto Loader stream from the landing folder into the Bronze table (ADR 0007)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from typing import Any  # loose type for the SparkSession

from fraud_ingest.contract import SCHEMA_HINTS  # typed fields for Auto Loader


# ── Configuration ─────────────────────────────────────────────
def state_paths(state_root: str) -> dict[str, str]:  # compute schema and checkpoint paths from root
    """Schema location and checkpoint, both under one pipeline_state volume."""  # docstring
    return {"schema": f"{state_root}/schema", "checkpoint": f"{state_root}/checkpoint"}  # two sub-folders


def build_autoloader_options(schema_location: str) -> dict[str, str]:  # construct Auto Loader configuration options
    """Auto Loader options from spec §7 (facts checked against Databricks docs 2026-09-24)."""  # docstring
    return {  # option name -> value
        "cloudFiles.format": "json",                        # JSON Lines files
        "cloudFiles.schemaLocation": schema_location,       # tracks the schema over time
        "cloudFiles.inferColumnTypes": "false",             # default all-strings inference...
        "cloudFiles.schemaHints": SCHEMA_HINTS,             # ...with the important fields pinned
        "cloudFiles.schemaEvolutionMode": "addNewColumns",  # fails once on a new field, resumes on retry
    }


# ── Stream (Databricks only) ──────────────────────────────────
def start_bronze_ingest(spark: Any, landing_path: str, state_root: str, target_table: str) -> None:  # load landing files into Bronze via Auto Loader stream
    """Load every not-yet-seen landing file into Bronze, then stop (Trigger.AvailableNow)."""  # docstring
    from pyspark.sql import functions as F  # imported here so local tests never need PySpark

    paths = state_paths(state_root)  # schema + checkpoint folders
    stream = (  # read side
        spark.readStream.format("cloudFiles")  # Auto Loader source
        .options(**build_autoloader_options(paths["schema"]))  # spec options
        .load(landing_path)  # the only folder Auto Loader watches
    )  # end read side stream definition
    enriched = stream.select(  # add ingest metadata; "*" keeps _rescued_data
        "*",  # every record field
        F.col("_metadata.file_modification_time").alias("file_arrived_at"),  # when the file landed
        F.col("_metadata.file_path").alias("source_file"),  # which file the row came from
        F.current_timestamp().alias("ingested_at"),  # when this run loaded it
    )  # end enriched select
    query = (  # write side
        enriched.writeStream.option("checkpointLocation", paths["checkpoint"])  # exactly-once per file
        .option("mergeSchema", "true")  # Bronze accepts new columns (schema-change scenario)
        .trigger(availableNow=True)  # process what's there, then stop (serverless-supported)
        .toTable(target_table)  # Delta append into Bronze
    )  # end write side stream definition
    query.awaitTermination()  # block until caught up; raises if the stream failed
