use crate::schema::Schema;

pub fn emit_swift(schemas: &[Schema]) -> String {
    let mut out = String::new();

    out.push_str("// DSVM-0 GENERATED FILE — DO NOT EDIT\n");
    out.push_str("// source: EVENT_SCHEMAS.v1\n");
    out.push_str("// generator: dsvm-schema-compiler@v1.0\n\n");

    // Superset CodingKeys (all field names across all schemas + eventType)
    let mut all_fields: Vec<&str> = Vec::new();
    for schema in schemas {
        for field in &schema.fields {
            if !all_fields.contains(&field.name.as_str()) {
                all_fields.push(&field.name);
            }
        }
    }
    all_fields.sort_unstable();

    out.push_str("private enum CodingKeys: String, CodingKey {\n");
    out.push_str("    case eventType\n");
    for name in &all_fields {
        out.push_str(&format!("    case {name}\n"));
    }
    out.push_str("}\n\n");

    // Enum
    out.push_str("public enum QSEvent: Codable, Equatable {\n");
    for schema in schemas {
        let case_name = to_swift_case(&schema.eventType);
        if schema.fields.is_empty() {
            out.push_str(&format!("    case {case_name}\n"));
        } else {
            let params: Vec<String> = schema
                .fields
                .iter()
                .map(|f| format!("{}: {}", f.name, swift_type(&f.r#type)))
                .collect();
            out.push_str(&format!("    case {}({})\n", case_name, params.join(", ")));
        }
    }
    out.push_str("}\n\n");

    // eventType property — bare case patterns work for any arity in Swift 5.9+
    out.push_str("extension QSEvent {\n");
    out.push_str("    public var eventType: String {\n");
    out.push_str("        switch self {\n");
    for schema in schemas {
        let case_name = to_swift_case(&schema.eventType);
        out.push_str(&format!(
            "        case .{case_name}: return \"{}\"\n",
            schema.eventType
        ));
    }
    out.push_str("        }\n");
    out.push_str("    }\n");
    out.push_str("}\n\n");

    // Decoder — strict dispatch table; default throws on unknown eventType
    out.push_str("extension QSEvent {\n");
    out.push_str("    public init(from decoder: Decoder) throws {\n");
    out.push_str("        let container = try decoder.container(keyedBy: CodingKeys.self)\n");
    out.push_str("        let type = try container.decode(String.self, forKey: .eventType)\n");
    out.push_str("\n        switch type {\n");
    for schema in schemas {
        let case_name = to_swift_case(&schema.eventType);
        if schema.fields.is_empty() {
            out.push_str(&format!(
                "        case \"{}\":\n            self = .{case_name}\n",
                schema.eventType
            ));
        } else {
            out.push_str(&format!("        case \"{}\":\n", schema.eventType));
            for field in &schema.fields {
                out.push_str(&format!(
                    "            let {0} = try container.decode({1}.self, forKey: .{0})\n",
                    field.name,
                    swift_type(&field.r#type)
                ));
            }
            // FIXED: include argument labels to match labeled associated value cases
            let args: Vec<String> = schema
                .fields
                .iter()
                .map(|f| format!("{0}: {0}", f.name))
                .collect();
            out.push_str(&format!("            self = .{case_name}({})\n", args.join(", ")));
        }
    }
    out.push_str("        default:\n");
    out.push_str("            throw DecodingError.dataCorruptedError(\n");
    out.push_str("                forKey: .eventType,\n");
    out.push_str("                in: container,\n");
    out.push_str("                debugDescription: \"Unknown eventType: \\(type)\"\n");
    out.push_str("            )\n");
    out.push_str("        }\n");
    out.push_str("    }\n");
    out.push_str("}\n\n");

    // Encoder — required by Codable; mirrors the decoder field layout
    out.push_str("extension QSEvent {\n");
    out.push_str("    public func encode(to encoder: Encoder) throws {\n");
    out.push_str("        var container = encoder.container(keyedBy: CodingKeys.self)\n");
    out.push_str("        try container.encode(eventType, forKey: .eventType)\n");
    out.push_str("        switch self {\n");
    for schema in schemas {
        let case_name = to_swift_case(&schema.eventType);
        if schema.fields.is_empty() {
            out.push_str(&format!("        case .{case_name}: break\n"));
        } else {
            let bindings: Vec<String> = schema
                .fields
                .iter()
                .map(|f| format!("let {}", f.name))
                .collect();
            out.push_str(&format!(
                "        case .{case_name}({}):\n",
                bindings.join(", ")
            ));
            for field in &schema.fields {
                out.push_str(&format!(
                    "            try container.encode({0}, forKey: .{0})\n",
                    field.name
                ));
            }
        }
    }
    out.push_str("        }\n");
    out.push_str("    }\n");
    out.push_str("}\n");

    out
}

fn to_swift_case(s: &str) -> String {
    let mut out = String::new();
    let mut upper_next = false;
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

fn swift_type(t: &str) -> &str {
    match t {
        "string" => "String",
        "int" => "Int64",
        "bool" => "Bool",
        _ => panic!("Unknown type: {t} (should be rejected by validator)"),
    }
}
