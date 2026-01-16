#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional, get_args, get_origin

from pydantic import BaseModel, Field, ValidationError, create_model
from pydantic.fields import FieldInfo

from gavicore.models import (
    AdditionalParameter,
    AdditionalParameters,
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
    [Workflow][procodile.Workflow].

    Attributes:
        function: The user's Python function.
        signature: The signature of `function`.
        job_ctx_arg: Names of `function` arguments of type `JobContext`.
        model_class: Pydantic model class for the arguments of `function`.
        description: Process description modeled after
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
        inputs: Optional[dict[str, FieldInfo | InputDescription]] = None,
        outputs: Optional[dict[str, FieldInfo | OutputDescription]] = None,
        inputs_arg: str | bool = False,
    ) -> "Process":
        """Create a new instance of this dataclass.

        Called by the `Workflow.main()` and `Workflow.step()` decorator function.
        Not intended to be used by clients.

        Args:
            function: The decorated function that is passed automatically since
                `process()` is a decorator function.
            id: Optional process identifier. Must be unique within the registry.
                If not provided, the fully qualified function name will be used.
            version: Optional version identifier. If not provided, `"0.0.0"`
                will be used.
            title: Optional, short process title.
            description: Optional, detailed description of the process. If not
                provided, the function's docstring, if any, will be used.
            inputs: Optional mapping from function argument names
                to [`pydantic.Field`](https://docs.pydantic.dev/latest/concepts/fields/)
                or [`InputDescription`][gavicore.models.InputDescription] instances.
                The preferred way is to annotate the arguments directly
                as described in [The Annotated Pattern](https://docs.pydantic.dev/latest/concepts/fields/#the-annotated-pattern).
                Use `InputDescription` instances to pass extra information that cannot
                be represented by a `pydantic.Field`, e.g., `additionalParameters` or `keywords`.
            outputs: Mapping from output names to
                [`pydantic.Field`](https://docs.pydantic.dev/latest/concepts/fields/)
                or [`OutputDescription`][gavicore.models.InputDescription] instances.
                Required, if you have multiple outputs returned as a
                dictionary. In this case, the function must return a typed `tuple` and
                output names refer to the items of the tuple in given order.
            inputs_arg: Specifies the use of an _inputs argument_. An inputs argument
                is a container for the actual process inputs. If specified, it must
                be the only function argument (besides an optional job context
                argument) and must be a subclass of `pydantic.BaseModel`.
                If `inputs_arg` is `True` the only argument will be the input argument,
                if `inputs_arg` is a `str` it must be the name of the only argument.

        """
        if not inspect.isfunction(function):
            raise TypeError("function argument must be callable")
        fn_name = f"{function.__module__}:{function.__qualname__}"
        id = id or fn_name
        version = version or "0.0.0"
        description = description or inspect.getdoc(function)
        signature = inspect.signature(function)
        input_descriptions, model_class, input_arg_, job_ctx_arg = _parse_inputs(
            fn_name, signature, inputs, inputs_arg
        )
        output_descriptions = _parse_outputs(
            fn_name, signature.return_annotation, outputs
        )
        return Process(
            function=function,
            signature=signature,
            model_class=model_class,
            description=ProcessDescription(
                id=id,
                version=version,
                title=title,
                description=description,
                inputs=input_descriptions,
                outputs=output_descriptions,
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


def additional_parameters(
    parameters: dict[str, Any], **metadata: Any
) -> AdditionalParameters:
    """
    Helper function that creates an instance of `AdditionalParameters`
    from the keys and values given the `parameters` dictionary.
    The return value is used as the `additionalParameters` argument of an
    `InputDescription` or `OutputDescription`.

    Args:
        parameters: the parameter key-value pairs.
        metadata: Other metadata fields passed to `AdditionalParameters`.

    Returns:
        A `AdditionalParameters` instance that can be passed to an
        `InputDescription` or `OutputDescription`.
    """
    return AdditionalParameters(
        parameters=[
            AdditionalParameter(name=k, value=[v]) for k, v in parameters.items()
        ],
        **metadata,
    )


def _parse_inputs(
    fn_name: str,
    signature: inspect.Signature,
    inputs: dict[str, FieldInfo | InputDescription] | None,
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

    if inputs:
        model_class = _merge_inputs_into_model_class(
            fn_name=fn_name,
            signature=signature,
            inputs=inputs,
            model_class=model_class,
        )

    model_class.model_rebuild()

    inputs_schema_dict: dict[str, Any] = create_schema_dict(model_class)
    required_names: list[str] = inputs_schema_dict.get("required", [])
    properties: dict[str, Any] = inputs_schema_dict.get("properties", {})

    input_descriptions: dict[str, InputDescription] = {}
    for input_name, input_schema_dict in properties.items():
        base_description = _get_input_description_from_fields(input_name, inputs)
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
    outputs: dict[str, FieldInfo | OutputDescription] | None,
) -> dict[str, OutputDescription]:
    model_field_definitions = _create_output_model_field_definitions(
        fn_name, output_annotation, outputs
    )
    model_class = create_model("Outputs", **model_field_definitions)  # type: ignore[call-overload]
    outputs_schema_dict = create_schema_dict(model_class)
    properties = outputs_schema_dict.get("properties", {})

    output_descriptions: dict[str, OutputDescription] = {}
    for output_name, output_schema_dict in properties.items():
        base_description = _get_output_description_from_fields(output_name, outputs)
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


def _merge_inputs_into_model_class(
    fn_name: str,
    signature: inspect.Signature,
    inputs: dict[str, FieldInfo | InputDescription],
    model_class: type[BaseModel],
) -> type[BaseModel]:
    invalid_inputs = [
        input_name for input_name in inputs if input_name not in signature.parameters
    ]
    if invalid_inputs:
        raise ValueError(
            f"function {fn_name!r}: "
            "all input names must have corresponding parameter names; "
            f"invalid input name(s): {', '.join(map(repr, invalid_inputs))}"
        )

    model_fields: dict[str, type | tuple[type, FieldInfo]] = {}
    for input_name, field_info in model_class.model_fields.items():
        parameter = signature.parameters[input_name]
        input_def = inputs.get(input_name)
        annotation: type = parameter.annotation
        if isinstance(input_def, FieldInfo):
            model_fields[input_name] = (
                annotation,
                FieldInfo.merge_field_infos(field_info, input_def),
            )
        elif isinstance(input_def, InputDescription):
            model_fields[input_name] = (
                annotation,
                FieldInfo.merge_field_infos(
                    field_info, _io_description_to_field_info(input_def)
                ),
            )
        else:
            model_fields[input_name] = (
                annotation,
                field_info,
            )

    return create_model(model_class.__name__, **model_fields)  # type: ignore[call-overload]


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
    outputs: dict[str, FieldInfo | OutputDescription] | None,
) -> dict[str, type | tuple[type, FieldInfo]]:
    model_fields: dict[str, Any] = {}
    if not outputs:
        # No output fields specified -> we use the annotation
        model_fields["return_value"] = _create_output_model_field_value(annotation)
    elif len(outputs) == 1:
        # A single output field specified -> we use the annotation and the field
        output_name, output_def = next(iter(outputs.items()))
        model_fields[output_name] = _create_output_model_field_value(
            annotation, output_def
        )
    else:
        origin = get_origin(annotation)
        args = get_args(annotation)
        if not (origin is tuple and args):
            raise TypeError(
                f"function {fn_name!r}: return type must be tuple[] with arguments"
            )
        if len(args) != len(outputs):
            raise ValueError(
                f"function {fn_name!r}: number of outputs must match number "
                f"of tuple[] arguments"
            )
        for arg_type, (output_name, output_def) in zip(args, outputs.items()):
            model_fields[output_name] = _create_output_model_field_value(
                arg_type, output_def
            )
    return model_fields


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
    # noinspection PyTypeChecker
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
    # noinspection PyTypeChecker
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
    fn_name: str, param_type: str, param_name: str, schema_dict: dict[str, Any]
) -> Schema:
    try:
        return Schema(**schema_dict)
    except ValidationError as e:
        raise ValueError(
            f"function {fn_name}(), {param_type} {param_name!r}: {e}"
        ) from e


def _create_output_model_field_value(
    annotation: type,
    io_def: FieldInfo | OutputDescription | None = None,
) -> type | tuple[type, FieldInfo]:
    if isinstance(io_def, FieldInfo):
        return annotation, io_def
    if isinstance(io_def, OutputDescription):
        return annotation, _io_description_to_field_info(io_def)
    return annotation


def _merge_schemas(schema_1: Schema, schema_2: Schema) -> Schema:
    return Schema(
        **_merge_dicts_flat(
            _schema_to_schema_dict(schema_1), _schema_to_schema_dict(schema_2)
        )
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


def _schema_to_schema_dict(schema: Schema) -> dict[str, Any]:
    return schema.model_dump(
        mode="json", exclude_unset=True, exclude_defaults=True, exclude_none=True
    )


def _io_description_to_field_info(
    io_description: InputDescription | OutputDescription,
) -> FieldInfo:
    json_schema_extra = _schema_to_schema_dict(io_description.schema_)
    return Field(json_schema_extra=json_schema_extra)
