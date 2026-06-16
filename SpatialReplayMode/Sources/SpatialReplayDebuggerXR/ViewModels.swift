import Foundation
import Combine
import SpatialReplayDiff
import SpatialReplayDebugger

// MARK: - DiffStreamViewModel

/// Binds an AsyncStream<DiffFrame> and accumulates frames for spatial rendering.
/// All mutations happen on the MainActor so SwiftUI + RealityKit updates are safe.
@MainActor
public final class DiffStreamViewModel: ObservableObject {
    @Published public private(set) var allFrames: [DiffFrame] = []
    @Published public private(set) var latestFrame: DiffFrame?

    public init() {}

    public func bind(stream: AsyncStream<DiffFrame>) async {
        for await frame in stream {
            allFrames.append(frame)
            latestFrame = frame
        }
    }

    public func reset() {
        allFrames = []
        latestFrame = nil
    }
}

// MARK: - TimelineViewModel

/// Owns the selected frame index and playback control.
@MainActor
public final class TimelineViewModel: ObservableObject {
    @Published public var selectedFrame: UInt64 = 0
    @Published public private(set) var isPlaying: Bool = false

    public init() {}

    public func select(_ frame: UInt64) {
        selectedFrame = frame
    }

    public func togglePlayback() {
        isPlaying.toggle()
    }
}

// MARK: - InspectorViewModel

/// Holds the frame currently under inspection (gaze-selected or tap-selected).
@MainActor
public final class InspectorViewModel: ObservableObject {
    @Published public private(set) var inspectedFrame: DiffFrame?

    public init() {}

    public func inspect(_ frame: DiffFrame?) {
        inspectedFrame = frame
    }
}
