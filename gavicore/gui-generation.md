# UI-Generation for Cuiman

This document has been created with the help of ChatGPT 5.2, 
but it is carefully reviewed and edited. 

It shall serve as a reference for planned enhancements of the 
CLI- and GUI-generation in Eozilla Cuiman.


## Universal Algorithm: JSON Schema → Form Panels

This document describes a simple and robust algorithm used by many 
schema-driven UI generators to convert JSON Schema into panel-based 
forms.

The approach works well for systems like:

- OGC API Processes clients
- OpenAPI form generators
- Workflow UIs
- JSON Schema form libraries
- CWL / Argo tool interfaces

Pipeline

    Schema
       ↓
    Field model
       ↓
    Grouped + ordered fields
       ↓
    Panels


### Step 1: Extract Fields from the Schema

Start from the root input schema.

Example schema

    {
      "type": "object",
      "properties": {
        "text": { "type": "string" },
        "mode": { "type": "string", "enum": ["fast","accurate"] }
      },
      "required": ["text"]
    }

Algorithm

    for property_name, property_schema in schema["properties"].items():
        field = build_field(property_name, property_schema)

Each field should capture

    id
    type
    required
    title
    description
    default
    enum
    ui hints

Example field model

    Field(
      id="text",
      type="string",
      required=True,
      widget="textarea",
      group="basic",
      order=10
    )


### Step 2: Merge Schema Metadata and UI Metadata

Combine three sources

    schema validation
    schema annotations
    x-ui metadata

Typical resolution logic

    title =
        schema.title
        or input.title
        or propertyName

    description =
        schema.description
        or input.description

Resolve UI hints

    ui = resolve_ui_metadata(input, schema)

    widget = ui.widget
    group  = ui.group
    order  = ui.order

Example result

    Field(
      id="crs",
      type="string",
      widget="text",
      placeholder="EPSG:4326",
      group="advanced",
      order=20
    )


### Step 3: Determine Widget Automatically (Fallback)

If UI metadata does not specify a widget, infer it from the schema.

Mapping used by most generators

    string              → text
    string + enum       → select
    string + password   → password
    number              → number
    integer             → number
    boolean             → checkbox
    array               → list
    object              → subform

Example inference

    if enum:
        widget = "select"

    elif schema.type == "boolean":
        widget = "checkbox"

    elif schema.type == "string":
        widget = "text"


### Step 4: Assign Fields to Panels

Panels are determined using the group metadata.

    panel = field.group or "main"

Example panel structure

    main
      ├ text
      └ mode

    advanced
      └ crs


### Step 5: Order Fields

Sort fields inside each panel.

Priority order

    1. x-ui.order
    2. schema.propertyOrder
    3. alphabetical

Example

    panel.fields.sort(key=lambda f: f.order)


### Step 6: Build Nested Panels (Objects)

If a property is itself an object

    {
      "type": "object",
      "properties": { ... }
    }

Create a sub-panel.

Example

    geometry
      ├ buffer_distance
      └ unit

Algorithm

    if schema.type == "object":
        recurse(schema.properties)


### Step 7: Handle Arrays

Arrays represent repeating fields.

Example schema

    {
      "type": "array",
      "items": { "type": "string" }
    }

Typical UI

    + Add item
    - Remove item


### Step 8: Final Panel Model

Internal UI model example

    Panel(
      name="main",
      fields=[
         Field("text", widget="textarea"),
         Field("mode", widget="select")
      ]
    )

    Panel(
      name="advanced",
      fields=[
         Field("crs", widget="text")
      ]
    )


### Why This Algorithm Works Across Ecosystems

Modern API and workflow ecosystems converged on this separation

    JSON Schema → semantics and validation
    OpenAPI / OGC → parameter metadata
    x-ui → presentation hints

A form generator merges these layers.

Used by

- React JSONSchema Form
- OpenAPI UI generators
- Backstage scaffolder
- Kubernetes CRD editors
- Argo workflow UIs
- CWL GUI tools


### Recommended Enhancement: Structural Grouping

Panels can also be inferred directly from schema structure.

Example

    {
      "properties": {
        "processing": {
          "type": "object",
          "properties": {
            "buffer": { "type": "number" },
            "simplify": { "type": "number" }
          }
        }
      }
    }

Generated UI

    Processing
      ├ buffer
      └ simplify


### Minimal Pseudocode

    fields = extract_fields(schema)

    for field in fields:
        field.ui = resolve_ui(field)

        if not field.widget:
            field.widget = infer_widget(field)

    panels = group_by(fields, field.group or "main")

    for panel in panels:
        panel.fields.sort(by_order)


## OGC API Processes → Form Panel Mapping

This section explains how an OGC API Processes client (such as cuiman)
can transform a process description into the internal field model used
by the form panel generator.


### Typical Process Input Structure

A process description usually contains:

    process.inputs[]

Each input may contain

    id
    title
    description
    schema
    minOccurs
    maxOccurs
    formats
    default
    additionalParameters
    x-ui (extension)

Example

    {
      "id": "geometry",
      "title": "Input geometry",
      "description": "Feature collection",
      "schema": {
        "type": "string",
        "contentMediaType": "application/geo+json"
      }
    }


### Step 1: Build Field Model from Process Inputs

For each process input

    for input in process.inputs:
        field = build_field(input)

Mapping

    field.id            ← input.id
    field.title         ← input.title
    field.description   ← input.description
    field.required      ← (minOccurs > 0)
    field.schema        ← input.schema


### Step 2: Merge Schema Metadata

If an input contains a schema, merge its properties.

Example

    schema.type
    schema.enum
    schema.default
    schema.minimum
    schema.maximum

Mapping

    field.type        ← schema.type
    field.enum        ← schema.enum
    field.default     ← schema.default


### Step 3: Resolve UI Metadata

UI hints may appear in multiple places.

Resolution order

    1 input["x-ui"]
    2 input["ui"]
    3 schema["x-ui"]
    4 schema["ui"]

Example

    {
      "x-ui": {
        "widget": "textarea",
        "group": "advanced",
        "order": 20
      }
    }

Mapping

    field.widget      ← ui.widget
    field.group       ← ui.group
    field.order       ← ui.order
    field.placeholder ← ui.placeholder
    field.secret      ← ui.secret


### Step 4: Derive File Inputs

OGC APIs often represent file inputs using media types.

Example

    {
      "type": "string",
      "contentMediaType": "application/geo+json"
    }

or

    formats:
        - mediaType: application/geo+json

Client logic

    if schema.contentMediaType exists:
        widget = "file"

    field.fileAccept ← contentMediaType


Example mapping

    contentMediaType = application/geo+json

becomes

    Field(
        widget="file",
        fileAccept=["application/geo+json"]
    )

### Step 5: Handle Literal vs Complex Inputs

Inputs fall into two categories.


Literal values

    number
    string
    boolean
    enum

→ rendered as simple form controls


Complex values

    object
    array
    file / dataset

→ rendered as nested panels or file pickers

### Step 6: Arrays and Cardinality

Cardinality is defined by

    minOccurs
    maxOccurs

Rules

    maxOccurs == 1
        → single field

    maxOccurs > 1
        → repeating field

Example UI

    + Add item
    - Remove item

### Step 7: Panel Grouping

Fields are grouped using

    x-ui.group

Fallback

    group = "main"

Example

    main
        ├ geometry
        ├ distance

    advanced
        ├ simplify
        └ tolerance

### Step 8: Final Internal Representation

The client should convert inputs into a UI model like

    Panel(
        name="main",
        fields=[
            Field("geometry", widget="file"),
            Field("distance", widget="number")
        ]
    )

    Panel(
        name="advanced",
        fields=[
            Field("simplify", widget="checkbox")
        ]
    )

### Recommended Client Architecture

A clean OGC API Processes UI client pipeline looks like this

    Process description
           ↓
    Parameter model
           ↓
    JSON Schema merge
           ↓
    UI metadata merge
           ↓
    Field model
           ↓
    Panels


This architecture keeps

    semantics      (schema)
    metadata       (input description)
    presentation   (x-ui)

cleanly separated.

## Handling `oneOf` / `anyOf` / `allOf` in JSON Schema for Tool UIs

JSON Schema composition constructs are powerful but can break
naïve form generators. Tool interfaces frequently encounter them
in OpenAPI, OGC APIs, and workflow systems.

The three constructs serve different purposes and should be
handled differently by UI generators.

### `oneOf` - Alternative Input Types

`oneOf` means the input must match exactly one schema option.

Example

    {
      "oneOf": [
        {
          "title": "GeoJSON",
          "type": "string",
          "contentMediaType": "application/geo+json"
        },
        {
          "title": "WKT",
          "type": "string"
        }
      ]
    }

**UI Strategy**: Render a selector that chooses which schema variant is active.

Example UI

    Geometry format

    ( ) GeoJSON file
    ( ) WKT string

After selection, render the corresponding field.

Implementation idea

    selector = choose(oneOf.options)

    render(schema = selector.selected)


Recommended widget

    widget = "schema-selector"


### `anyOf` - Multiple Optional Shapes

anyOf means the value may match one or more schemas.

Example

    {
      "anyOf": [
        { "type": "string" },
        { "type": "number" }
      ]
    }

This is ambiguous for UI generation.

**Recommended strategy**: Prefer a simple fallback control.

Example

    widget = "text"

or

    widget = "json-editor"


Most workflow tools avoid full UI branching for anyOf.

### `allOf` - Schema Composition

`allOf` means schemas are merged together.

Example

    {
      "allOf": [
        { "$ref": "#/definitions/BaseGeometry" },
        {
          "properties": {
            "buffer": { "type": "number" }
          }
        }
      ]
    }

**UI Strategy**: Flatten the schemas.

Implementation

    merged_schema = merge(allOf.schemas)

Then generate fields from the merged schema.


### Discriminator-Based `oneOf`

Many OpenAPI schemas use a `discriminator` field.

Example

    {
      "oneOf": [
        { "$ref": "#/schemas/FileInput" },
        { "$ref": "#/schemas/UrlInput" }
      ],
      "discriminator": {
        "propertyName": "type"
      }
    }

**UI Strategy**: Render a dropdown bound to the discriminator.

Example UI

    Input source

        file
        url

Switching the dropdown changes the visible fields.

### Recommended Simplification Strategy

For workflow or tool UIs, a practical rule set works well.

    allOf  → merge schemas
    oneOf  → render schema selector
    anyOf  → fallback editor or first schema


Pseudo logic

    if schema.allOf:
        schema = merge(schema.allOf)

    if schema.oneOf:
        render_selector(schema.oneOf)

    if schema.anyOf:
        render_generic_input()


### Example Internal Representation

The generator might create a field like

    Field(
        id="geometry",
        widget="schema-selector",
        variants=[
            SchemaVariant("GeoJSON", schema1),
            SchemaVariant("WKT", schema2)
        ]
    )


### Why This Matters for Tool Interfaces

Composition appears often when APIs allow multiple
representations for the same conceptual input.

Examples

    geometry as
        - file
        - URL
        - inline JSON

    dataset as
        - ID reference
        - file upload

Handling these with a schema selector keeps
the UI predictable and compact.


### Recommended Internal Pipeline

A robust client pipeline looks like

    raw schema
        ↓
    resolve $ref
        ↓
    flatten allOf
        ↓
    detect oneOf / anyOf
        ↓
    build field model
        ↓
    render UI

This keeps schema composition logic separate
from the UI rendering layer.

## Resolving `$ref` and External Schemas in Tool Descriptions

Many OpenAPI and OGC API schemas use $ref to reference definitions.
A UI generator must resolve these references before building form fields.

This step is essential for reliable schema-driven interfaces.


### What `$ref` Means

A `$ref` replaces the current schema node with another schema.

Example

    {
      "$ref": "#/components/schemas/Geometry"
    }

Meaning

    Replace this node with the referenced schema.

### Local References

Local references point inside the same document.

Example

    {
      "$ref": "#/definitions/BoundingBox"
    }

Resolution algorithm

    target = resolve_pointer(document, "#/definitions/BoundingBox")

    schema = target


Example resolved result

    {
      "type": "array",
      "items": { "type": "number" },
      "minItems": 4,
      "maxItems": 4
    }


### External References

Some schemas reference external files or URLs.

Example

    {
      "$ref": "https://example.org/schemas/geometry.json"
    }

Client behavior

    if reference not cached:
        fetch schema
        cache it

    replace node with fetched schema


Recommendation

Cache external schemas aggressively to avoid repeated network requests.

### Reference Chains

References may point to schemas that contain further references.

Example

    A → $ref B
    B → $ref C

Resolution rule

Resolve recursively until the final schema is reached.

Pseudo logic

    function resolve(schema):
        while schema contains "$ref":
            schema = load_ref(schema["$ref"])
        return schema


### Circular References

Some schemas contain cycles.

Example

    Node
      └ children → Node

Naïve recursion will cause infinite loops.

Strategy

Track visited references.

Example

    visited_refs = set()

    if ref in visited_refs:
        stop recursion

    visited_refs.add(ref)


For UI generation this usually means rendering a nested structure editor.


### Merge with `allOf` After Resolution

After resolving references, composition keywords must still be handled.

Example

    {
      "allOf": [
        { "$ref": "#/schemas/BaseInput" },
        { "properties": { "buffer": { "type": "number" } } }
      ]
    }

Resolution pipeline

    resolve $ref
        ↓
    flatten allOf
        ↓
    build fields

### Recommended Client Pipeline

A robust schema handling pipeline looks like

    raw schema
        ↓
    resolve $ref
        ↓
    detect cycles
        ↓
    flatten allOf
        ↓
    process oneOf / anyOf
        ↓
    build field model


Keeping these steps separate greatly simplifies debugging.


### Practical Optimization

Schema resolution can be expensive if repeated often.

Recommended cache

    schema_cache[url]

Before loading a schema

    if url in cache:
        return cached_schema


This improves performance significantly when multiple inputs
reference the same definitions.


### Example Internal Function

Example reference resolver

    function resolve_schema(schema):

        if "$ref" in schema:
            target = load_reference(schema["$ref"])
            return resolve_schema(target)

        if "allOf" in schema:
            merged = merge_allOf(schema["allOf"])
            return resolve_schema(merged)

        return schema


### Why This Matters for Tool UIs

Without proper reference resolution, the UI generator may see only

    { "$ref": "..." }

and cannot determine

    type
    enum
    constraints
    nested properties

Resolving schemas first ensures the UI generator works with the
complete semantic definition.

---