# Cuiman GUI-Generation

The UI for the process inputs is generated from the
[OGC process description](https://docs.ogc.org/is/18-062r2/18-062r2.html#toc35)
of the currently selected process. The input descriptions are used to build an
[OpenAPI Schema v3.0](https://swagger.io/specification/v3/) of type `object`
comprising the inputs as properties.
The GUI is generated from this root schema.

The pipeline in short:

    Process Input Descriptions
       ↓
    Schema
       ↓
    Field Metadata
       ↓
    Field = View Model + View (Mantine React components)


The UI generation at its core is not aware of the target UI library
that is used to render the UI and let users interact with it.

The framework used to generate UIs is implemented in the
[Eozilla App](https://github.com/eo-tools/eozilla-app) and is documented
[here](https://github.com/eo-tools/eozilla-app/blob/main/schema-form.md).

## Customizing the UI

The UI generated from the process inputs can be customized by
the way the inputs' OpenAPI schemas are defined.
This is described in the following.

### Schema Mapping Overview

A given schema is converted into UI fields using the available metadata that
is part of the schema itself and metadata that can be specified using special
schema properties prefixed by "x-ui".

**Mapped OpenAPI/JSON schema metadata:**

- `title` - used as widget or group label
- `description` - used as tool-tip text, where possible
- `default` - serves as default value for the widget
- `enum` - provides the options for select-like widgets
- `format` - mostly for type `string`, controls the actual target data type

**Supported "x-ui" metadata extensions**:

- `x-ui-widget` - hint to generate a widget of the given type
- `x-ui-placeholder` - a placeholder value used in text or numeric input fields
- `x-ui-minimum` - minimum value for sliders
- `x-ui-maximum` - maximum value for sliders
- `x-ui-step` - step size for sliders
- `x-ui-order` - number or string used for sorting the fields of a group
- `x-ui-layout` - grouping fields and group layout

Note that you can also use the prefix "x-ui:" instead of "x-ui-". The latter is
more convenient when encoding schemas in YAML. If multiple extensions are used
in a schema or process input description, they can also be grouped in an object
property named `x-ui`:

```yaml
    x-ui:
      widget: slider
      minimum: 0
      maximum: 100
      step: 5
```

The extensions can occur in both schemas and process input or output descriptions.

**Schema widget mapping:**

The following list provides an overview about the currently implemented
mapping of schema elements to Mantine widgets and components.

- `type: boolean`: creates **checkbox** and **switch** widgets.
- `type: integer` and `type: number`: creates numeric **input** or **slider** widgets.
    * `enum: [...]`: creates numeric **select**, **radio group**,
      or **segmented control** widgets.
- `type: string`: creates **text input**, **textarea**, **date/time picker** widgets.
    * `enum: [...]`: creates textual **select**, **radio group**,
      or **segmented control** widgets.
    * `format: password`: creates a **password input** widget.
    * `format: date-time`: creates a **datetime picker** widget.
    * `format: date`: creates a **date picker** widget.
    * `format: time`: creates a **time picker** widget.
- `type: array`: creates **array input** widgets for numeric and textual item types
  or **array editors** for any item schema type.
  A special tuple type for **geographic bounding boxes** is supported too.
- `type: object`: creates a **sub-form** with optionally ordered and outlaid
  fields for the object properties.
- `oneOf: [s1, s2, s3, ...]`: creates a **tabs** view with a tab
  generated for each subschema `s{i}`. An optional schema `discriminator`
  is fully supported. Typically, the item schemas are objects.
- `anyOf: [s1, s2, s3, ...]`: same as `oneOf`.
- `allOf: [s1, s2, s3, ...]`: creates a field for the schema resulting from
  merging the schemas `s{i}`. Typically, the item schemas are objects.
- `nullable: true`: creates a **labeled switch** widget that, if selected, shows
  the generated field for the same schema, but using `nullable: false`. If
  unselected, the value is `null` (JSON) or `Null` (Python).

If none of the above is given, a JSON editor widget will be generated for a given
schema.

**Partly supported schema keywords:**

- `$ref`: only schema-relative references are currently
  supported. For example, `$ref: #/$defs/Complex` expects a schema definition
  named `Complex` in a top-level JSON object `$defs` in the same schema.
  Schema definitions can also be referenced in nested objects, e.g.,
  `$ref: #/components/schemas/Complex`.
- `prefixItems`: JSON schema introduced this keyword to represent typed
  tuples. Since there is no unambiguous OpenAPI schema representation,
  multiple prefix-item schemas are converted into an `items` value which
  comprises a `oneOf` element of the converted `prefixItems` schemas.
- `items`: if the value is a list of schemas (= tuple), see `prefixItems` above.

**Currently unsupported schema keywords:**

- `additionalProperties`: currently not implemented, ignored for time being.
  The plan is to support it by a special editor that allows adding and removing
  named properties. Will work only if and only if `properties` is not given.
- `minProperties`, `maxProperties`: ignored.
- `additionalItems`: ignored.
- `not` - ignored, hence falls back to an untyped schema.


The following subsections describe the default mapping of schema types
to Mantine widgets in more detail including the available customization options.


### Type `boolean`

Schemas of type `boolean` generate a
[checkbox](https://mantine.dev/core/checkbox/)
by default.

**Customisation options**:

- `x-ui-widget: switch`: generates a
  [switch](https://mantine.dev/core/switch/) instead.


### Type `integer` and `number`

Schemas of type `integer` and `number` generate a
[number input](https://mantine.dev/core/number-input/)
by default if `enum` is not specified. With `enum`, a
[select](https://mantine.dev/core/select/) is generated.

**Customisation options**:

- `x-ui-widget: slider` generates a
  [slider](https://mantine.dev/core/slider/).
  Requires `minimum` and `maximum` to be given too, optionally also `step` to
  control the step size.

If `enum` is given too:

- `x-ui-widget: radio` generates a
  [radio group](https://mantine.dev/core/radio/).
- `x-ui-widget: button` generates a
  [segmented control](https://mantine.dev/core/segmented-control/).
- `x-ui-widget: select` generates a
  [select](https://mantine.dev/core/select/) widget.


### Type `string`

Schemas of type `string` generate a
[text input](https://mantine.dev/core/text-input/)
by default if `format` is not provided (or currently unsupported) and `enum`
is not specified.

If `enum` is specified, a [select](https://mantine.dev/core/select/)
widget is generated by default.

If `format` is given:

- `format: password`: generates a
  [password input](https://mantine.dev/core/password-input/) widget.
- `format: date-time`: generates a
  [datetime picker](https://mantine.dev/dates/date-time-picker/).
- `format: date`: generates a
  [date picker](https://mantine.dev/dates/date-picker-input/).
- `format: time`: generates a
  [time picker](https://mantine.dev/dates/time-input/).

**Customisation options**:

- `x-ui-widget: textarea`: generates a
  [text area input](https://mantine.dev/core/textarea/)
  if `format` is not provided or currently unsupported.

If `enum` is specified:

- `x-ui-widget: radio` generates a
  [radio group](https://mantine.dev/core/radio/).
- `x-ui-widget: button` generates a
  [segmented control](https://mantine.dev/core/segmented-control/).
- `x-ui-widget: select` generates a
  [select](https://mantine.dev/core/select/) widget.


### Type `array`

With a few exceptions, the `array` type will generate an _array editor_ field.
The editor is used to interactively add, edit, and remove array items.
The array item fields are generated from the schema's `items` property
which specifies the items' schema.

A few tuple types are supported that generates a special widget instead of
the default array editor:

- **geographic bounding boxes**: item type `number` with `minItems: 4`, `maxItems: 4`,
  and `x-ui-widget: map` (or `format: bbox`) creates a special editor to enter the
  bounding box using a map.
  It lets users draw a geometry whose bounding box will become the effective field
  value.

**Customisation options**:

- `x-ui-widget: input` generates array input widgets where users enter array
  items into a text input separated by a comma or a character specified by the `x-ui-separator` property.
- `x-ui-widget: textarea` is similar as above, but uses a multi-line
  text area.


### Type `object`

Schemas of type `object` generate a sub-form with optionally ordered and outlaid
fields for the object's `properties`.

**Customisation options**:

If no layout or order is specified, the property forms are generated in the
order that corresponds to order of the `properties` in the object schema.

- `x-ui-layout: column`: arranges the sub-fields in a column
- `x-ui-layout: row`: arranges the sub-fields in a row
- `x-ui-layout: { layout }`: specifies a layout. A layout is an object with
  two properties `type` and `items`. `type` is either `column` (default)
  or `row` and `items` is an optional list of property names or of other layout
  objects. If `items` is not given, it defaults to all properties that
  have not yet been part of the layout.
- `x-ui-order: <order>`: an integer value that can be used in the property schemas
  to specify the fields order. The default order value is the index of
  a property in its given order.


### `nullable` Schemas

If `nullable: true` a labeled switch widget is created that if selected,
shows the generated field for the same schema, but using `nullable: false`.
If the switch is unselected, the effective value of the field will be
`null` (`Null` in Python).


### `oneOf` and `anyOf` Schemas

The values of both `oneOf` and `anyOf` are lists that define
alternative schemas. They create a **tabs** view with a tab
generated for each subschema `s{i}`.

Given that all subschemas are of type `object` an optional schema
`discriminator` specifies a common object property whose value
uniquely identifies the type of the subschema. The subschemas must
be specified by schema references using the `$ref` keyword.
The discriminator property is omitted from the generated sub-forms
as its field value is determined by `$ref` schema name or the
discriminator's optional `mapping` keys.


### `allOf` Schemas

The `allOf` schema combination creates a field for the schema resulting from
merging all its subschemas. Typically, the item schemas are objects and `allOf`
is used to represent a type derived form two or more subtypes.
