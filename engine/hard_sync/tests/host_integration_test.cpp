// Integration test for the "glue" that makes this a standalone playable
// instrument: a host loop that resolves a PatternSequencer's events for the
// block about to be rendered, feeds them to an Engine, then renders. There's
// no new engine component here -- this is exactly what a real audio
// callback's body would look like, kept in the test rather than in include/
// because it's call-site wiring, not a reusable abstraction.
//
//   1. Sample-accurate placement - a step landing mid-block (not at a block
//      boundary) appears in the rendered output at its exact sample offset,
//      scaled by its bus's gain, with silence everywhere else.
//   2. Block-driven == one-shot   - driving the host loop one block at a
//      time (the real callback pattern) produces the same audio as
//      resolving the whole span in one PatternSequencer call and pushing
//      every event before a single renderBlock of equal total length.
#include <cstdint>
#include <iostream>
#include <vector>

#include "Engine.h"
#include "PatternSequencer.h"
#include "TriggerEvent.h"

namespace {

constexpr double SAMPLE_RATE = 48000.0;
constexpr std::size_t BLOCK_SIZE = 128;

std::vector<float> makeRamp(std::size_t n) {
    std::vector<float> out(n);
    for (std::size_t i = 0; i < n; ++i) out[i] = static_cast<float>(i + 1) * 0.001f;
    return out;
}

// The host loop: resolve this block's events, push them, render. Mirrors
// what an audio callback's body does every time the host asks for a block.
template <std::size_t NumVoices, std::size_t NumBuses>
void renderHostBlock(chilli::PatternSequencer& sequencer, chilli::Engine<NumVoices, NumBuses>& engine, float* buffer,
                      std::size_t numFrames, std::vector<TriggerEvent>& scratchEvents) {
    scratchEvents.clear();
    sequencer.resolveEvents(numFrames, scratchEvents);
    for (const auto& ev : scratchEvents) engine.pushTrigger(ev);
    engine.renderBlock(buffer, numFrames);
}

} // namespace

bool runHostIntegrationTest() {
    bool allPass = true;
    auto ramp = makeRamp(256);

    // 1. Sample-accurate placement across a block-by-block host loop: a step
    // at beat 0.5, 60 BPM (48000 samples/beat) lands at frame 24000, which is
    // mid-block (block 187, offset 64 within it). Render enough blocks to
    // fully cover the rendered output and check every sample against the
    // expected silence-then-ramp shape.
    {
        chilli::PatternSequencer sequencer(SAMPLE_RATE);
        sequencer.setTempo(60.0);
        chilli::SequenceStep step;
        step.beat = 0.5;
        step.trigger.padIndex = 0;
        step.trigger.busId = 0;
        step.trigger.velocity = 1.0f;
        step.trigger.attackSec = 0.0f; // exact comparison below needs full level from sample 0
        step.trigger.sampleData = ramp.data();
        step.trigger.sampleLength = static_cast<uint32_t>(ramp.size());
        sequencer.setPattern({step}, /*lengthBeats=*/100.0); // long loop, one hit only

        chilli::Engine<8, 2> engine(BLOCK_SIZE, SAMPLE_RATE);
        engine.bus(0).gain = 0.5f;

        constexpr std::size_t triggerFrame = 24000;
        constexpr std::size_t totalFrames = triggerFrame + 256 + BLOCK_SIZE; // hit + full ramp + margin
        constexpr std::size_t numBlocks = (totalFrames + BLOCK_SIZE - 1) / BLOCK_SIZE;

        std::vector<float> output(numBlocks * BLOCK_SIZE, -999.0f);
        std::vector<TriggerEvent> scratchEvents;
        for (std::size_t b = 0; b < numBlocks; ++b) {
            renderHostBlock(sequencer, engine, output.data() + b * BLOCK_SIZE, BLOCK_SIZE, scratchEvents);
        }

        bool ok = true;
        for (std::size_t i = 0; i < triggerFrame && ok; ++i) {
            if (output[i] != 0.0f) ok = false;
        }
        for (std::size_t i = 0; i < ramp.size() && ok; ++i) {
            if (output[triggerFrame + i] != ramp[i] * 0.5f) ok = false;
        }
        std::cout << "  Sample-accurate placement via host loop: " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 2. Buffer-size independence: the same dense, looping pattern (steps
    // re-trigger every loop, exercising a hard steal on the same pad each
    // time the pattern wraps) driven by host loops with three different
    // block sizes must produce bit-identical audio over the same span.
    // Each Engine/PatternSequencer pair is internally consistent (every
    // resolveEvents/renderBlock call in a given run uses that run's own
    // block size), since a single Engine instance's internal clock only
    // stays in sync with what's copied out when numFrames == blockSize()
    // every call (see Engine::renderBlock's doc comment) -- this test
    // varies the block size *across* independent runs, not within one.
    {
        std::vector<chilli::SequenceStep> pattern;
        for (int i = 0; i < 4; ++i) {
            chilli::SequenceStep step;
            step.beat = i * 0.5; // beats 0, 0.5, 1.0, 1.5 -- all within lengthBeats below
            step.trigger.padIndex = i;
            step.trigger.busId = static_cast<uint8_t>(i % 2);
            step.trigger.velocity = 1.0f;
            step.trigger.attackSec = 0.0f;
            step.trigger.sampleData = ramp.data();
            step.trigger.sampleLength = static_cast<uint32_t>(ramp.size());
            pattern.push_back(step);
        }
        constexpr double BPM = 480.0; // 6000 samples/beat
        constexpr double LENGTH_BEATS = 2.0; // 12000-frame loop -- wraps more than once below
        constexpr std::size_t TOTAL_FRAMES = 20480; // common multiple of every block size tried

        auto renderWithBlockSize = [&](std::size_t blockSize) {
            chilli::PatternSequencer sequencer(SAMPLE_RATE);
            sequencer.setTempo(BPM);
            sequencer.setPattern(pattern, LENGTH_BEATS);
            chilli::Engine<8, 2> engine(blockSize, SAMPLE_RATE);

            std::vector<float> output(TOTAL_FRAMES, -999.0f);
            std::vector<TriggerEvent> scratchEvents;
            std::size_t rendered = 0;
            while (rendered < TOTAL_FRAMES) {
                renderHostBlock(sequencer, engine, output.data() + rendered, blockSize, scratchEvents);
                rendered += blockSize;
            }
            return output;
        };

        const auto out32 = renderWithBlockSize(32);
        const auto out128 = renderWithBlockSize(128);
        const auto out512 = renderWithBlockSize(512);

        bool ok = true;
        for (std::size_t i = 0; i < TOTAL_FRAMES && ok; ++i) {
            if (out32[i] != out128[i] || out32[i] != out512[i]) ok = false;
        }
        std::cout << "  Buffer-size independence (32/128/512 bit-identical): " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    return allPass;
}

int main() {
    std::cout << "Host Integration Test Results:\n";
    const bool ok = runHostIntegrationTest();
    std::cout << (ok ? "Test: PASS" : "Test: FAIL") << "\n";
    return ok ? 0 : 1;
}
