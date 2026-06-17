// Minimal Hard-Sync test harness for 808 voice stealing.
//
// Simulates a fixed-sample-rate audio callback firing two overlapping 808
// triggers on the same voice slot (one at frame 0, one at frame 64 inside a
// 128-frame block) and checks:
//   1. Zero overlap   - the first hit contributes no audio after the steal.
//   2. Timing         - the second hit's attack starts at exactly sample 64.
//   3. Transient       - both hits use direct (non-interpolated) sample access
//                        during their bypass window, and the crossfade out of
//                        that window introduces no discontinuity.
//
// No external dependencies; self-contained besides the three engine headers.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>

#include "AtomicRingBuffer.h"
#include "TriggerEvent.h"
#include "Voice808State.h"

namespace {

constexpr double SAMPLE_RATE = 48000.0;
constexpr int BLOCK_SIZE = 128;
constexpr int TOTAL_BLOCKS = 8;
constexpr int TOTAL_FRAMES = BLOCK_SIZE * TOTAL_BLOCKS;
constexpr size_t QUEUE_CAPACITY = 512;
constexpr size_t MAX_VOICES = 64;
constexpr uint32_t CROSSFADE_SAMPLES = 32;
constexpr double PI = 3.14159265358979323846;

} // namespace

struct TestEngine {
    std::array<Voice808State, MAX_VOICES> voicePool{};
    AtomicRingBuffer<TriggerEvent, QUEUE_CAPACITY> queue_;
    double sampleRate = SAMPLE_RATE;
    uint64_t globalFrame = 0;

    void pushTrigger(const TriggerEvent& ev) { queue_.push(ev); }

    // Renders one block. Alongside the audio output, records which voice
    // "generation" produced each sample and whether the direct-access path was
    // used, so the test can verify steal/timing/transient behavior exactly
    // rather than inferring it from raw amplitude.
    void renderBlock(float* output, uint32_t* generationOut, bool* directOut) {
        std::memset(output, 0, BLOCK_SIZE * sizeof(float));
        std::fill(generationOut, generationOut + BLOCK_SIZE, 0u);
        std::fill(directOut, directOut + BLOCK_SIZE, false);

        struct Pending {
            uint32_t frame;
            TriggerEvent ev;
        };
        std::array<Pending, QUEUE_CAPACITY> pending{};
        size_t pendingCount = 0;

        TriggerEvent ev;
        while (pendingCount < pending.size() && queue_.pop(ev)) {
            const uint32_t frameInBlock = (ev.timestamp > globalFrame)
                ? static_cast<uint32_t>(ev.timestamp - globalFrame)
                : 0;
            if (frameInBlock >= static_cast<uint32_t>(BLOCK_SIZE)) {
                continue; // belongs to a later block; out of scope for this harness
            }
            pending[pendingCount++] = Pending{frameInBlock, ev};
        }
        std::sort(pending.begin(), pending.begin() + pendingCount,
                  [](const Pending& a, const Pending& b) { return a.frame < b.frame; });

        // Render in segments split at each trigger's frame so a mid-block steal
        // takes effect exactly on its target sample instead of at the next
        // block boundary.
        uint32_t cursor = 0;
        size_t idx = 0;
        while (cursor < static_cast<uint32_t>(BLOCK_SIZE)) {
            while (idx < pendingCount && pending[idx].frame <= cursor) {
                voicePool[pending[idx].ev.padIndex].init(pending[idx].ev, 0, sampleRate);
                ++idx;
            }
            const uint32_t segmentEnd =
                (idx < pendingCount) ? pending[idx].frame : static_cast<uint32_t>(BLOCK_SIZE);
            renderSegment(output, generationOut, directOut, cursor, segmentEnd);
            cursor = segmentEnd;
        }

        globalFrame += BLOCK_SIZE;
    }

    void renderSegment(float* output, uint32_t* generationOut, bool* directOut,
                        uint32_t start, uint32_t end) {
        for (auto& voice : voicePool) {
            if (!voice.active) continue;
            for (uint32_t i = start; i < end; ++i) {
                voice.updateState(sampleRate);

                if (voice.glideActive) {
                    voice.pitchCurrent += (voice.pitchTarget - voice.pitchCurrent) * voice.pitchRate;
                }

                const float remaining = static_cast<float>(voice.transientBypassSamples) - voice.sampleOffset;
                float sample;
                bool usedDirect = false;

                if (voice.transientBypass && remaining > static_cast<float>(CROSSFADE_SAMPLES)) {
                    sample = getDirectSample(voice.sampleOffset);
                    usedDirect = true;
                } else if (voice.transientBypass && remaining > 0.0f) {
                    const float w = 1.0f - (remaining / static_cast<float>(CROSSFADE_SAMPLES));
                    const float direct = getDirectSample(voice.sampleOffset);
                    const float interp = getInterpolatedSample(voice.sampleOffset);
                    sample = direct * (1.0f - w) + interp * w;
                } else {
                    sample = getInterpolatedSample(voice.sampleOffset);
                }

                output[i] += sample * voice.aLevel;
                generationOut[i] = voice.generation;
                directOut[i] = usedDirect;

                voice.sampleOffset += getStepSize(voice.pitchCurrent);
                if (voice.sampleOffset >= static_cast<float>(voice.sampleLength)) {
                    voice.sampleOffset = std::fmod(voice.sampleOffset, static_cast<float>(voice.sampleLength));
                }
            }
        }
    }

    // --- Stub sample source (no real 808 sample is needed to test timing/steal logic) ---

    static float getDirectSample(float offset) {
        // Phase-offset sine so the stub transient is non-zero at offset 0; a bare
        // sin(0) would mask the "does sample 64 actually carry signal" check.
        constexpr double kPhase = 0.6;
        return static_cast<float>(std::sin(2.0 * PI * 0.05 * static_cast<double>(offset) + kPhase));
    }

    static float getInterpolatedSample(float offset) {
        const uint32_t i0 = static_cast<uint32_t>(offset);
        const float frac = offset - static_cast<float>(i0);
        const float s0 = getDirectSample(static_cast<float>(i0));
        const float s1 = getDirectSample(static_cast<float>(i0 + 1));
        return s0 * (1.0f - frac) + s1 * frac;
    }

    static float getStepSize(float pitchOctaves) {
        return std::pow(2.0f, pitchOctaves);
    }
};

namespace {

TriggerEvent makeHit(uint64_t timestamp) {
    TriggerEvent ev{};
    ev.timestamp = timestamp;
    ev.padIndex = 0; // same slot for both hits -> the second one steals the first
    ev.velocity = 1.0f;
    ev.pitchStartOctaves = -0.25f;
    ev.pitchTargetOctaves = 0.0f;
    ev.attackSec = 0.005f;
    ev.glideSec = 0.12f;
    ev.transientBypassSamples = 256;
    ev.sampleLength = 4096;
    return ev;
}

} // namespace

bool runHardSyncTest() {
    TestEngine engine;
    std::array<float, TOTAL_FRAMES> output{};
    std::array<uint32_t, TOTAL_FRAMES> generation{};
    std::array<bool, TOTAL_FRAMES> usedDirect{};

    engine.pushTrigger(makeHit(0));  // first 808, frame 0
    engine.pushTrigger(makeHit(64)); // steals the same slot at frame 64 (mid-block)

    for (int b = 0; b < TOTAL_BLOCKS; ++b) {
        engine.renderBlock(output.data() + b * BLOCK_SIZE,
                            generation.data() + b * BLOCK_SIZE,
                            usedDirect.data() + b * BLOCK_SIZE);
    }

    // 1. Zero overlap: once the steal happens, the first hit (generation 1) must
    // never contribute another sample, anywhere in the rendered output.
    const auto gen1Count = std::count(generation.begin(), generation.end(), 1u);
    bool zeroOverlap = (gen1Count == 64); // exactly frames [0, 64)
    for (int i = 64; i < TOTAL_FRAMES; ++i) {
        if (generation[i] == 1) {
            zeroOverlap = false;
            break;
        }
    }

    // 2. Correct timing: generation 1 owns sample 63, generation 2 owns sample 64,
    // and that sample actually carries signal (the attack has started, not silence).
    const bool correctTiming =
        generation[63] == 1 && generation[64] == 2 && std::abs(output[64]) > 1e-6f;

    // 3. Transient integrity:
    //   a) every sample of the (truncated) first hit used direct access -- it never
    //      lived long enough to reach the crossfade, so it must stay 100% direct.
    bool firstHitAllDirect = true;
    for (int i = 0; i < 64; ++i) {
        if (!usedDirect[i]) {
            firstHitAllDirect = false;
            break;
        }
    }
    //   b) the second hit is direct for its bypass window minus the crossfade tail.
    const int hit2Start = 64;
    const int hit2DirectEnd = hit2Start + static_cast<int>(256 - CROSSFADE_SAMPLES); // local offset 224
    bool secondHitDirect = true;
    for (int i = hit2Start; i < hit2DirectEnd; ++i) {
        if (!usedDirect[i]) {
            secondHitDirect = false;
            break;
        }
    }
    //   c) the crossfade out of the bypass window doesn't click (no sample-to-sample
    //      jump larger than the underlying stub waveform could ever produce on its own).
    bool crossfadeClean = true;
    const int crossfadeStart = hit2DirectEnd;
    const int crossfadeEnd = hit2Start + 256; // local offset 320
    for (int i = crossfadeStart; i < crossfadeEnd && i + 1 < TOTAL_FRAMES; ++i) {
        if (std::abs(output[i + 1] - output[i]) > 0.5f) {
            crossfadeClean = false;
            break;
        }
    }
    const bool transientIntegrity = firstHitAllDirect && secondHitDirect && crossfadeClean;

    std::cout << "Hard-Sync Test Results:\n";
    std::cout << "  Zero overlap after steal:        " << (zeroOverlap ? "PASS" : "FAIL") << "\n";
    std::cout << "  Correct timing at frame 64:      " << (correctTiming ? "PASS" : "FAIL") << "\n";
    std::cout << "  Transient integrity (direct/xfd): " << (transientIntegrity ? "PASS" : "FAIL") << "\n";

    return zeroOverlap && correctTiming && transientIntegrity;
}

int main() {
    const bool ok = runHardSyncTest();
    std::cout << (ok ? "Test: PASS" : "Test: FAIL") << "\n";
    return ok ? 0 : 1;
}
