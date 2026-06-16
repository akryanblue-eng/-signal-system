import Foundation
import CryptoSwift

public enum ProjectionHasher {

    public static func hash(_ data: Data) -> Hash32 {
        let digest = data.sha256()
        return Hash32(bytes: Data(digest))
    }

    public static func eventHash(
        _ event: OracleEventEnvelope<GazeSamplePayload>
    ) -> Hash32 {
        hash(CanonicalEncoder.encodeEventWithoutHash(event))
    }

    public static func projectionHash(_ frame: ProjectionFrame) -> Hash32 {
        hash(CanonicalEncoder.encodeProjection(frame))
    }
}
