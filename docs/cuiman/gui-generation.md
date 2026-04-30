# Cuiman GUI-Generation 

The Cuiman GUI to build process requests is generated from a selected 
[OGC process descriptions](https://docs.ogc.org/is/18-062r2/18-062r2.html#toc35).
For a given process, the input descriptions are used to build an 
[OpenAPI Schema v3.0](https://swagger.io/specification/v3/) of type `object` 
comprising the inputs as properties. The GUI is generated from this root schemas. 

The pipeline in short:

    Process Input Descriptions
       ↓
    Schema
       ↓
    Field Metadata
       ↓
    Field = View Model + View (Panel viewables)


The UI generation at its core is not aware of the target UI library
that is used to render the UI and let users interact with it.

The framework used to generate UIs is implemented in the Eozilla 
Gavicore package `gavicore.ui` and is documented 
[here](../gavicore/ui/description.md).  

## Customizing Schemas

Cuiman's default UI library is [Panel](https://panel.holoviz.org/).
Therefore, most of the customization configuration is directly mapped
to configuration of the underlying Panel widgets and viewables.


### Schema Mapping Overview

A given schema is converted into UI fields given using the available metadata that 
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
- `x-ui-order` - number of string used for sorting the fields of a group
- `x-ui-layout` - grouping fields and group layout

Note that you can also use the prefix "x-ui:" instead of "x-ui-". The latter is 
more convenient when encoding schemas is YAML. If multiple extensions are used,
in a schema or process input description, they can also be grouped in an object 
property named `x-ui`:

```yaml
    x-ui: 
      widget: slider,
      minimum: 0,        
      maximum: 100,
      step: 5,
    }
```

The extensions can occur in bot schemas and process input/output descriptions. 

**Schema widget mapping:** 

The following list provides an overview about the currently implemented
mapping of schema elements to Panel widgets and panels.

- `type: boolean`: creates **checkbox** and **switch** widgets.
- `type: integer` and `type: number`: creates numeric **input** or **slider** widgets.
    * `enum: [...]`: creates numeric **select**, **radio group**, 
      or **toggle button group** widgets. 
- `type: string`: creates **text input**, **textarea**, **date/time picker** widgets.
    * `enum: [...]`: creates textual **select**, **radio group**, 
      or **toggle button group** widgets. 
    * `format: password`: creates a **password input** widget.
    * `format: datetime`: creates a **datetime picker** widget.
    * `format: date`: creates a **date picker** widget.
    * `format: time`: creates a **time picker** widget.
- `type: array`: creates **array input** widgets for numeric and textual item types
  or **array editors** for any item schema type. 
  A few special tuple types such as **geographic bounding boxes** and 
  **date(-time) ranges** are supported too.
- `type: object`: creates a **sub-form** with optionally ordered and outlaid 
  fields for the object properties.
- `oneOf: [s1, s2, s3, ...]`: creates a **tabs panel** with a tab 
  generated for each subschemas `s{i}`. An optional schema `discriminator` 
  is fully supported. Typically, the item schemas are objects.
- `anyOf: [s1, s2, s3, ...]`: same as `oneOf`. 
- `allOf: [s1, s2, s3, ...]`: creates a field for the schema resulting from
  merging the schemas `s{i}`. Typically, the item schemas are objects.
- `nullable: true`: creates a **labeled switch** widget that if selected, shows
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
to Panel widgets in more detail including the available customization options. 


### Type `boolean`

Schemas of type `boolean` generate 
a [checkbox](https://panel.holoviz.org/reference/widgets/Checkbox.html)
by default. 

**Customisation options**: 

- `x-ui-widget: switch`: generates a 
  [switch](https://panel.holoviz.org/reference/widgets/Switch.html) instead.


### Type `integer` and `number`

Schemas of type `integer` and `number` generate 
an [int input](https://panel.holoviz.org/reference/widgets/IntInput.html)
or [float input](https://panel.holoviz.org/reference/widgets/FloatInput.html) 
by default if `enum` is not specified. With `enum`, a 
[select](https://panel.holoviz.org/reference/widgets/Select.html) is generated.

**Customisation options**: 

- `x-ui-widget: slider` generates a 
  [slider](https://panel.holoviz.org/reference/widgets/IntSlider.html). 
  Requires `minimum` and `maximum` to be given too, optionally also `step` to
  control the step size. 

If `enum` is given too:

- `x-ui-widget: slider` generates a 
  [discrete slider](https://panel.holoviz.org/reference/widgets/DiscreteSlider.html).
- `x-ui-widget: radio` generates a 
  [radio box group](https://panel.holoviz.org/reference/widgets/RadioBoxGroup).
- `x-ui-widget: button` generates a 
  [radio button group](https://panel.holoviz.org/reference/widgets/RadioButtonGroup).
- `x-ui-widget: select` generates a 
  [select](https://panel.holoviz.org/reference/widgets/Select) widget.


### Type `string`

Schemas of Type `string` generates 
a [text-input](https://panel.holoviz.org/reference/widgets/TextInput.html)
by default if `format` is not provided (or currently unsupported) and `enum` 
is not specified. 

If `enum` is specified, a [select](https://panel.holoviz.org/reference/widgets/Select) 
widget is generated by default.

If `format` is given:

- `format: byte`: generates a 
  [file input](https://panel.holoviz.org/reference/widgets/FileInput.html) 
  and stores the file data as base64-encoded string.
- `format: password`: generates a 
  [password input](https://panel.holoviz.org/reference/widgets/PasswordInput.html)
  and stores the password as plain text (take care!).
- `format: date-time`: generates a 
  [datetime picker](https://panel.holoviz.org/reference/widgets/DatetimePicker.html).
- `format: date`: generates a 
  [date picker](https://panel.holoviz.org/reference/widgets/DatePicker.html).
- `format: time`: generates a 
  [time picker](https://panel.holoviz.org/reference/widgets/TimePicker.html).

**Customisation options**: 

- `x-ui-widget: dropper`: generates a 
  [file dropper](https://panel.holoviz.org/reference/widgets/FileDropper.html) 
  if `format` is `bytes` and stores the file data as base64-encoded string.  
- `x-ui-widget: input`: generates a 
  [datetime input](https://panel.holoviz.org/reference/widgets/DatetimeInput.html) 
  if `format` is `date-time`.  
- `x-ui-widget: textarea`: generates a 
  [text area input](https://panel.holoviz.org/reference/widgets/TextAreaInput.html) 
  if `format` is not provided or currently unsupported.

If `enum` is specified:

- `x-ui-widget: radio` generates a 
  [radio box group](https://panel.holoviz.org/reference/widgets/RadioBoxGroup).
- `x-ui-widget: button` generates a 
  [radio button group](https://panel.holoviz.org/reference/widgets/RadioButtonGroup).
- `x-ui-widget: select` generates a 
  [select](https://panel.holoviz.org/reference/widgets/Select) widget.


### Type `array`

With a few exceptions, the `array` type will generate an _array editor_ field.
The editor is used to interactively add, edit, and remove array items. 
The array item fields are generated from the schema's `items` property 
which specifies the items' schema.

A few tuple types are supported that generate special widgets instead of 
the default array editor:

- **geographic bounding boxes**: item type `number` with `minItems: 4`, `maxItems: 4`, 
  and `x-ui-widget: map` creates a special editor to enter the bounding box
  using [](). It lets users draw a geometry whose bounding 
  box will become the effective field value.

- **date(-time) ranges**: item type `string` with `minItems: 2`, `maxItems: 2` creates 
  a [date-time range picker](https://panel.holoviz.org/reference/widgets/DatetimeRangePicker.html) 
  for item format `date-time` or 
  a [date range picker](https://panel.holoviz.org/reference/widgets/DateRangePicker.html) 
  for item format `date`. 

**Customisation options**: 

- `x-ui-widget: input` generates array input widgets where users enter array
  items into a [text-input](https://panel.holoviz.org/reference/widgets/TextInput.html)
  separated by a comma or a character specified by the `x-ui-separator` property.   
- `x-ui-widget: textarea` similar as above, but uses a multi-line 
  [text area](https://panel.holoviz.org/reference/widgets/TextAreaInput.html).


### Type `object`

Schemas of Type `object` generate sub-form with optionally ordered and outlaid 
fields for the object's `properties`.

**Customisation options**: 

If no layout or order is specified, the property forms are generated in the 
order that corresponds to order of the `properties` in the object schema.

- `x-ui-layout: column`: arranges the sub-fields in a column  
- `x-ui-layout: row`: arranges the sub-fields in a row  
- `x-ui-layout: { layout }`: specifies a layout. A layout is an object with
  two properties `type` and `items`. `type` is either `column` (default)
  or `row` and `items` is an optional list of property names or of other layout 
  objects. If `items` is not not given, it defaults to all properties that 
  have not yet been part of the layout.
- `x-ui-order: <order`: a integer value that can be used in the property schemas
  to specify the fields order. The default order value is the index of 
  a property in its given order.


### `nullable` Schemas 

If `nullable: true` a labeled switch widget is created that if selected, 
shows the generated field for the same schema, but using `nullable: false`.
If the switch is unselected, the effective value of the field will be 
`null` (`Null` in Python).


### `oneOf` and `anyOf` Schemas

The values of both `oneOf` and `anyOf` are lists that define 
alternative schemas. They create create a **tabs panel** with a tab 
generated for each subschemas `s{i}`. 

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


## Customizing the UI Generation

Under the hood the `cuiman.gui` package uses the common package 
`gavicore.ui` that provides the core UI generation framework.
Within that framework, `gavicore.ui.panel` implements a UI generator 
using the [panel](https://pypi.org/project/panel/) package.
However, [panel](https://pypi.org/project/panel/) is an optional package to Gavicore
as usually only Eozilla/Cuiman client applications require a GUI.

### 1. Define the required customization

Let's say we want to generate a custom UI for a 2-tuple representing
a numeric value range, whose values can be validated by the following 
schema: 

```yaml
    type: array
    items: 
      type: number
      minimum: -1.0
      maximum: 1.0
    minItems: 2
    maxItems: 2
    default: [-1.0, 1.0]
```

The UI field to be generated for this schema should be a 
[numeric range slider](https://panel.holoviz.org/reference/widgets/EditableRangeSlider.html). 
Furthermore, we say that the field is only used if `x-ui-widget: range-input`.

### 2. Create a custom field factory

In order to generate the desired UI field, we'll develop a custom
`gavicore.ui.panel.PanelFieldFactory` class and register an instance of it 
in the framework. 

The `PanelFieldFactory` is a typed abstract base class that implements 
the generic `gavicore.ui.FieldFactory` interface. A `FieldFactory` is 
responsible for calculating a "suitability score" for a given field metadata
 `gavicore.ui.FieldMeta` which includes the OpenAPI schema and derived metadata.

The framework selects the factory with the highest score for a given schema.
The default score returned by the inbuilt factories is `5`.
If a factory was selected, it is asked to create a `gavicore.ui.Field` given the
current `gavicore.ui.FieldContext`. A `PanelFieldFactory` is supposed to only create 
`gavicore.ui.panel.PanelField` instances.

The above is best explained by example. First we create a new class
`NumberRangeFactory` that derives from `PanelFieldFactoryBase`:

```python
from gavicore.models import DataType
from gavicore.ui import FieldContext, FieldMeta
from gavicore.ui.panel import PanelField, PanelFieldFactoryBase


class NumberRangeFactory(PanelFieldFactoryBase):
    def get_array_score(self, meta: FieldMeta) -> int:
        """Compute the score of this factory for an array schema."""
        ...

    def create_array_field(self, ctx: FieldContext) -> PanelField:
        """Create the Panel field for the selected array schema."""
        ...
```

### 3. Implement the custom field factory

Lets implement `get_array_score()` first:

```python
    def get_array_score(self, meta: FieldMeta) -> int:
        schema = meta.schema_
        assert schema.type == DataType.array  # will never fail 
        is_range_input = (
            meta.widget == 'range-input' 
            and schema.items is not None 
            and schema.items.type == DataType.number
            and schema.minItems == 2 
            and schema.maxItems == 2
        )
        return 100 if is_range_input else 0
```

Now `create_array_field()`:

```python
    def create_array_field(self, ctx: FieldContext) -> int:
        # A view model is a reactive holder for some value, 
        # here an array value:
        view_model=ctx.vm.array()
        # The view must derive from type pn.widgets.WidgetBase
        view = pn.widgets.EditableRangeSlider(
            name=ctx.label,  # always use ctx.label for adding labels to widgets 
            value=view_model.value, # the view model's initial value is used here
        )
        return PanelField(view_model=view_model, view=view)
```

### 4. Register the custom field factory

Finally, we register an instance of the new class in the Cuiman client's 
configuration:

```python
from cuiman.api import ClientConfig

config = ClientConfig.default_config
config.get_field_factory_registry().register(NumberRangeFactory())
```

The next time you run the Cuiman GUI client, it will consider that factory
for generating its GUIs for a given OGC process description, provided
that the above code is executed once before the GUI is used.
