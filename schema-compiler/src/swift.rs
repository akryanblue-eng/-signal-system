use crate::schema::EventSchema;

pub fn emit_swift(schemas: &[EventSchema]) -> String {
    let mut out = String::new();

    out.push_str("// DSVM-0 GENERATED FILE — DO NOT EDIT\n");
    out.push_str("// source: EVENT_SCHEMAS.v1\n");
    out.push_str("// generator: dsvm-schema-compiler@v1.0\n\n");

    // Discriminator key only — no superset leakage
    out.push_str("private enum DiscriminatorKeys: String, CodingKey { case eventType }\n\n");

    // Per-event payload structs (events with fields only)
    for schema in schemas {
        if !schema.fields.is_empty() {
            let payload_name = to_swift_type_case(&schema.event_type) + "Payload";
            out.push_str(&format!("public struct {payload_name}: Codable, Equatable {{\n"));
            for field in &schema.fields {
                out.push_str(&format!(
                    "    public let {}: {}\n",
                    field.name,
                    field.ty.swift_type()
                ));
            }
            out.push_str("}\n\n");
        }
    }

    // Enum declaration
    out.push_str("public enum QSEvent: Codable, Equatable {\n");
    for schema in schemas {
        let case_name = to_swift_case(&schema.event_type);
        if schema.fields.is_empty() {
            out.push_str(&format!("    case {case_name}\n"));
        } else {
            let params: Vec<String> = schema
                .fields
                .iter()
                .map(|f| format!("{}: {}", f.name, f.ty.swift_type()))
                .collect();
            out.push_str(&format!("    case {}({})\n", case_name, params.join(", ")));
        }
    }
    out.push_str("}\n\n");

    // eventType property — bare case patterns (Swift 5.9+, any arity)
    out.push_str("extension QSEvent {\n");
    out.push_str("    public var eventType: String {\n");
    out.push_str("        switch self {\n");
    for schema in schemas {
        let case_name = to_swift_case(&schema.event_type);
        out.push_str(&format!(
            "        case .{case_name}: return \"{}\"\n",
            schema.event_type
        ));
    }
    out.push_str("        }\n");
    out.push_str("    }\n");
    out.push_str("}\n\n");

    // Decoder — pure switch-table routing; payload structs own field interpretation
    out.push_str("extension QSEvent {\n");
    out.push_str("    public init(from decoder: Decoder) throws {\n");
    out.push_str(
        "        let container = try decoder.container(keyedBy: DiscriminatorKeys.self)\n",
    );
    out.push_str("        let type = try container.decode(String.self, forKey: .eventType)\n");
    out.push_str("\n        switch type {\n");
    for schema in schemas {
        let case_name = to_swift_case(&schema.event_type);
        if schema.fields.is_empty() {
            out.push_str(&format!(
                "        case \"{}\":\n            self = .{case_name}\n",
                schema.event_type
            ));
        } else {
            let payload_name = to_swift_type_case(&schema.event_type) + "Payload";
            let args: Vec<String> = schema
                .fields
                .iter()
                .map(|f| format!("{0}: payload.{0}", f.name))
                .collect();
            out.push_str(&format!("        case \"{}\":\n", schema.event_type));
            out.push_str(&format!(
                "            let payload = try {payload_name}(from: decoder)\n"
            ));
            out.push_str(&format!(
                "            self = .{case_name}({})\n",
                args.join(", ")
            ));
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

    // Encoder — symmetric: DiscriminatorKeys owns eventType, payload structs own fields
    out.push_str("extension QSEvent {\n");
    out.push_str("    public func encode(to encoder: Encoder) throws {\n");
    out.push_str(
        "        var container = encoder.container(keyedBy: DiscriminatorKeys.self)\n",
    );
    out.push_str("        try container.encode(eventType, forKey: .eventType)\n");
    out.push_str("        switch self {\n");
    for schema in schemas {
        let case_name = to_swift_case(&schema.event_type);
        if schema.fields.is_empty() {
            out.push_str(&format!("        case .{case_name}: break\n"));
        } else {
            let payload_name = to_swift_type_case(&schema.event_type) + "Payload";
            let bindings: Vec<String> = schema
                .fields
                .iter()
                .map(|f| format!("let {}", f.name))
                .collect();
            let payload_args: Vec<String> = schema
                .fields
                .iter()
                .map(|f| format!("{0}: {0}", f.name))
                .collect();
            out.push_str(&format!(
                "        case .{case_name}({}):\n",
                bindings.join(", ")
            ));
            out.push_str(&format!(
                "            try {payload_name}({}).encode(to: encoder)\n",
                payload_args.join(", ")
            ));
        }
    }
    out.push_str("        }\n");
    out.push_str("    }\n");
    out.push_str("}\n");

    out
}

fn to_swift_case(s: &str) -> String {
    // snake_case → lowerCamelCase
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

fn to_swift_type_case(s: &str) -> String {
    // snake_case → UpperCamelCase (for struct names)
    let camel = to_swift_case(s);
    let mut chars = camel.chars();
    match chars.next() {
        None => String::new(),
        Some(c) => c.to_ascii_uppercase().to_string() + chars.as_str(),
    }
}
