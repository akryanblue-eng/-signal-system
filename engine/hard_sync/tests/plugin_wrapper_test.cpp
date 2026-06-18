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
//   5. Boundary conditions - the same staged schedule rendered through
//      1-frame-at-a-time host calls (maximum quantum pressure: the overflow
//      buffer drains one sample per call for up to 63 calls between
//      internal renders) and through a single offline-style call covering
//      the entire span both match the 64-frame (quantum-aligned) reference
//      bit-for-bit.
//   6. Lifecycle stability - five back-to-back prepare()-then-render cycles
//      with the same trigger produce bit-identical output every time (no
//      state leaking from one cycle into the next), and a stale trigger
//      staged immediately before a second, redundant prepare() call (no
//      process() in between, as a host renegotiating sample rate before
//      ever pulling audio might do) never fires -- prepare() must discard
//      staged-but-undispatched events, not just playback state.
//   7. Triple-buffer (ParameterBridge) snapshot consistency - heavy
//      setParameter() churn (1-2 calls between each query, this sketch's
//      writer/reader still being same-thread by contract, so this cannot
//      exercise an actual data race) interleaved with oversized
//      offline-style process() calls, queried via getStateSnapshot() (state
//      + generation from a single acquire(), not two independent reads
//      that could straddle a publish), never yields a bad magic/version, a
//      generation that goes backwards, or a busGain/drive value that
//      disagrees with what was just set -- i.e. the publish path never
//      hands back a half-written State. Proving the same under real
//      concurrent readers and writers needs a thread-sanitizer build, the
//      same boundary this suite already respected when scoping out
//      "concurrency stress" earlier.
//   8. ParameterTrace forensic log - a standalone observer of every
//      ParameterBridge publish (see ParameterTrace.h), not just the latest
//      snapshot: totalRecorded() counts every publish ever made including
//      the constructor's own initial one, size() caps at the trace's fixed
//      capacity with the oldest entries silently evicted once exceeded, the
//      newest held entry always matches whatever was most recently set, and
//      every entry still held carries a strictly increasing generation.
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

// Stages the whole schedule before the first process() call -- at that
// point internalFrame_ and overflowCount_ are both still zero, so every
// offset maps to its absolute frame exactly, with no risk of landing in an
// already-rendered overflow window (see pushTrigger()'s doc comment) -- then
// renders totalFrames in blockSize-sized host calls (the last one truncated
// if blockSize doesn't divide totalFrames evenly).
std::vector<float> renderSchedule(const std::vector<ScheduledTrigger>& schedule, std::size_t blockSize,
                                   std::size_t totalFrames) {
    chilli::ChilliPluginWrapper<8, 2> wrapper;
    wrapper.prepare(SAMPLE_RATE, blockSize);
    for (const auto& s : schedule) wrapper.pushTrigger(s.ev, static_cast<std::size_t>(s.frame));

    std::vector<float> output(totalFrames, -999.0f);
    std::size_t rendered = 0;
    while (rendered < totalFrames) {
        const std::size_t n = std::min(blockSize, totalFrames - rendered);
        wrapper.process(output.data() + rendered, n);
        rendered += n;
    }
    return output;
}

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

        const auto out17 = renderSchedule(schedule, 17, TOTAL_FRAMES);
        const auto out64 = renderSchedule(schedule, 64, TOTAL_FRAMES);
        const auto out333 = renderSchedule(schedule, 333, TOTAL_FRAMES);

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

    // 5. Boundary conditions: 1-frame-at-a-time callbacks (maximum quantum
    // pressure) and a single whole-span offline call both match the
    // 64-frame reference bit-for-bit.
    {
        std::vector<ScheduledTrigger> schedule;
        const uint64_t frames[] = {0, 63, 64, 65, 500, 2000};
        for (std::size_t i = 0; i < 6; ++i) {
            TriggerEvent ev;
            ev.padIndex = static_cast<int>(i % 8);
            ev.busId = static_cast<uint8_t>(i % 2);
            ev.velocity = 1.0f;
            ev.attackSec = 0.0f;
            ev.sampleData = ramp.data();
            ev.sampleLength = static_cast<uint32_t>(ramp.size());
            schedule.push_back(ScheduledTrigger{frames[i], ev});
        }
        constexpr std::size_t TOTAL_FRAMES = 2560;

        const auto reference = renderSchedule(schedule, 64, TOTAL_FRAMES);
        const auto oneFrameAtATime = renderSchedule(schedule, 1, TOTAL_FRAMES);
        const auto wholeSpanInOneCall = renderSchedule(schedule, TOTAL_FRAMES, TOTAL_FRAMES);

        bool hasSignal = false;
        for (float v : reference) {
            if (v != 0.0f) { hasSignal = true; break; }
        }
        bool ok = hasSignal;
        for (std::size_t i = 0; i < TOTAL_FRAMES; ++i) {
            if (reference[i] != oneFrameAtATime[i] || reference[i] != wholeSpanInOneCall[i]) ok = false;
        }
        std::cout << "  Boundary conditions (1-frame and whole-span calls match reference): " << (ok ? "PASS" : "FAIL")
                   << "\n";
        allPass &= ok;
    }

    // 6. Lifecycle stability: repeated prepare()-then-render cycles are
    // bit-identical, and a stale trigger staged before a redundant
    // re-prepare() (no process() in between) never fires.
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
        std::vector<float> first;
        bool repeatedCyclesOk = true;
        for (int cycle = 0; cycle < 5; ++cycle) {
            wrapper.prepare(SAMPLE_RATE, 64);
            wrapper.pushTrigger(ev, 10);
            std::vector<float> out(128, -999.0f);
            wrapper.process(out.data(), 128);
            if (cycle == 0) {
                first = out;
            } else if (out != first) {
                repeatedCyclesOk = false;
            }
        }

        TriggerEvent staleEv = ev;
        staleEv.padIndex = 1;
        staleEv.busId = 1;
        wrapper.prepare(SAMPLE_RATE, 64);
        wrapper.pushTrigger(staleEv, 5);   // staged, then immediately invalidated below
        wrapper.prepare(SAMPLE_RATE, 64);  // redundant re-prepare, no process() in between
        wrapper.pushTrigger(ev, 10);       // only this one should ever fire
        std::vector<float> afterRedundantPrepare(128, -999.0f);
        wrapper.process(afterRedundantPrepare.data(), 128);
        const bool staleTriggerDiscarded = afterRedundantPrepare == first;

        const bool ok = repeatedCyclesOk && staleTriggerDiscarded;
        std::cout << "  Lifecycle stability (repeated cycles identical, stale trigger discarded): "
                   << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 7. Triple-buffer (ParameterBridge) snapshot consistency under heavy
    // setParameter() churn interleaved with oversized offline-style
    // process() calls. Single-threaded, so this cannot exercise an actual
    // data race (see class doc comment); what it does prove deterministically
    // is that every getState()/parameterGeneration() observed mid-churn is a
    // complete, valid snapshot -- never a torn or stale-looking State -- and
    // that generation only ever moves forward.
    {
        using Wrapper = chilli::ChilliPluginWrapper<8, 2>;
        Wrapper wrapper;
        wrapper.prepare(SAMPLE_RATE, 64);

        TriggerEvent ev;
        ev.padIndex = 0;
        ev.busId = 0;
        ev.velocity = 1.0f;
        ev.attackSec = 0.0f;
        ev.sampleData = ramp.data();
        ev.sampleLength = static_cast<uint32_t>(ramp.size());
        wrapper.pushTrigger(ev, 0);

        bool ok = true;
        uint64_t lastGeneration = 0;
        std::vector<float> hugeOut(5000, -999.0f);

        uint32_t rngState = 12345;
        auto nextRand = [&]() {
            rngState = rngState * 1664525u + 1013904223u;
            return rngState;
        };

        for (int i = 0; i < 2000; ++i) {
            const float driveVal = 1.0f + static_cast<float>(nextRand() % 800) / 100.0f;
            const float gainVal = static_cast<float>(nextRand() % 100) / 100.0f;
            wrapper.setParameter(static_cast<uint32_t>(Wrapper::ParameterId::kDrive), driveVal);
            wrapper.setParameter(Wrapper::kBusGainParam(0), gainVal);

            const auto snapshot = wrapper.getStateSnapshot(); // state + generation from one acquire()
            const auto& state = snapshot.state;
            if (state.magic != Wrapper::kStateMagic || state.version != Wrapper::kStateVersion) ok = false;
            if (snapshot.generation < lastGeneration) ok = false; // must never go backwards
            lastGeneration = snapshot.generation;
            if (state.drive != driveVal || state.busGain[0] != gainVal) ok = false;
            if (wrapper.bus(0).gain != gainVal) ok = false;

            if (i % 200 == 0) {
                wrapper.process(hugeOut.data(), hugeOut.size()); // oversized offline-style render mid-churn
            }
        }

        std::cout << "  Snapshot consistency under heavy parameter churn (valid magic/version, "
                      "monotonic generation, bus state agrees): "
                   << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 8. ParameterTrace forensic log: total count includes the constructor's
    // initial publish, size() caps at capacity with oldest-entry eviction,
    // the newest entry matches the most recently set value, and generation
    // strictly increases across every entry still held.
    {
        using Wrapper = chilli::ChilliPluginWrapper<8, 2>;
        Wrapper wrapper;
        wrapper.prepare(SAMPLE_RATE, 64);

        constexpr int kCapacity = 1024;
        constexpr int kSetCalls = 1500; // > capacity, forces eviction
        float lastDrive = 0.0f;
        for (int i = 0; i < kSetCalls; ++i) {
            lastDrive = 1.0f + static_cast<float>(i % 100) * 0.01f;
            wrapper.setParameter(static_cast<uint32_t>(Wrapper::ParameterId::kDrive), lastDrive);
        }

        const auto& trace = wrapper.parameterTrace();
        const std::size_t expectedTotal = 1 + static_cast<std::size_t>(kSetCalls); // +1 for ctor's initial publish
        bool ok = trace.totalRecorded() == expectedTotal;
        ok = ok && trace.size() == static_cast<std::size_t>(kCapacity);

        const auto& newest = trace.at(trace.size() - 1);
        ok = ok && newest.state.drive == lastDrive;

        for (std::size_t i = 0; i + 1 < trace.size(); ++i) {
            if (trace.at(i).generation >= trace.at(i + 1).generation) ok = false;
        }

        std::cout << "  ParameterTrace forensic log (total count, capacity cap, newest entry, "
                      "monotonic generation): "
                   << (ok ? "PASS" : "FAIL") << "\n";
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
