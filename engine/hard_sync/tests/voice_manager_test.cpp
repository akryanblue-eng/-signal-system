// Deterministic test for VoiceManager's bus wiring on top of RoutingEngine.
//
// Checks the properties that make trigger-time, immutable bus assignment
// trustworthy:
//   1. Honored      - a voice triggered onto bus 1 contributes only to bus 1.
//   2. Immutable     - a mid-block steal of the same pad onto a DIFFERENT bus
//                      splits cleanly at the exact frame: samples before the
//                      steal land in the old bus, samples from the steal
//                      onward land in the new bus, with no bleed either way.
//   3. Co-mixing     - two different voices assigned to the same bus sum
//                      together (tolerance-based: repeated float addition).
//   4. Determinism   - replaying the same trigger sequence reproduces a
//                      bit-identical bus/main output.
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>

#include "RoutingEngine.h"
#include "TriggerEvent.h"
#include "VoiceManager.h"

namespace {

constexpr double SAMPLE_RATE = 48000.0;
constexpr uint32_t BLOCK_SIZE = 128;

// Distinct, never-zero values so "this bus received signal" checks can't be
// confused with "this voice's data legitimately contains a zero".
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
    ev.pitchStartOctaves = 0.0f;
    ev.pitchTargetOctaves = 0.0f;
    ev.attackSec = 0.0f;             // aLevel reaches 1.0 on the very first sample
    ev.glideSec = 0.0f;
    ev.transientBypassSamples = 0;   // pure interpolated playback -- isolates routing from transient logic
    return ev;
}

} // namespace

bool runVoiceManagerTest() {
    bool allPass = true;
    auto rampA = makeRamp(256);
    auto rampB = makeRamp(256);

    // 1. Trigger-time bus assignment is honored.
    {
        chilli::VoiceManager<8, 2> vm(BLOCK_SIZE);
        chilli::RoutingEngine<2> routing(BLOCK_SIZE);
        vm.pushTrigger(makeHit(0, 0, /*busId=*/1, rampA.data(), static_cast<uint32_t>(rampA.size())));
        routing.clearBuses();
        vm.renderBlock(routing, SAMPLE_RATE);
        routing.process();

        bool bus0Silent = true;
        for (float s : routing.bus(0).buffer) {
            if (s != 0.0f) { bus0Silent = false; break; }
        }
        bool bus1HasSignal = false;
        for (float s : routing.bus(1).buffer) {
            if (s != 0.0f) { bus1HasSignal = true; break; }
        }

        const bool ok = bus0Silent && bus1HasSignal;
        std::cout << "  Trigger-time bus assignment honored: " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 2. Mid-block steal onto a different bus splits at the exact frame.
    {
        chilli::VoiceManager<8, 2> vm(BLOCK_SIZE);
        chilli::RoutingEngine<2> routing(BLOCK_SIZE);
        vm.pushTrigger(makeHit(0, 0, /*busId=*/0, rampA.data(), static_cast<uint32_t>(rampA.size())));
        vm.pushTrigger(makeHit(64, 0, /*busId=*/1, rampA.data(), static_cast<uint32_t>(rampA.size())));
        routing.clearBuses();
        vm.renderBlock(routing, SAMPLE_RATE);
        routing.process();

        bool ok = true;
        for (uint32_t i = 0; i < 64; ++i) {
            if (routing.bus(0).buffer[i] == 0.0f) ok = false; // first hit present in bus 0
            if (routing.bus(1).buffer[i] != 0.0f) ok = false; // not yet present in bus 1
        }
        for (uint32_t i = 64; i < BLOCK_SIZE; ++i) {
            if (routing.bus(1).buffer[i] == 0.0f) ok = false; // second hit present in bus 1
            if (routing.bus(0).buffer[i] != 0.0f) ok = false; // bus 0 receives nothing after the steal
        }
        std::cout << "  Mid-block steal to a different bus splits exactly: " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 3. Two voices sharing one bus sum together.
    {
        chilli::VoiceManager<8, 2> vm(BLOCK_SIZE);
        chilli::RoutingEngine<2> routing(BLOCK_SIZE);
        vm.pushTrigger(makeHit(0, 0, /*busId=*/0, rampA.data(), static_cast<uint32_t>(rampA.size())));
        vm.pushTrigger(makeHit(0, 1, /*busId=*/0, rampB.data(), static_cast<uint32_t>(rampB.size())));
        routing.clearBuses();
        vm.renderBlock(routing, SAMPLE_RATE);
        routing.process();

        bool ok = true;
        for (uint32_t i = 0; i < BLOCK_SIZE; ++i) {
            const float expected = rampA[i] + rampB[i]; // unity pitch -> exact sample reads, no interpolation blend
            if (std::abs(routing.mainOut()[i] - expected) > 1e-5f) { ok = false; break; }
        }
        std::cout << "  Two voices on one bus sum together:  " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 4. Determinism: replaying the same trigger sequence reproduces
    // bit-identical output.
    {
        auto runOnce = [&]() {
            chilli::VoiceManager<8, 2> vm(BLOCK_SIZE);
            chilli::RoutingEngine<2> routing(BLOCK_SIZE);
            vm.pushTrigger(makeHit(0, 0, /*busId=*/0, rampA.data(), static_cast<uint32_t>(rampA.size())));
            vm.pushTrigger(makeHit(64, 1, /*busId=*/1, rampB.data(), static_cast<uint32_t>(rampB.size())));
            routing.clearBuses();
            vm.renderBlock(routing, SAMPLE_RATE);
            routing.process();
            return routing.mainOut();
        };

        const auto first = runOnce();
        const auto second = runOnce();
        const bool ok = first.size() == second.size() &&
            std::memcmp(first.data(), second.data(), first.size() * sizeof(float)) == 0;
        std::cout << "  Determinism (replay is bit-identical): " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    return allPass;
}

int main() {
    std::cout << "VoiceManager Test Results:\n";
    const bool ok = runVoiceManagerTest();
    std::cout << (ok ? "Test: PASS" : "Test: FAIL") << "\n";
    return ok ? 0 : 1;
}
