use crate::schema::EventSchema;

pub fn emit_rust(schemas: &[EventSchema]) -> String {
    let mut out = String::new();

    out.push_str("// DSVM-0 GENERATED FILE — DO NOT EDIT\n");
    out.push_str("// source: EVENT_SCHEMAS.v1\n");
    out.push_str("// generator: dsvm-schema-compiler@v1.0\n\n");

    out.push_str("#[derive(Debug, Clone, PartialEq)]\n");
    out.push_str("pub enum QSEvent {\n");
    for schema in schemas {
        let name = to_rust_enum(&schema.event_type);
        if schema.fields.is_empty() {
            out.push_str(&format!("    {name},\n"));
        } else {
            let fields: Vec<String> = schema
                .fields
                .iter()
                .map(|f| format!("{}: {}", f.name, f.ty.rust_type()))
                .collect();
            out.push_str(&format!("    {name} {{ {} }},\n", fields.join(", ")));
        }
    }
    out.push_str("}\n\n");

    out.push_str("impl QSEvent {\n");
    out.push_str("    pub fn event_type(&self) -> &str {\n");
    out.push_str("        match self {\n");
    for schema in schemas {
        let name = to_rust_enum(&schema.event_type);
        if schema.fields.is_empty() {
            out.push_str(&format!(
                "            QSEvent::{name} => \"{}\",\n",
                schema.event_type
            ));
        } else {
            out.push_str(&format!(
                "            QSEvent::{name} {{ .. }} => \"{}\",\n",
                schema.event_type
            ));
        }
    }
    out.push_str("        }\n");
    out.push_str("    }\n");
    out.push_str("}\n\n");

    // Bijectivity surface: sorted list of all known event type strings.
    out.push_str("pub const EVENT_TYPES: &[&str] = &[\n");
    for schema in schemas {
        out.push_str(&format!("    \"{}\",\n", schema.event_type));
    }
    out.push_str("];\n\n");

    // Binary search on the sorted constant — O(log n), no heap allocation.
    out.push_str("pub fn is_known_event_type(s: &str) -> bool {\n");
    out.push_str("    EVENT_TYPES.binary_search(&s).is_ok()\n");
    out.push_str("}\n");

    out
}

fn to_rust_enum(s: &str) -> String {
    let mut out = String::new();
    let mut upper_next = true;
    for c in s.chars() {
        if c == '_' {
            upper_next = true;
        } else if upper_next {
            out.push(c.to_ascii_uppercase());
            upper_next = false;
        } else {
            out.push(c);
        }
    }
    out
}
