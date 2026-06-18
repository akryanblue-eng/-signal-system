// Deterministic test for the Engine wrapper -- the single class an audio
// callback is meant to touch. Verifies that wrapping VoiceManager +
// RoutingEngine behind one renderBlock() call doesn't change behavior and
// doesn't leak sequencing bugs (forgetting to clear buses, mixing down at
// the wrong time, etc.):
//   1. Single trigger    - lands in output, scaled by its bus's gain.
//   2. Co-mixing         - two voices on one bus sum together, same result
//                           as calling VoiceManager/RoutingEngine directly.
//   3. Partial copy      - requesting fewer frames than blockSize() copies
//                           only a truncated prefix, never over-reads.
//   4. Determinism       - replaying the same trigger sequence across two
//                           fresh Engine instances is bit-identical.
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>

#include "Engine.h"
#include "TriggerEvent.h"

namespace {

constexpr double SAMPLE_RATE = 48000.0;
constexpr uint32_t BLOCK_SIZE = 128;

std::vector<float> makeRamp(std::size_t n) {
    std::vector<float> out(n);
    for (std::size_t i = 0; i < n; ++i) {
        out[i] = static_cast<float>(i + 1) * 0.001f;
    }
    return out;
}

TriggerEvent makeHit(uint64_t timestamp, int padIndex, uint8_t busId, const float* data, uint32_t length) {
    TriggerEvent ev{};
    ev.timestamp = timestamp;
    ev.padIndex = padIndex;
    ev.busId = busId;
    ev.sampleData = data;
    ev.sampleLength = length;
    ev.velocity = 1.0f;
    ev.attackSec = 0.0f;
    ev.glideSec = 0.0f;
    ev.transientBypassSamples = 0;
    return ev;
}

} // namespace

bool runEngineTest() {
    bool allPass = true;
    auto rampA = makeRamp(256);
    auto rampB = makeRamp(256);

    // 1. Single trigger lands in output, scaled by its bus's gain (0.5x,
    // exact since it's a power of two).
    {
        chilli::Engine<8, 2> engine(BLOCK_SIZE, SAMPLE_RATE);
        engine.bus(0).gain = 0.5f;
        engine.pushTrigger(makeHit(0, 0, /*busId=*/0, rampA.data(), static_cast<uint32_t>(rampA.size())));

        std::vector<float> output(BLOCK_SIZE, 0.0f);
        engine.renderBlock(output.data(), BLOCK_SIZE);

        bool ok = true;
        for (uint32_t i = 0; i < BLOCK_SIZE; ++i) {
            if (output[i] != rampA[i] * 0.5f) { ok = false; break; }
        }
        std::cout << "  Single trigger respects bus gain (exact): " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 2. Two voices on one bus sum together.
    {
        chilli::Engine<8, 2> engine(BLOCK_SIZE, SAMPLE_RATE);
        engine.pushTrigger(makeHit(0, 0, /*busId=*/0, rampA.data(), static_cast<uint32_t>(rampA.size())));
        engine.pushTrigger(makeHit(0, 1, /*busId=*/0, rampB.data(), static_cast<uint32_t>(rampB.size())));

        std::vector<float> output(BLOCK_SIZE, 0.0f);
        engine.renderBlock(output.data(), BLOCK_SIZE);

        bool ok = true;
        for (uint32_t i = 0; i < BLOCK_SIZE; ++i) {
            const float expected = rampA[i] + rampB[i];
            if (std::abs(output[i] - expected) > 1e-5f) { ok = false; break; }
        }
        std::cout << "  Two voices on one bus sum together:       " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 3. Requesting fewer frames than blockSize() copies a truncated prefix
    // and never writes past it.
    {
        constexpr uint32_t kPartial = 40;
        chilli::Engine<8, 2> engine(BLOCK_SIZE, SAMPLE_RATE);
        engine.pushTrigger(makeHit(0, 0, /*busId=*/0, rampA.data(), static_cast<uint32_t>(rampA.size())));

        std::vector<float> output(BLOCK_SIZE, -999.0f); // sentinel past the requested prefix
        engine.renderBlock(output.data(), kPartial);

        bool prefixCorrect = true;
        for (uint32_t i = 0; i < kPartial; ++i) {
            if (output[i] != rampA[i]) { prefixCorrect = false; break; }
        }
        bool tailUntouched = true;
        for (uint32_t i = kPartial; i < BLOCK_SIZE; ++i) {
            if (output[i] != -999.0f) { tailUntouched = false; break; }
        }
        const bool ok = prefixCorrect && tailUntouched;
        std::cout << "  Partial numFrames copies only the prefix: " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 4. Determinism: two fresh engines replaying the same trigger sequence
    // (including a mid-block steal) produce bit-identical output.
    {
        auto runOnce = [&]() {
            chilli::Engine<8, 2> engine(BLOCK_SIZE, SAMPLE_RATE);
            engine.pushTrigger(makeHit(0, 0, /*busId=*/0, rampA.data(), static_cast<uint32_t>(rampA.size())));
            engine.pushTrigger(makeHit(64, 0, /*busId=*/1, rampB.data(), static_cast<uint32_t>(rampB.size())));
            std::vector<float> output(BLOCK_SIZE, 0.0f);
            engine.renderBlock(output.data(), BLOCK_SIZE);
            return output;
        };

        const auto first = runOnce();
        const auto second = runOnce();
        const bool ok = first.size() == second.size() &&
            std::memcmp(first.data(), second.data(), first.size() * sizeof(float)) == 0;
        std::cout << "  Determinism (replay is bit-identical):    " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    return allPass;
}

int main() {
    std::cout << "Engine Test Results:\n";
    const bool ok = runEngineTest();
    std::cout << (ok ? "Test: PASS" : "Test: FAIL") << "\n";
    return ok ? 0 : 1;
}
