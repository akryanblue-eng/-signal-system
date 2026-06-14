use crate::schema::Schema;

pub fn emit_rust(schemas: &[Schema]) -> String {
    let mut out = String::new();

    out.push_str("// DSVM-0 GENERATED FILE — DO NOT EDIT\n");
    out.push_str("// source: EVENT_SCHEMAS.v1\n");
    out.push_str("// generator: dsvm-schema-compiler@v1.0\n\n");

    out.push_str("#[derive(Debug, Clone, PartialEq)]\n");
    out.push_str("pub enum QSEvent {\n");
    for schema in schemas {
        let name = to_rust_enum(&schema.eventType);
        if schema.fields.is_empty() {
            out.push_str(&format!("    {name},\n"));
        } else {
            let fields: Vec<String> = schema
                .fields
                .iter()
                .map(|f| format!("{}: {}", f.name, rust_type(&f.r#type)))
                .collect();
            out.push_str(&format!("    {name} {{ {} }},\n", fields.join(", ")));
        }
    }
    out.push_str("}\n\n");

    out.push_str("impl QSEvent {\n");
    out.push_str("    pub fn event_type(&self) -> &str {\n");
    out.push_str("        match self {\n");
    for schema in schemas {
        let name = to_rust_enum(&schema.eventType);
        if schema.fields.is_empty() {
            out.push_str(&format!(
                "            QSEvent::{name} => \"{}\",\n",
                schema.eventType
            ));
        } else {
            out.push_str(&format!(
                "            QSEvent::{name} {{ .. }} => \"{}\",\n",
                schema.eventType
            ));
        }
    }
    out.push_str("        }\n");
    out.push_str("    }\n");
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

fn rust_type(t: &str) -> &str {
    match t {
        "string" => "String",
        "int" => "i64",
        "bool" => "bool",
        _ => panic!("Unknown type: {t} (should be rejected by validator)"),
    }
}
