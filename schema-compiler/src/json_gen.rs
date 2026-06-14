use crate::schema::Schema;

pub fn emit_json(schemas: &[Schema]) -> String {
    let mut out = String::new();
    out.push_str("[\n");
    for (i, schema) in schemas.iter().enumerate() {
        out.push_str("  {\n");
        out.push_str(&format!("    \"eventType\": \"{}\",\n", schema.eventType));
        out.push_str("    \"fields\": [\n");
        for (j, field) in schema.fields.iter().enumerate() {
            out.push_str("      {\n");
            out.push_str(&format!("        \"name\": \"{}\",\n", field.name));
            out.push_str(&format!("        \"type\": \"{}\",\n", field.r#type));
            out.push_str(&format!("        \"index\": {}\n", field.index.unwrap()));
            if j < schema.fields.len() - 1 { out.push_str("      },\n"); } else { out.push_str("      }\n"); }
        }
        out.push_str("    ]\n");
        if i < schemas.len() - 1 { out.push_str("  },\n"); } else { out.push_str("  }\n"); }
    }
    out.push_str("]\n");
    out
}
