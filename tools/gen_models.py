#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datamodel_code_generator as dcg

from tools.common import EOZILLA_PATH, OPEN_API_PATH

MODELS_PATH = EOZILLA_PATH / "gavicore/src/gavicore/models.py"


def main():
    assert not bool(dcg), "NO ERROR: see gavicore.models.QualifiedValue, then uncomment"
    dcg.generate(
        input_=OPEN_API_PATH,
        input_file_type=dcg.InputFileType.OpenAPI,
        # use_annotated=True, # --> if True, mypy cannot see pydantic aliases
        use_double_quotes=True,
        use_standard_collections=True,
        use_schema_description=True,
        use_non_positive_negative_number_constrained_types=True,
        use_title_as_name=True,
        use_one_literal_as_default=True,
        use_union_operator=False,
        field_constraints=True,
        set_default_enum_member=True,
        keep_model_order=False,
        target_python_version=dcg.PythonVersion.PY_310,
        output_model_type=dcg.DataModelType.PydanticV2BaseModel,
        output=MODELS_PATH,
    )


if __name__ == "__main__":
    main()
