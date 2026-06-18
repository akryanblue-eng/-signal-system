#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

#include "Engine.h"
#include "MasterBus.h"
#include "TriggerEvent.h"

namespace chilli {

// Host-agnostic bridge between Engine's fixed-internal-block-size design and
// a real plugin host's calling convention, where process() is invoked once
// per audio callback with whatever block size the host/OS chose for that
// callback -- a size that can vary from call to call and is rarely under the
// host's control to fix in advance (think CoreAudio/ASIO/WASAPI, not just a
// VST3 "maximum" hint). Engine itself cannot absorb that directly: its
// renderBlock() always advances its internal clock by exactly blockSize()
// frames no matter what numFrames is passed in, so driving it with the
// host's own varying numFrames would desync that clock from what actually
// reached the output on every call where the two sizes differ.
//
// The fix: always render Engine in fixed kQuantumFrames chunks internally,
// and keep whatever doesn't fit the host's requested numFrames in an
// overflow buffer for the next call to drain first. From Engine's
// perspective every call still looks like exactly kQuantumFrames; from the
// host's perspective every call returns exactly the numFrames it asked for.
//
// A second, easy-to-miss problem that buffering alone does not solve:
// VoiceManager's queue is drained *entirely* on every renderBlock() call,
// and anything whose timestamp falls outside that call's own window is
// silently discarded rather than re-queued (see VoiceManager::renderBlock).
// If a host pushed an entire buffer's worth of events in one batch (e.g. 512
// frames) before calling process(), and process() internally rendered that
// in eight 64-frame quanta, only events landing in the *first* quantum would
// survive -- the rest would be popped and discarded by that first internal
// renderBlock() call before their own quantum ever ran. To stay safe against
// that, pushTrigger() here stages events in this class's own queue instead
// of forwarding them to Engine immediately; process() then dispatches only
// the subset due in each quantum's window to Engine right before rendering
// that quantum, the same "resolve this window's events, then render it"
// shape host_integration_test.cpp's renderHostBlock() already uses, just
// applied at quantum granularity instead of host-call granularity. This also
// means a host using this wrapper is free to push a whole buffer's events in
// one batch -- a relaxation of Engine's own "push only what's due right now"
// constraint, not just a faithful forwarding of it.
//
// PatternSequencer is deliberately NOT composed in here. Unlike Engine, it
// already accepts an arbitrary numFrames per resolveEvents() call with no
// internal fixed-block constraint of its own (proven by
// host_integration_test.cpp's buffer-size-independence check) -- there is no
// "host lifecycle" problem for it to solve, so it stays a separate, optional
// upstream stage a caller wires in the same way it already does today rather
// than being re-embedded inside this wrapper.
//
// No virtual interface: every other component in this engine (Engine,
// VoiceManager, RoutingEngine, PatternSequencer, MasterBus) is a concrete,
// templated class with no vtable, and there is exactly one implementation of
// "the thing a host talks to" here -- an abstract base with this as its only
// override would add an indirection layer with nothing to dispatch between.
// A real VST3/AU adapter can compose this class by value the same way this
// class composes Engine and MasterBus. Likewise process() takes a single
// float* (not float**): every component this composes is mono throughout,
// and a multi-channel host calling convention is the adapter's problem to
// solve, not this bridge's.
template <std::size_t NumVoices, std::size_t NumBuses, std::size_t QueueCapacity = 512>
class ChilliPluginWrapper {
public:
    using EngineType = Engine<NumVoices, NumBuses, QueueCapacity>;

    // Flat parameter address space for setParameter(), mirroring how a real
    // plugin host enumerates automatable parameters by integer id rather
    // than by name. kBusGainParam(i) addresses bus i's gain.
    enum class ParameterId : uint32_t {
        kDrive = 0,
        kCeiling = 1,
        kBusGainBase = 2,
    };
    static constexpr uint32_t kBusGainParam(std::size_t busIndex) {
        return static_cast<uint32_t>(ParameterId::kBusGainBase) + static_cast<uint32_t>(busIndex);
    }

    // Internal render granularity Engine is always driven at, regardless of
    // what numFrames process() is called with. Small enough to keep
    // dispatchDueEvents()'s scheduling window tight (an event can wait at
    // most kQuantumFrames-1 frames before its window is even considered),
    // large enough to keep the per-call rendering loop's overhead
    // reasonable.
    static constexpr std::size_t kQuantumFrames = 64;

    static constexpr uint32_t kStateMagic = 0x43484C50; // 'CHLP'
    static constexpr uint32_t kStateVersion = 1;

    // Binary preset blob: fixed layout, versioned so a future field addition
    // can detect (and reject, or migrate) an older blob rather than
    // misreading it.
    struct State {
        uint32_t magic = kStateMagic;
        uint32_t version = kStateVersion;
        float drive = 1.0f;
        float ceiling = 1.0f;
        std::array<float, NumBuses> busGain{};
    };

    ChilliPluginWrapper() { state_.busGain.fill(1.0f); }

    // Allocates and resets every piece of internal state -- the only place
    // in this class that allocates, matching the "allocate at
    // prepare/construction, never in process()" discipline every wrapped
    // component already follows. Safe to call again later (e.g. the host
    // changing sample rate mid-session); fully resets playback state, so any
    // currently-sounding voice and any staged-but-not-yet-fired trigger is
    // discarded. Current parameter values (drive/ceiling/bus gains) survive
    // a re-prepare, since they're host-facing state, not playback state.
    void prepare(double sampleRate, std::size_t maxBlockSize) {
        engine_.emplace(kQuantumFrames, sampleRate);
        maxBlockSize_ = maxBlockSize;
        overflowCount_ = 0;
        pendingCount_ = 0;
        internalFrame_ = 0;
        applyStateToEngine();
    }

    // frameOffsetInNextBuffer is relative to the start of the *next*
    // process() call. Stages the event rather than forwarding it to Engine
    // immediately (see class doc comment) -- safe to call several times for
    // one upcoming buffer, in any order, including for offsets past the
    // first internal quantum.
    //
    // Bridging a fixed internal quantum to a smaller host buffer forces
    // Engine to render up to kQuantumFrames-1 frames *ahead* of what the
    // host has actually asked for yet (that's what overflow_ holds) --
    // unavoidable, since Engine cannot render less than one full quantum at
    // a time. Those already-rendered frames are frozen audio: a trigger
    // whose target frame falls inside that window has already missed its
    // slot, and is clamped to fire at the earliest frame Engine hasn't
    // rendered yet instead of landing exactly where requested (the same
    // "fire ASAP" fallback Engine itself uses for a past timestamp, not a
    // dropped event). A caller that pushes triggers at least kQuantumFrames
    // ahead of their target relative to the current playback position --
    // the same lookahead a real host would apply to compensate for a
    // plugin's reported latency -- never hits this clamp.
    void pushTrigger(TriggerEvent ev, std::size_t frameOffsetInNextBuffer) {
        if (pendingCount_ >= pendingEvents_.size()) return; // staging queue full; drop, same as a saturated ring buffer would
        uint64_t frame = (internalFrame_ - overflowCount_) + frameOffsetInNextBuffer;
        if (frame < internalFrame_) frame = internalFrame_; // already-rendered overflow window; fire as soon as possible instead
        pendingEvents_[pendingCount_++] = PendingEvent{frame, ev};
    }

    // Renders exactly numFrames frames of fully mixed, MasterBus-saturated
    // output -- numFrames is whatever the host's callback asked for this
    // time and may differ from every other call. Drains buffered overflow
    // from the previous call first, then renders additional kQuantumFrames
    // chunks from Engine (each immediately passed through MasterBus) until
    // there's enough to satisfy this call, buffering any surplus for the
    // next one.
    void process(float* output, std::size_t numFrames) {
        std::size_t produced = 0;

        if (overflowCount_ > 0) {
            const std::size_t n = std::min(overflowCount_, numFrames);
            std::copy(overflow_.begin(), overflow_.begin() + static_cast<std::ptrdiff_t>(n), output);
            std::copy(overflow_.begin() + static_cast<std::ptrdiff_t>(n), overflow_.begin() + static_cast<std::ptrdiff_t>(overflowCount_),
                      overflow_.begin());
            overflowCount_ -= n;
            produced += n;
        }

        while (produced < numFrames) {
            dispatchDueEvents(internalFrame_, kQuantumFrames);

            std::array<float, kQuantumFrames> quantum{};
            engine_->renderBlock(quantum.data(), kQuantumFrames);
            masterBus_.processBlock(quantum.data(), kQuantumFrames);
            internalFrame_ += kQuantumFrames;

            const std::size_t need = numFrames - produced;
            const std::size_t take = std::min(need, kQuantumFrames);
            std::copy(quantum.begin(), quantum.begin() + static_cast<std::ptrdiff_t>(take), output + produced);
            produced += take;

            if (take < kQuantumFrames) {
                std::copy(quantum.begin() + static_cast<std::ptrdiff_t>(take), quantum.end(), overflow_.begin());
                overflowCount_ = kQuantumFrames - take;
            }
        }
    }

    void setParameter(uint32_t id, float value) {
        if (id == static_cast<uint32_t>(ParameterId::kDrive)) {
            state_.drive = value;
        } else if (id == static_cast<uint32_t>(ParameterId::kCeiling)) {
            state_.ceiling = value;
        } else {
            const uint32_t busIndex = id - static_cast<uint32_t>(ParameterId::kBusGainBase);
            if (busIndex >= NumBuses) return;
            state_.busGain[busIndex] = value;
        }
        applyStateToEngine();
    }

    // Plain reads/writes, not atomics -- this sketch assumes the host
    // serializes setParameter() with process() calls itself (e.g. both on
    // the audio thread, or via the host's own lock-free automation queue
    // feeding calls made from that thread). A real cross-thread automation
    // path (atomics, or a double-buffered parameter set applied at the top
    // of process()) is additional work a concrete VST3/AU adapter would add
    // on top; it's not needed to prove the lifecycle/buffering logic this
    // class exists for.
    State getState() const { return state_; }

    void setState(const State& state) {
        if (state.magic != kStateMagic || state.version != kStateVersion) return;
        state_ = state;
        applyStateToEngine();
    }

    Bus& bus(std::size_t index) { return engine_->bus(index); }
    const Bus& bus(std::size_t index) const { return engine_->bus(index); }

    double sampleRate() const { return engine_->sampleRate(); }
    std::size_t maxBlockSize() const { return maxBlockSize_; }

private:
    struct PendingEvent {
        uint64_t frame = 0;
        TriggerEvent ev;
    };

    void applyStateToEngine() {
        masterBus_.setDrive(state_.drive);
        masterBus_.setCeiling(state_.ceiling);
        for (std::size_t i = 0; i < NumBuses; ++i) engine_->bus(i).gain = state_.busGain[i];
    }

    // Forwards every staged event due in [windowStart, windowStart +
    // windowLen) to Engine, swap-erasing each as it's dispatched. Anything
    // not due yet (e.g. staged for a later quantum within this same
    // process() call, or a future call entirely) is left in place.
    void dispatchDueEvents(uint64_t windowStart, std::size_t windowLen) {
        std::size_t i = 0;
        while (i < pendingCount_) {
            if (pendingEvents_[i].frame < windowStart + windowLen) {
                TriggerEvent ev = pendingEvents_[i].ev;
                ev.timestamp = pendingEvents_[i].frame;
                engine_->pushTrigger(ev);
                pendingEvents_[i] = pendingEvents_[pendingCount_ - 1];
                --pendingCount_;
            } else {
                ++i;
            }
        }
    }

    std::optional<EngineType> engine_;
    MasterBus masterBus_;
    State state_;

    std::array<float, kQuantumFrames> overflow_{};
    std::size_t overflowCount_ = 0;
    uint64_t internalFrame_ = 0;
    std::size_t maxBlockSize_ = 0;

    std::array<PendingEvent, QueueCapacity> pendingEvents_{};
    std::size_t pendingCount_ = 0;
};

} // namespace chilli
