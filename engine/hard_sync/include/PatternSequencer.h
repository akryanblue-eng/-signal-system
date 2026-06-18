#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

#include "TriggerEvent.h"

namespace chilli {

// A single hit in a pattern: a beat position relative to the pattern's own
// start (e.g. 0.0, 0.5, 1.0, ... on an 1/8-note grid), plus every other
// field a trigger needs. Composed from TriggerEvent rather than duplicating
// its fields, so SequenceStep can never drift out of sync with whatever
// TriggerEvent actually carries. `trigger.timestamp` is ignored -- the
// sequencer overwrites it with the step's resolved absolute sample frame.
struct SequenceStep {
    double beat = 0.0;
    TriggerEvent trigger;
};

// Converts a musical pattern (steps in beats, tempo in BPM) into
// TriggerEvents with absolute sample-frame timestamps. Deliberately knows
// nothing about Engine/VoiceManager/RoutingEngine -- only TriggerEvent --
// so it stays a pure "musical position -> sample position" converter that
// any caller can feed into Engine::pushTrigger().
//
// Intended to run on the control/sequencer thread: TriggerEvent's own doc
// comment already describes that thread as the origin of every trigger, so
// unlike Engine/VoiceManager/RoutingEngine, resolveEvents() is not required
// to be allocation-free.
//
// Tempo is tracked as a running beat position (a double), not a
// fixed-point counter. At double precision, the accumulated error from
// advancing that position once per audio block is many orders of
// magnitude below a single sample period even after a full day of
// continuous playback, so fixed-point buys no real precision here. In
// exchange, a running beat position lets setTempo() take effect smoothly
// from the next call onward without retroactively reinterpreting where in
// the pattern every already-resolved block actually was -- which is what
// would happen if beat position were instead recomputed fresh from an
// absolute frame count and the *current* tempo on every call.
class PatternSequencer {
public:
    explicit PatternSequencer(double sampleRate) : sampleRate_(sampleRate) {}

    void setTempo(double bpm) { bpm_ = bpm; }

    // lengthBeats is the loop length: once the running beat position passes
    // it, playback wraps back to the start of the pattern. Steps need not
    // be pre-sorted by beat.
    void setPattern(std::vector<SequenceStep> steps, double lengthBeats) {
        pattern_ = std::move(steps);
        lengthBeats_ = lengthBeats;
    }

    // Appends every step whose resolved position falls within the next
    // numFrames to outEvents (does not clear outEvents first -- callers
    // collecting from multiple sequencers/tracks into one list rely on
    // that), with TriggerEvent::timestamp set to an absolute sample frame
    // matching the frame counter the caller's Engine/VoiceManager
    // independently advances by the same numFrames every call. Advances
    // this sequencer's own clock by exactly numFrames.
    void resolveEvents(std::size_t numFrames, std::vector<TriggerEvent>& outEvents) {
        if (bpm_ <= 0.0 || lengthBeats_ <= 0.0 || pattern_.empty()) {
            globalFrame_ += numFrames;
            return;
        }

        const double samplesPerBeat = sampleRate_ * 60.0 / bpm_;
        const double beatStart = currentBeat_;
        const double beatEnd = currentBeat_ + static_cast<double>(numFrames) / samplesPerBeat;

        const auto firstLoop = static_cast<int64_t>(std::floor(beatStart / lengthBeats_));
        const auto lastLoop = static_cast<int64_t>(std::floor(beatEnd / lengthBeats_));

        const std::size_t firstNewEvent = outEvents.size();
        for (int64_t loop = firstLoop; loop <= lastLoop; ++loop) {
            for (const auto& step : pattern_) {
                const double stepBeat = static_cast<double>(loop) * lengthBeats_ + step.beat;
                if (stepBeat < beatStart || stepBeat >= beatEnd) continue;

                TriggerEvent ev = step.trigger;
                const double framesFromBlockStart = (stepBeat - beatStart) * samplesPerBeat;
                ev.timestamp = globalFrame_ + static_cast<uint64_t>(std::llround(framesFromBlockStart));
                outEvents.push_back(ev);
            }
        }
        std::sort(outEvents.begin() + static_cast<std::ptrdiff_t>(firstNewEvent), outEvents.end(),
                  [](const TriggerEvent& a, const TriggerEvent& b) { return a.timestamp < b.timestamp; });

        currentBeat_ = beatEnd;
        globalFrame_ += numFrames;
    }

private:
    double sampleRate_;
    std::vector<SequenceStep> pattern_;
    double lengthBeats_ = 0.0;
    double bpm_ = 120.0;
    double currentBeat_ = 0.0;
    uint64_t globalFrame_ = 0;
};

} // namespace chilli
