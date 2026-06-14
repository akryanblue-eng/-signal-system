use crate::schema::EventSchema;

pub fn emit_json(schemas: &[EventSchema]) -> String {
    let mut out = String::new();
    out.push_str("[\n");
    for (i, schema) in schemas.iter().enumerate() {
        out.push_str("  {\n");
        out.push_str(&format!("    \"event_type\": \"{}\",\n", schema.event_type));
        out.push_str("    \"fields\": [\n");
        for (j, field) in schema.fields.iter().enumerate() {
            out.push_str("      {\n");
            out.push_str(&format!("        \"name\": \"{}\",\n", field.name));
            out.push_str(&format!("        \"type\": \"{}\",\n", field.ty.as_str()));
            out.push_str(&format!("        \"required\": {},\n", field.required));
            out.push_str(&format!("        \"index\": {}\n", j));
            if j < schema.fields.len() - 1 {
                out.push_str("      },\n");
            } else {
                out.push_str("      }\n");
            }
        }
        out.push_str("    ]\n");
        if i < schemas.len() - 1 {
            out.push_str("  },\n");
        } else {
            out.push_str("  }\n");
        }
    }
    out.push_str("]\n");
    out
}
