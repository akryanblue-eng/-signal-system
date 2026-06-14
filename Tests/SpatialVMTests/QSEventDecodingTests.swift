import XCTest
@testable import SpatialVM

final class QSEventDecodingTests: XCTestCase {

    // MARK: - P2: Runtime unknown-eventType rejection

    func testUnknownEventTypeThrows() throws {
        let json = """
        {"eventType":"__unknown_event_type__","nodeId":"x"}
        """.data(using: .utf8)!

        XCTAssertThrowsError(try JSONDecoder().decode(QSEvent.self, from: json)) { err in
            // Confirm it's a data-corrupted error, not an unrelated failure.
            guard case DecodingError.dataCorrupted(let ctx) = err else {
                XCTFail("Expected DecodingError.dataCorrupted, got \(err)")
                return
            }
            XCTAssertTrue(
                ctx.debugDescription.contains("__unknown_event_type__"),
                "Error description should include the unknown type name"
            )
        }
    }

    func testKnownEventTypesDecodeSuccessfully() throws {
        let cases: [(String, QSEvent)] = [
            ("""{"eventType":"choose_ascension"}""", .chooseAscension),
            ("""{"eventType":"choose_creation"}""", .chooseCreation),
            ("""{"eventType":"enter_node","nodeId":"neon-in-nirvana"}""",
             .enterNode(nodeId: "neon-in-nirvana")),
            ("""{"eventType":"discover_artifact","artifactId":"signal-core"}""",
             .discoverArtifact(artifactId: "signal-core")),
            ("""{"eventType":"reveal_lore","loreId":"the-myth"}""",
             .revealLore(loreId: "the-myth")),
            ("""{"eventType":"node_completed","nodeId":"sky-high"}""",
             .nodeCompleted(nodeId: "sky-high")),
            ("""{"eventType":"portal_unlocked","portalId":"gate-zero"}""",
             .portalUnlocked(portalId: "gate-zero")),
        ]

        for (jsonString, expected) in cases {
            let data = jsonString.data(using: .utf8)!
            let decoded = try JSONDecoder().decode(QSEvent.self, from: data)
            XCTAssertEqual(decoded, expected, "Failed for: \(jsonString)")
        }
    }

    // MARK: - P3: Bijectivity via eventType round-trip

    func testEventTypeRoundTrip() throws {
        let events: [QSEvent] = [
            .chooseAscension,
            .chooseCreation,
            .enterNode(nodeId: "x"),
            .discoverArtifact(artifactId: "y"),
            .revealLore(loreId: "z"),
            .nodeCompleted(nodeId: "a"),
            .portalUnlocked(portalId: "b"),
        ]

        for event in events {
            let encoded = try JSONEncoder().encode(event)
            let decoded = try JSONDecoder().decode(QSEvent.self, from: encoded)
            XCTAssertEqual(event, decoded, "Round-trip failed for eventType '\(event.eventType)'")
        }
    }

    func testEventTypePropertyIsUnique() {
        let events: [QSEvent] = [
            .chooseAscension,
            .chooseCreation,
            .enterNode(nodeId: "x"),
            .discoverArtifact(artifactId: "y"),
            .revealLore(loreId: "z"),
            .nodeCompleted(nodeId: "a"),
            .portalUnlocked(portalId: "b"),
        ]

        let typeStrings = events.map { $0.eventType }
        let unique = Set(typeStrings)
        XCTAssertEqual(
            typeStrings.count, unique.count,
            "eventType property must return distinct strings for each variant (bijectivity)"
        )
    }

    func testEmptyPayloadEventsDecodeWithoutExtraFields() throws {
        // Confirm unit cases ignore extra fields (robustness)
        let json = """
        {"eventType":"choose_ascension","nodeId":"stray-field"}
        """.data(using: .utf8)!
        let decoded = try JSONDecoder().decode(QSEvent.self, from: json)
        XCTAssertEqual(decoded, .chooseAscension)
    }
}
