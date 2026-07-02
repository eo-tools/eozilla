from __future__ import annotations

import yaml

from gavicore.cwl.models import CommandLineTool

NDVI_CWL = """
cwlVersion: v1.0
class: CommandLineTool

label: Compute NDVI
doc: Computes an NDVI raster from Sentinel-2 bands.

baseCommand:
  - ndvi

requirements:
  DockerRequirement:
    dockerPull: ghcr.io/acme/ndvi:1.2

inputs:
  nir:
    type: File
    inputBinding:
      prefix: --nir

  red:
    type: File
    inputBinding:
      prefix: --red

  output_format:
    type: string?
    default: GeoTIFF
    inputBinding:
      prefix: --format

outputs:
  ndvi:
    type: File
    outputBinding:
      glob: "*.tif"
"""


ZONAL_STATS_CWL = """
cwlVersion: v1.0
class: CommandLineTool

label: Zonal Statistics

baseCommand:
  - zonalstats

requirements:
  DockerRequirement:
    dockerPull: ghcr.io/acme/zonalstats:2.0

inputs:
  raster:
    type: File
    inputBinding:
      prefix: --raster

  polygons:
    type: File
    inputBinding:
      prefix: --polygons

  statistics:
    type:
      type: array
      items:
        type: enum
        symbols:
          - mean
          - min
          - max
          - median
    inputBinding:
      prefix: --stat
      separate: true

outputs:
  table:
    type: File
    outputBinding:
      glob: "*.csv"
"""


def parse_cwl(text: str) -> CommandLineTool:
    data = yaml.safe_load(text)
    return CommandLineTool.model_validate(data)


def test_parse_ndvi_cwl() -> None:
    doc = parse_cwl(NDVI_CWL)

    assert doc.cwl_version == "v1.0"
    assert doc.class_ == "CommandLineTool"
    assert doc.label == "Compute NDVI"
    assert doc.requirements.docker_requirement.docker_pull == "ghcr.io/acme/ndvi:1.2"
    assert doc.inputs.root["nir"].type.is_file
    assert doc.inputs.root["red"].type.is_file
    assert doc.inputs.root["output_format"].default == "GeoTIFF"
    assert doc.outputs.root["ndvi"].output_binding.glob == "*.tif"


def test_parse_zonal_stats_cwl() -> None:
    doc = parse_cwl(ZONAL_STATS_CWL)

    statistics = doc.inputs.root["statistics"].type.root

    assert doc.label == "Zonal Statistics"
    assert (
        doc.requirements.docker_requirement.docker_pull == "ghcr.io/acme/zonalstats:2.0"
    )
    assert statistics.type == "array"
    assert statistics.items.type == "enum"
    assert statistics.items.symbols == ["mean", "min", "max", "median"]
    assert doc.outputs.root["table"].output_binding.glob == "*.csv"
