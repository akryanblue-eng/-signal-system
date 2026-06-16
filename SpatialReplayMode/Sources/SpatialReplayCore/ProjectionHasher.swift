import Foundation
import CryptoKit

public enum ProjectionHasher {

    public static func hash(_ data: Data) -> Hash32 {
        let digest = SHA256.hash(data: data)
        return Hash32(bytes: Data(digest))
    }

    public static func eventHash<T: Codable & Equatable>(
        _ event: OracleEventEnvelope<T>
    ) -> Hash32 {
        hash(CanonicalEncoder.encodeEvent(event))
    }

    public static func projectionHash(_ frame: ProjectionFrame) -> Hash32 {
        hash(CanonicalEncoder.encode(frame))
    }
}
