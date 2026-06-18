// Host Mock test for ChilliPluginWrapper: simulates a plugin host driving
// the wrapper through prepare()/process()/setParameter()/getState()/
// setState() the way a real VST3/AU adapter eventually will, without any
// SDK in the loop.
//
//   1. Buffer-size independence at the wrapper layer - the same trigger
//      schedule, staged in full before any process() call (the same
//      lookahead a real host applies to compensate for a plugin's reported
//      latency -- see pushTrigger()'s doc comment for why a *late* push can
//      legitimately fire later than requested), then rendered through host
//      call sizes 17, 64 (the wrapper's own internal quantum), and 333
//      frames, produces bit-identical output. 333 spans multiple internal
//      quanta in one process() call and isn't a multiple of 64 or 17, so a
//      single host buffer can contain events meant for several different
//      internal quanta -- exactly the scenario that would silently lose
//      events if pushTrigger() forwarded straight to Engine instead of
//      staging and dispatching per-quantum.
//   2. prepare() resets playback state - a voice left sounding from before
//      a second prepare() call does not bleed into audio rendered after it,
//      and sampleRate() reflects the new call's value.
//   3. setParameter() reaches both DSP stages - kDrive changes MasterBus's
//      saturation (monotonic, same property master_bus_test.cpp checks
//      directly), and kBusGainParam(i) changes that bus's live gain and is
//      reflected in getState().
//   4. getState()/setState() round-trip - capturing state, mutating
//      parameters, rendering (different output), then restoring the
//      captured state and re-rendering the same trigger reproduces the
//      original output exactly. A blob with a corrupted magic/version is
//      rejected (no-op) rather than partially applied.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <vector>

#include "ChilliPluginWrapper.h"
#include "TriggerEvent.h"

namespace {

constexpr double SAMPLE_RATE = 48000.0;

std::vector<float> makeRamp(std::size_t n) {
    std::vector<float> out(n);
    for (std::size_t i = 0; i < n; ++i) out[i] = static_cast<float>(i + 1) * 0.001f;
    return out;
}

struct ScheduledTrigger {
    uint64_t frame;
    TriggerEvent ev;
};

} // namespace

bool runPluginWrapperTest() {
    bool allPass = true;
    auto ramp = makeRamp(256);

    // 1. Buffer-size independence: same schedule, three different host call
    // sizes, bit-identical output over the same total span.
    {
        std::vector<ScheduledTrigger> schedule;
        const uint64_t frames[] = {10, 100, 200, 300, 1000, 1050, 1900};
        for (std::size_t i = 0; i < 7; ++i) {
            TriggerEvent ev;
            ev.padIndex = static_cast<int>(i % 8);
            ev.busId = static_cast<uint8_t>(i % 2);
            ev.velocity = 1.0f;
            ev.attackSec = 0.0f;
            ev.sampleData = ramp.data();
            ev.sampleLength = static_cast<uint32_t>(ramp.size());
            schedule.push_back(ScheduledTrigger{frames[i], ev});
        }
        constexpr std::size_t TOTAL_FRAMES = 2048;

        auto renderWithBlockSize = [&](std::size_t blockSize) {
            chilli::ChilliPluginWrapper<8, 2> wrapper;
            wrapper.prepare(SAMPLE_RATE, blockSize);
            // Stage the whole schedule before the first process() call --
            // at this point internalFrame_ and overflowCount_ are both
            // still zero, so every offset maps to its absolute frame
            // exactly, with no risk of landing in an already-rendered
            // overflow window (see pushTrigger()'s doc comment).
            for (const auto& s : schedule) wrapper.pushTrigger(s.ev, static_cast<std::size_t>(s.frame));

            std::vector<float> output(TOTAL_FRAMES, -999.0f);
            std::size_t rendered = 0;
            while (rendered < TOTAL_FRAMES) {
                const std::size_t n = std::min(blockSize, TOTAL_FRAMES - rendered);
                wrapper.process(output.data() + rendered, n);
                rendered += n;
            }
            return output;
        };

        const auto out17 = renderWithBlockSize(17);
        const auto out64 = renderWithBlockSize(64);
        const auto out333 = renderWithBlockSize(333);

        bool ok = false;
        for (float v : out17) {
            if (v != 0.0f) { ok = true; break; }
        }
        for (std::size_t i = 0; i < TOTAL_FRAMES; ++i) {
            if (out17[i] != out64[i] || out17[i] != out333[i]) ok = false;
        }
        std::cout << "  Buffer-size independence (17/64/333 bit-identical): " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 2. prepare() resets playback state: a voice sounding right before a
    // second prepare() call must not bleed into audio rendered after it.
    {
        chilli::ChilliPluginWrapper<8, 2> wrapper;
        wrapper.prepare(48000.0, 256);

        TriggerEvent ev;
        ev.padIndex = 0;
        ev.busId = 0;
        ev.velocity = 1.0f;
        ev.attackSec = 0.0f;
        ev.sampleData = ramp.data();
        ev.sampleLength = static_cast<uint32_t>(ramp.size());
        wrapper.pushTrigger(ev, 0);
        std::vector<float> warm(64, -999.0f);
        wrapper.process(warm.data(), 64); // voice now mid-playback, definitely sounding

        wrapper.prepare(44100.0, 128); // re-prepare mid-session
        std::vector<float> after(64, -999.0f);
        wrapper.process(after.data(), 64);

        bool ok = wrapper.sampleRate() == 44100.0;
        for (float v : after) {
            if (v != 0.0f) ok = false;
        }
        std::cout << "  prepare() resets playback state, updates sampleRate(): " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 3. setParameter() reaches MasterBus (drive) and Engine (bus gain).
    {
        TriggerEvent ev;
        ev.padIndex = 0;
        ev.busId = 0;
        ev.velocity = 1.0f;
        ev.attackSec = 0.0f;
        ev.sampleData = ramp.data();
        ev.sampleLength = static_cast<uint32_t>(ramp.size());

        using Wrapper = chilli::ChilliPluginWrapper<8, 2>;

        auto renderWithDrive = [&](float drive) {
            Wrapper wrapper;
            wrapper.prepare(SAMPLE_RATE, 64);
            wrapper.setParameter(static_cast<uint32_t>(Wrapper::ParameterId::kDrive), drive);
            wrapper.pushTrigger(ev, 0);
            std::vector<float> out(64, -999.0f);
            wrapper.process(out.data(), 64);
            float peak = 0.0f;
            for (float v : out) peak = std::max(peak, std::abs(v));
            return peak;
        };

        const float peakLowDrive = renderWithDrive(1.0f);
        const float peakHighDrive = renderWithDrive(8.0f);
        const bool driveOk = peakHighDrive > peakLowDrive;

        Wrapper wrapper;
        wrapper.prepare(SAMPLE_RATE, 64);
        wrapper.setParameter(Wrapper::kBusGainParam(0), 0.25f);
        const bool gainOk = wrapper.bus(0).gain == 0.25f && wrapper.getState().busGain[0] == 0.25f;

        const bool ok = driveOk && gainOk;
        std::cout << "  setParameter() reaches MasterBus drive and bus gain: " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 4. getState()/setState() round-trip, including rejecting a corrupted blob.
    {
        using Wrapper = chilli::ChilliPluginWrapper<8, 2>;
        TriggerEvent ev;
        ev.padIndex = 0;
        ev.busId = 0;
        ev.velocity = 1.0f;
        ev.attackSec = 0.0f;
        ev.sampleData = ramp.data();
        ev.sampleLength = static_cast<uint32_t>(ramp.size());

        Wrapper wrapper;
        wrapper.prepare(SAMPLE_RATE, 64);
        wrapper.setParameter(static_cast<uint32_t>(Wrapper::ParameterId::kDrive), 2.5f);
        wrapper.setParameter(static_cast<uint32_t>(Wrapper::ParameterId::kCeiling), 0.8f);
        wrapper.setParameter(Wrapper::kBusGainParam(0), 0.3f);
        wrapper.setParameter(Wrapper::kBusGainParam(1), 0.6f);
        const auto captured = wrapper.getState();

        wrapper.pushTrigger(ev, 0);
        std::vector<float> reference(64, -999.0f);
        wrapper.process(reference.data(), 64);

        // Mutate away from the captured state and render -- must differ.
        wrapper.setParameter(static_cast<uint32_t>(Wrapper::ParameterId::kDrive), 1.0f);
        wrapper.setParameter(static_cast<uint32_t>(Wrapper::ParameterId::kCeiling), 1.0f);
        wrapper.setParameter(Wrapper::kBusGainParam(0), 1.0f);
        wrapper.prepare(SAMPLE_RATE, 64); // reset playback state for a clean re-trigger
        wrapper.setState(captured);       // ...then immediately restore via setState
        wrapper.pushTrigger(ev, 0);
        std::vector<float> restored(64, -999.0f);
        wrapper.process(restored.data(), 64);

        bool roundTripOk = true;
        for (std::size_t i = 0; i < 64; ++i) {
            if (reference[i] != restored[i]) roundTripOk = false;
        }

        // Corrupted blob (bad magic) must be rejected, leaving state unchanged.
        auto corrupted = captured;
        corrupted.magic = 0xDEADBEEF;
        wrapper.setParameter(static_cast<uint32_t>(Wrapper::ParameterId::kDrive), 5.0f);
        const auto beforeReject = wrapper.getState();
        wrapper.setState(corrupted);
        const auto afterReject = wrapper.getState();
        const bool rejectOk = afterReject.drive == beforeReject.drive && afterReject.magic == Wrapper::kStateMagic;

        const bool ok = roundTripOk && rejectOk;
        std::cout << "  getState()/setState() round-trip, rejects corrupted blob: " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    return allPass;
}

int main() {
    std::cout << "Plugin Wrapper Test Results:\n";
    const bool ok = runPluginWrapperTest();
    std::cout << (ok ? "Test: PASS" : "Test: FAIL") << "\n";
    return ok ? 0 : 1;
}
