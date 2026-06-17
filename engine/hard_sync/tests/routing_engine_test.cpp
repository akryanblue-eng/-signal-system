// Deterministic test for the bus-based RoutingEngine.
//
// Checks the properties that make a mixing console trustworthy:
//   1. Summing      - N identical voices into one bus add up correctly.
//   2. Exact gain   - a power-of-two gain (0.5) is bit-exact, not just close
//                      (this is the one case IEEE 754 float multiply
//                      guarantees zero rounding error, so it's a real
//                      bit-exactness check rather than a tolerance fudge).
//   3. Zero latency - routing introduces no frame shift/delay.
//   4. Multi-bus mix - two buses with different gains combine elementwise.
//   5. Determinism  - replaying the exact same inputs through the exact same
//                      sequence of calls reproduces a bit-identical output.
#include <cmath>
#include <cstring>
#include <iostream>
#include <vector>

#include "RoutingEngine.h"

namespace {

constexpr double PI = 3.14159265358979323846;
constexpr std::size_t BLOCK_SIZE = 128;

std::vector<float> makeSine(double freqHz, double rate, std::size_t numSamples) {
    std::vector<float> out(numSamples);
    for (std::size_t i = 0; i < numSamples; ++i) {
        out[i] = static_cast<float>(std::sin(2.0 * PI * freqHz * static_cast<double>(i) / rate));
    }
    return out;
}

} // namespace

bool runRoutingEngineTest() {
    bool allPass = true;

    // 1. Summing: 10 identical voices into one bus.
    {
        chilli::RoutingEngine<1> routing(BLOCK_SIZE);
        auto sine = makeSine(440.0, 48000.0, BLOCK_SIZE);

        constexpr int kVoices = 10;
        for (int v = 0; v < kVoices; ++v) {
            routing.bus(0).accumulate(sine.data(), BLOCK_SIZE);
        }
        routing.process();

        bool summingOk = true;
        for (std::size_t i = 0; i < BLOCK_SIZE; ++i) {
            const float expected = sine[i] * static_cast<float>(kVoices);
            if (std::abs(routing.mainOut()[i] - expected) > 1e-4f) {
                summingOk = false;
                break;
            }
        }
        std::cout << "  Summing (10 voices == 10x signal): " << (summingOk ? "PASS" : "FAIL") << "\n";
        allPass &= summingOk;
    }

    // 2. Exact gain: 0.5 is a power of two, so the multiply has zero rounding
    // error in IEEE 754 -- this is checked with == on purpose, not a tolerance.
    {
        chilli::RoutingEngine<1> routing(BLOCK_SIZE);
        auto sine = makeSine(220.0, 48000.0, BLOCK_SIZE);
        routing.bus(0).accumulate(sine.data(), BLOCK_SIZE);
        routing.bus(0).gain = 0.5f;
        routing.process();

        bool gainExact = true;
        for (std::size_t i = 0; i < BLOCK_SIZE; ++i) {
            if (routing.mainOut()[i] != sine[i] * 0.5f) {
                gainExact = false;
                break;
            }
        }
        std::cout << "  Exact gain (0.5x is bit-exact):     " << (gainExact ? "PASS" : "FAIL") << "\n";
        allPass &= gainExact;
    }

    // 3. Zero latency: an impulse at frame k must appear at frame k in mainOut,
    // with nothing before it and nothing smeared after it.
    {
        chilli::RoutingEngine<1> routing(BLOCK_SIZE);
        std::vector<float> impulse(BLOCK_SIZE, 0.0f);
        constexpr std::size_t kImpulseFrame = 37;
        impulse[kImpulseFrame] = 1.0f;

        routing.bus(0).accumulate(impulse.data(), BLOCK_SIZE);
        routing.process();

        bool zeroLatency = routing.mainOut()[kImpulseFrame] == 1.0f;
        for (std::size_t i = 0; i < BLOCK_SIZE && zeroLatency; ++i) {
            if (i != kImpulseFrame && routing.mainOut()[i] != 0.0f) zeroLatency = false;
        }
        std::cout << "  Zero latency (impulse stays at frame 37): " << (zeroLatency ? "PASS" : "FAIL") << "\n";
        allPass &= zeroLatency;
    }

    // 4. Multi-bus mix: two buses, different gains, combined elementwise.
    {
        chilli::RoutingEngine<2> routing(BLOCK_SIZE);
        auto sineA = makeSine(440.0, 48000.0, BLOCK_SIZE);
        auto sineB = makeSine(660.0, 48000.0, BLOCK_SIZE);

        routing.bus(0).accumulate(sineA.data(), BLOCK_SIZE);
        routing.bus(0).gain = 0.5f;
        routing.bus(1).accumulate(sineB.data(), BLOCK_SIZE);
        routing.bus(1).gain = 0.25f;
        routing.process();

        bool mixOk = true;
        for (std::size_t i = 0; i < BLOCK_SIZE; ++i) {
            const float expected = sineA[i] * 0.5f + sineB[i] * 0.25f;
            if (routing.mainOut()[i] != expected) { // both gains are powers of two -> bit-exact
                mixOk = false;
                break;
            }
        }
        std::cout << "  Multi-bus mix (bit-exact elementwise sum): " << (mixOk ? "PASS" : "FAIL") << "\n";
        allPass &= mixOk;
    }

    // 5. Determinism: replaying the same call sequence reproduces bit-identical output.
    {
        auto runOnce = [&]() {
            chilli::RoutingEngine<3> routing(BLOCK_SIZE);
            auto sineA = makeSine(440.0, 48000.0, BLOCK_SIZE);
            auto sineB = makeSine(660.0, 48000.0, BLOCK_SIZE);
            auto sineC = makeSine(880.0, 48000.0, BLOCK_SIZE);

            routing.bus(0).accumulate(sineA.data(), BLOCK_SIZE);
            routing.bus(0).accumulate(sineB.data(), BLOCK_SIZE); // two voices sharing bus 0
            routing.bus(1).accumulate(sineC.data(), BLOCK_SIZE);
            routing.bus(1).gain = 0.5f;
            routing.process();
            return routing.mainOut();
        };

        const auto first = runOnce();
        const auto second = runOnce();
        const bool deterministic =
            first.size() == second.size() &&
            std::memcmp(first.data(), second.data(), first.size() * sizeof(float)) == 0;
        std::cout << "  Determinism (replay is bit-identical): " << (deterministic ? "PASS" : "FAIL") << "\n";
        allPass &= deterministic;
    }

    return allPass;
}

int main() {
    std::cout << "RoutingEngine Test Results:\n";
    const bool ok = runRoutingEngineTest();
    std::cout << (ok ? "Test: PASS" : "Test: FAIL") << "\n";
    return ok ? 0 : 1;
}
