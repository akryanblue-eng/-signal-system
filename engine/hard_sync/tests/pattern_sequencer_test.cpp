// Deterministic test for PatternSequencer's beat-to-sample-frame resolution.
//
//   1. Multi-loop resolve  - one big resolveEvents() call spanning several
//                             pattern repeats resolves every step's exact
//                             absolute sample-frame timestamp, in order.
//   2. Chunking invariance - resolving the same span in many small,
//                             non-aligned chunks (the real audio-callback
//                             usage pattern) produces the exact same events
//                             as one big call -- no step lost or duplicated
//                             at a chunk boundary.
//   3. Live tempo change   - changing BPM between calls takes effect
//                             immediately on the next call's beat rate,
//                             with no event loss across the change point.
//   4. Determinism         - replaying the same call sequence on a fresh
//                             instance reproduces identical events.
#include <cstdint>
#include <iostream>
#include <vector>

#include "PatternSequencer.h"
#include "TriggerEvent.h"

namespace {

chilli::SequenceStep makeStep(double beat, int padIndex, uint8_t busId) {
    chilli::SequenceStep step;
    step.beat = beat;
    step.trigger.padIndex = padIndex;
    step.trigger.busId = busId;
    step.trigger.velocity = 1.0f;
    return step;
}

bool sameEvents(const std::vector<TriggerEvent>& a, const std::vector<TriggerEvent>& b) {
    if (a.size() != b.size()) return false;
    for (std::size_t i = 0; i < a.size(); ++i) {
        if (a[i].timestamp != b[i].timestamp || a[i].padIndex != b[i].padIndex || a[i].busId != b[i].busId) {
            return false;
        }
    }
    return true;
}

} // namespace

bool runPatternSequencerTest() {
    bool allPass = true;
    constexpr double SAMPLE_RATE = 48000.0;

    // 1. Multi-loop resolve: 2-step pattern, 2-beat loop, 60 BPM -> exactly
    // 48000 samples per beat. One call spanning 4 beats (2 loops) must
    // resolve all 4 steps at exact frame positions, in order.
    {
        chilli::PatternSequencer seq(SAMPLE_RATE);
        seq.setTempo(60.0);
        std::vector<chilli::SequenceStep> pattern = {makeStep(0.0, 0, 0), makeStep(1.0, 1, 0)};
        seq.setPattern(pattern, /*lengthBeats=*/2.0);

        std::vector<TriggerEvent> events;
        seq.resolveEvents(static_cast<std::size_t>(4 * SAMPLE_RATE), events);

        bool ok = events.size() == 4;
        if (ok) {
            const uint64_t expectedFrames[4] = {0, 48000, 96000, 144000};
            const int expectedPads[4] = {0, 1, 0, 1};
            for (int i = 0; i < 4 && ok; ++i) {
                ok &= events[static_cast<std::size_t>(i)].timestamp == expectedFrames[i];
                ok &= events[static_cast<std::size_t>(i)].padIndex == expectedPads[i];
            }
        }
        std::cout << "  Multi-loop resolve (exact frame positions): " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 2. Chunking invariance: resolving the same span via many small,
    // non-block-aligned chunks must produce the exact same events as one
    // big call.
    {
        constexpr double BPM = 137.0; // deliberately non-round, doesn't divide evenly into 128-frame chunks
        constexpr double LENGTH_BEATS = 4.0;
        std::vector<chilli::SequenceStep> pattern = {makeStep(0.0, 0, 0), makeStep(1.0, 1, 1),
                                                       makeStep(1.5, 2, 0), makeStep(3.0, 3, 1)};
        constexpr std::size_t TOTAL_FRAMES = 500000;
        constexpr std::size_t CHUNK = 128;

        chilli::PatternSequencer groundTruth(SAMPLE_RATE);
        groundTruth.setTempo(BPM);
        groundTruth.setPattern(pattern, LENGTH_BEATS);
        std::vector<TriggerEvent> wholeSpanEvents;
        groundTruth.resolveEvents(TOTAL_FRAMES, wholeSpanEvents);

        chilli::PatternSequencer chunked(SAMPLE_RATE);
        chunked.setTempo(BPM);
        chunked.setPattern(pattern, LENGTH_BEATS);
        std::vector<TriggerEvent> chunkedEvents;
        std::size_t framesLeft = TOTAL_FRAMES;
        while (framesLeft > 0) {
            const std::size_t thisChunk = std::min(CHUNK, framesLeft);
            chunked.resolveEvents(thisChunk, chunkedEvents);
            framesLeft -= thisChunk;
        }

        const bool ok = !wholeSpanEvents.empty() && sameEvents(wholeSpanEvents, chunkedEvents);
        std::cout << "  Chunking invariance (block-by-block == one big call): " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 3. Live tempo change: doubling BPM between calls must double the
    // beat distance covered by the same numFrames on the very next call.
    {
        chilli::PatternSequencer seq(SAMPLE_RATE);
        seq.setTempo(60.0); // 48000 samples/beat
        std::vector<chilli::SequenceStep> pattern = {makeStep(0.0, 0, 0)};
        seq.setPattern(pattern, /*lengthBeats=*/100.0); // long loop, only care about beat-rate here

        std::vector<TriggerEvent> firstCall;
        seq.resolveEvents(24000, firstCall); // 0.5 beats at 60 BPM

        seq.setTempo(120.0); // 24000 samples/beat from here on
        std::vector<TriggerEvent> secondCall;
        seq.resolveEvents(24000, secondCall); // should now cover 1.0 beat, not 0.5

        // No step lands inside either call's window (pattern only has a hit
        // at beat 0, already consumed); this only checks the clock's beat
        // rate changed by inspecting where a step at beat 1.5 *would* fall.
        std::vector<chilli::SequenceStep> probePattern = {makeStep(1.5, 9, 0)};
        seq.setPattern(probePattern, 100.0);
        std::vector<TriggerEvent> thirdCall;
        seq.resolveEvents(24000, thirdCall); // current beat is 1.0; this window is [1.0, 2.0) at the new tempo

        const bool ok = thirdCall.size() == 1 && thirdCall[0].padIndex == 9;
        std::cout << "  Live tempo change takes effect immediately: " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 4. Determinism: replaying the same call sequence on a fresh instance
    // reproduces identical events.
    {
        auto runOnce = [&]() {
            chilli::PatternSequencer seq(SAMPLE_RATE);
            seq.setTempo(95.0);
            std::vector<chilli::SequenceStep> pattern = {makeStep(0.0, 0, 0), makeStep(0.5, 1, 1),
                                                           makeStep(2.5, 2, 0)};
            seq.setPattern(pattern, 4.0);
            std::vector<TriggerEvent> events;
            for (int b = 0; b < 50; ++b) seq.resolveEvents(128, events);
            return events;
        };

        const auto first = runOnce();
        const auto second = runOnce();
        const bool ok = !first.empty() && sameEvents(first, second);
        std::cout << "  Determinism (replay matches exactly):       " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    return allPass;
}

int main() {
    std::cout << "PatternSequencer Test Results:\n";
    const bool ok = runPatternSequencerTest();
    std::cout << (ok ? "Test: PASS" : "Test: FAIL") << "\n";
    return ok ? 0 : 1;
}
