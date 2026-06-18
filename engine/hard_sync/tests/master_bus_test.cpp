// Deterministic test for MasterBus's tanh soft-saturation transfer
// function.
//
//   1. Bounded above   - a ramp from 0.0 to 2.0 never exceeds ceiling, and
//                         gets arbitrarily close to it as input grows.
//   2. Symmetric        - process(-x) == -process(x) for every x: tanh's
//                         oddness means positive/negative excursions
//                         saturate identically with no separate logic.
//   3. Near-linear quiet signal - for |x| much smaller than ceiling/drive,
//                         output is within a tight tolerance of the
//                         unsaturated value, so quiet material is barely
//                         colored.
//   4. Drive increases saturation - for a fixed input inside the curved
//                         region, raising drive moves the output strictly
//                         closer to ceiling.
//   5. processBlock matches per-sample process() - the block helper is
//                         just process() applied per sample, in place.
#include <cmath>
#include <iostream>
#include <vector>

#include "MasterBus.h"

namespace {

bool nearlyEqual(float a, float b, float tol) { return std::abs(a - b) <= tol; }

} // namespace

bool runMasterBusTest() {
    bool allPass = true;

    // 1. Bounded above: ramp 0.0 -> 2.0 stays within (-ceiling, ceiling],
    // and gets close to ceiling as input grows large.
    {
        chilli::MasterBus bus(1.0f);
        bool boundedEverywhere = true;
        for (int i = 0; i <= 200; ++i) {
            const float x = static_cast<float>(i) / 100.0f; // 0.0 .. 2.0
            const float y = bus.process(x);
            if (y < 0.0f || y > 1.0f) boundedEverywhere = false;
        }
        const float farOut = bus.process(1000.0f);
        const bool approachesCeiling = nearlyEqual(farOut, 1.0f, 1e-4f);
        const bool ok = boundedEverywhere && approachesCeiling;
        std::cout << "  Bounded above by ceiling, approaches it for large input: " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 2. Symmetric: process(-x) == -process(x).
    {
        chilli::MasterBus bus(1.0f);
        bus.setDrive(2.0f);
        bool ok = true;
        for (float x : {0.0f, 0.1f, 0.5f, 1.0f, 2.0f, 10.0f}) {
            const float pos = bus.process(x);
            const float neg = bus.process(-x);
            if (!nearlyEqual(pos, -neg, 1e-6f)) ok = false;
        }
        std::cout << "  Symmetric for positive/negative input:    " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 3. Near-linear for quiet signals: at drive 1, ceiling 1, x = 0.001 is
    // far inside the linear region of tanh, so output should be within a
    // tight tolerance of the unsaturated input.
    {
        chilli::MasterBus bus(1.0f);
        const float x = 0.001f;
        const float y = bus.process(x);
        const bool ok = nearlyEqual(y, x, 1e-6f);
        std::cout << "  Quiet signal passes through near-unchanged: " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 4. Raising drive pushes the same input strictly closer to ceiling
    // (more saturation) inside the curved region.
    {
        chilli::MasterBus bus(1.0f);
        constexpr float x = 0.8f;
        bus.setDrive(1.0f);
        const float lowDrive = bus.process(x);
        bus.setDrive(4.0f);
        const float highDrive = bus.process(x);
        const bool ok = highDrive > lowDrive && highDrive < 1.0f;
        std::cout << "  Higher drive saturates the same input harder: " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 5. processBlock applies process() per sample, in place.
    {
        chilli::MasterBus bus(1.0f);
        bus.setDrive(3.0f);
        std::vector<float> samples = {-2.0f, -0.3f, 0.0f, 0.3f, 2.0f};
        std::vector<float> expected;
        for (float s : samples) expected.push_back(bus.process(s));

        std::vector<float> buffer = {-2.0f, -0.3f, 0.0f, 0.3f, 2.0f};
        bus.processBlock(buffer.data(), buffer.size());

        bool ok = true;
        for (std::size_t i = 0; i < buffer.size(); ++i) {
            if (buffer[i] != expected[i]) ok = false;
        }
        std::cout << "  processBlock matches per-sample process():  " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    return allPass;
}

int main() {
    std::cout << "MasterBus Test Results:\n";
    const bool ok = runMasterBusTest();
    std::cout << (ok ? "Test: PASS" : "Test: FAIL") << "\n";
    return ok ? 0 : 1;
}
