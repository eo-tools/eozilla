#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional, get_args, get_origin

from pydantic import BaseModel, ValidationError, create_model
from pydantic.fields import FieldInfo

from gavicore.models import (
    InputDescription,
    OutputDescription,
    ProcessDescription,
    Schema,
)
from gavicore.util.schema import create_schema_dict


@dataclass
class Process:
    """
    A process comprises a process description and executable code
    in form of a Python function.

    Instances of this class are be managed by the
    [ProcessRegistry][procodile.ProcessRegistry].

    Attributes:
        function: The user's Python function.
        signature: The signature of `function`.
        job_ctx_arg: Names of `function` arguments of type `JobContext`.
        model_class: Pydantic model class for the arguments of `function`.
        description: Process description modelled after
            [OGC API - Processes - Part 1: Core](https://docs.ogc.org/is/18-062r2/18-062r2.html#toc37).
    """

    function: Callable
    signature: inspect.Signature
    model_class: type[BaseModel]
    description: ProcessDescription
    # names of special arguments
    inputs_arg: str | None
    job_ctx_arg: str | None

    # noinspection PyShadowingBuiltins
    @classmethod
    def create(
        cls,
        function: Callable,
        id: Optional[str] = None,
        version: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        input_fields: Optional[dict[str, FieldInfo | InputDescription]] = None,
        output_fields: Optional[dict[str, FieldInfo | OutputDescription]] = None,
        inputs_arg: str | bool = False,
    ) -> "Process":
        """Create a new instance of this dataclass.

        Called by the `ProcessRegistry.process()` decorator function.
        Not intended to be used by clients.
        """
        if not inspect.isfunction(function):
            raise TypeError("function argument must be callable")
        fn_name = f"{function.__module__}:{function.__qualname__}"
        id = id or fn_name
        version = version or "0.0.0"
        description = description or inspect.getdoc(function)
        signature = inspect.signature(function)
        inputs, model_class, input_arg_, job_ctx_arg = _parse_inputs(
            fn_name, signature, input_fields, inputs_arg
        )
        outputs = _parse_outputs(fn_name, signature.return_annotation, output_fields)
        return Process(
            function=function,
            signature=signature,
            model_class=model_class,
            description=ProcessDescription(
                id=id,
                version=version,
                title=title,
                description=description,
                inputs=inputs,
                outputs=outputs,
                # Note, we may later add the following:
                # metadata=metadata,
                # keywords=keywords,
                # links=links,
                # outputTransmission=output_transmission,
                # jobControlOptions=job_control_options,
            ),
            inputs_arg=input_arg_,
            job_ctx_arg=job_ctx_arg,
        )


def _parse_inputs(
    fn_name: str,
    signature: inspect.Signature,
    input_fields: dict[str, FieldInfo | InputDescription] | None,
    inputs_arg: str | bool,
) -> tuple[dict[str, InputDescription], type[BaseModel], str | None, str | None]:
    arg_parameters, job_ctx_arg = _parse_parameters(fn_name, signature)

    model_class: type[BaseModel]
    input_arg_: str | None = None
    if inputs_arg:
        model_class, input_arg_ = _parse_input_arg(fn_name, arg_parameters, inputs_arg)
    else:
        model_field_definitions: dict[str, Any] = {
            param_name: (
                (parameter.annotation, parameter.default)
                if parameter.default is not inspect.Parameter.empty
                else parameter.annotation
            )
            for param_name, parameter in arg_parameters.items()
        }
        model_class = create_model("ProcessInputs", **model_field_definitions)

    field_infos = (
        {k: v for k, v in input_fields.items() if isinstance(v, FieldInfo)}
        if input_fields
        else {}
    )
    if field_infos:
        model_class = _merge_field_infos_into_model_class(
            fn_name=fn_name,
            signature=signature,
            field_infos=field_infos,
            model_class=model_class,
        )

    model_class.model_rebuild()

    inputs_schema_dict: dict[str, Any] = create_schema_dict(model_class)
    required_names: list[str] = inputs_schema_dict.get("required", [])
    properties: dict[str, Any] = inputs_schema_dict.get("properties", {})

    input_descriptions: dict[str, InputDescription] = {}
    for input_name, input_schema_dict in properties.items():
        base_description = _get_input_description_from_fields(input_name, input_fields)
        schema_dict = dict(input_schema_dict)
        title = schema_dict.pop("title", None)
        descr = schema_dict.pop("description", None)
        schema = _create_schema(fn_name, "input", input_name, schema_dict)
        description = InputDescription(
            minOccurs=1 if input_name in required_names else 0,
            maxOccurs=None,
            schema=schema,
            title=title,
            description=descr,
        )
        input_descriptions[input_name] = _merge_input_descriptions(
            description, base_description
        )
    return input_descriptions, model_class, input_arg_, job_ctx_arg


def _parse_outputs(
    fn_name: str,
    output_annotation: type,
    output_fields: dict[str, FieldInfo | OutputDescription] | None,
) -> dict[str, OutputDescription]:
    model_field_definitions = _create_output_model_field_definitions(
        fn_name, output_annotation, output_fields
    )
    model_class = create_model("Outputs", **model_field_definitions)
    outputs_schema_dict = create_schema_dict(model_class)
    properties = outputs_schema_dict.get("properties", {})

    output_descriptions: dict[str, OutputDescription] = {}
    for output_name, output_schema_dict in properties.items():
        base_description = _get_output_description_from_fields(
            output_name, output_fields
        )
        schema_dict = dict(output_schema_dict)
        title = schema_dict.pop("title", None)
        descr = schema_dict.pop("description", None)
        schema = _create_schema(fn_name, "output", output_name, schema_dict)
        description = OutputDescription(
            schema=schema,
            title=title,
            description=descr,
        )
        output_descriptions[output_name] = _merge_output_descriptions(
            description, base_description
        )
    return output_descriptions


def _parse_parameters(
    fn_name: str, signature: inspect.Signature
) -> tuple[dict[str, inspect.Parameter], str | None]:
    from .job import JobContext

    arg_parameters: dict[str, inspect.Parameter] = {}
    job_ctx_arg: str | None = None
    for param_name, parameter in signature.parameters.items():
        if parameter.annotation is JobContext:
            if job_ctx_arg:
                raise ValueError(
                    f"function {fn_name!r}: only one parameter can have type "
                    f"{JobContext.__name__}, but found {job_ctx_arg!r} "
                    f"and {param_name!r}"
                )
            job_ctx_arg = param_name
        else:
            arg_parameters[param_name] = parameter
    return arg_parameters, job_ctx_arg


def _merge_field_infos_into_model_class(
    fn_name: str,
    signature: inspect.Signature,
    field_infos: dict[str, FieldInfo],
    model_class: type[BaseModel],
) -> type[BaseModel]:
    invalid_inputs = [
        input_name
        for input_name in field_infos
        if input_name not in signature.parameters
    ]
    if invalid_inputs:
        raise ValueError(
            f"function {fn_name!r}: "
            "all input names must have corresponding parameter names; "
            f"invalid input name(s): {', '.join(map(repr, invalid_inputs))}"
        )

    # noinspection PyTypeChecker
    model_field_definitions: dict[str, Any] = dict(model_class.model_fields)
    for input_name, field_info in field_infos.items():
        if input_name in model_field_definitions:
            old_field_info = model_field_definitions[input_name]
            parameter = signature.parameters[input_name]
            model_field_definitions[input_name] = (
                parameter.annotation,
                FieldInfo.merge_field_infos(old_field_info, field_info),
            )

    return create_model(model_class.__name__, **model_field_definitions)


def _parse_input_arg(
    fn_name: str,
    arg_parameters: dict[str, inspect.Parameter],
    inputs_arg: str | Literal[True],
) -> tuple[type[BaseModel], str]:
    if len(arg_parameters) > 1:
        raise ValueError(
            f"function {fn_name!r}: the inputs argument must be the only "
            f"argument (inputs_arg={inputs_arg!r})"
        )

    inputs_arg_param: inspect.Parameter | None
    if isinstance(inputs_arg, str):
        inputs_arg_param = arg_parameters.get(inputs_arg)
    else:
        inputs_arg_param = (
            list(arg_parameters.values())[0] if len(arg_parameters) == 1 else None
        )

    if inputs_arg_param is None:
        raise ValueError(
            f"function {fn_name!r}: specified inputs argument "
            f"is not an argument of the function (inputs_arg={inputs_arg!r})"
        )

    model_class = inputs_arg_param.annotation
    # noinspection PyTypeChecker
    if isinstance(model_class, type) and issubclass(model_class, BaseModel):
        return model_class, inputs_arg_param.name
    else:
        raise TypeError(
            f"function {fn_name!r}: type of inputs argument "
            f"{inputs_arg_param.name!r} must be a subclass of BaseModel"
        )


def _create_output_model_field_definitions(
    fn_name: str,
    annotation: type,
    output_fields: dict[str, FieldInfo | OutputDescription] | None,
) -> dict[str, Any]:
    model_field_definitions: dict[str, Any] = {}

    if not output_fields:
        # No output fields specified -> we use the annotation
        model_field_definitions = _create_output_field_entry("return_value", annotation)
    elif len(output_fields) == 1:
        # A single output field specified -> we use the annotation and the field
        output_name, field_info = next(iter(output_fields.items()))
        model_field_definitions = _create_output_field_entry(
            output_name, annotation, field_info
        )
    else:
        origin = get_origin(annotation)
        args = get_args(annotation)
        if not (origin is tuple and args):
            raise TypeError(
                f"function {fn_name!r}: return type must be tuple[] with arguments"
            )
        if len(args) != len(output_fields):
            raise ValueError(
                f"function {fn_name!r}: number of outputs must match number "
                f"of tuple[] arguments"
            )
        for arg_type, (output_name, field_info) in zip(args, output_fields.items()):
            model_field_definitions.update(
                _create_output_field_entry(output_name, arg_type, field_info)
            )
    return model_field_definitions


def _get_input_description_from_fields(
    name: str,
    fields: dict[str, FieldInfo | InputDescription] | None,
) -> InputDescription | None:
    if not fields:
        return None
    field = fields.get(name)
    return field if isinstance(field, InputDescription) else None


def _get_output_description_from_fields(
    name: str,
    fields: dict[str, FieldInfo | OutputDescription] | None,
) -> OutputDescription | None:
    if not fields:
        return None
    field = fields.get(name)
    return field if isinstance(field, OutputDescription) else None


def _merge_input_descriptions(
    description: InputDescription,
    base_description: InputDescription | None,
) -> InputDescription:
    if base_description is None:
        return description
    return InputDescription(
        schema=_merge_schemas(base_description.schema_, description.schema_),
        title=base_description.title or description.title,
        description=base_description.description or description.description,
        keywords=base_description.keywords or description.keywords,
        metadata=base_description.metadata or description.metadata,
        additionalParameters=(
            base_description.additionalParameters or description.additionalParameters
        ),
    )


def _merge_output_descriptions(
    description: OutputDescription,
    base_description: OutputDescription | None,
) -> OutputDescription:
    if base_description is None:
        return description
    return OutputDescription(
        schema=_merge_schemas(base_description.schema_, description.schema_),
        title=base_description.title or description.title,
        description=base_description.description or description.description,
        keywords=base_description.keywords or description.keywords,
        metadata=base_description.metadata or description.metadata,
        additionalParameters=(
            base_description.additionalParameters or description.additionalParameters
        ),
    )


def _create_schema(
    fn_name: str, param_type: str, param_name: str, schema: dict[str, Any]
) -> Schema:
    try:
        return Schema(**schema)
    except ValidationError as e:
        raise ValueError(
            f"function {fn_name}(), {param_type} {param_name!r}: {e}"
        ) from e


def _create_output_field_entry(
    output_name: str,
    output_annotation: Any,
    output_field: FieldInfo | OutputDescription | None = None,
) -> dict:
    if isinstance(output_field, FieldInfo):
        return {output_name: (output_annotation, output_field)}
    else:
        return {output_name: output_annotation}


def _merge_schemas(schema_1: Schema, schema_2: Schema) -> Schema:
    return Schema(
        **_merge_dicts_flat(_to_schema_dict(schema_1), _to_schema_dict(schema_2))
    )


def _merge_dicts_flat(d1: dict[str, Any], d2: dict[str, Any]) -> dict[str, Any]:
    d = dict(d1)
    for k, v2 in d2.items():
        if k in d:
            v1 = d1[k]
            if isinstance(v1, dict) and isinstance(v2, dict):
                v2 = _merge_dicts_flat(v1, v2)
        d[k] = v2
    return d


def _to_schema_dict(schema: Schema) -> dict[str, Any]:
    return schema.model_dump(
        mode="json", exclude_unset=True, exclude_defaults=True, exclude_none=True
    )
