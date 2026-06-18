#pragma once

#include <algorithm>
#include <cstddef>

#include "RoutingEngine.h"
#include "TriggerEvent.h"
#include "VoiceManager.h"

namespace chilli {

// The single class an audio callback (VST/AU host, system audio thread,
// etc.) ever needs to touch. Wraps a VoiceManager and a RoutingEngine and
// owns the per-block sequencing between them -- clear buses, let voices
// accumulate, mix down -- so that ordering is never the caller's concern
// and can never be gotten wrong from outside this class.
//
// Voice/bus counts and block size are fixed at construction, matching the
// no-allocation-after-construction discipline of every class it wraps:
// renderBlock() never allocates.
template <std::size_t NumVoices, std::size_t NumBuses, std::size_t QueueCapacity = 512>
class Engine {
public:
    Engine(std::size_t blockSize, double sampleRate)
        : voiceManager_(blockSize), routing_(blockSize), sampleRate_(sampleRate) {}

    // Queues a trigger for the next renderBlock() call whose block window
    // contains its timestamp. Safe to call from a non-audio thread (backed
    // by AtomicRingBuffer).
    void pushTrigger(const TriggerEvent& ev) { voiceManager_.pushTrigger(ev); }

    // Per-bus gain/mix control -- the only mixer-level surface this engine
    // exposes today. Bus *assignment* is not controllable from here by
    // design: it's latched per voice at trigger time (see VoiceManager.h).
    Bus& bus(std::size_t index) { return routing_.bus(index); }
    const Bus& bus(std::size_t index) const { return routing_.bus(index); }

    // Renders exactly blockSize() frames internally, then copies up to
    // numFrames of that into output. numFrames is expected to equal
    // blockSize(); a smaller value copies a truncated prefix rather than
    // over-reading the mixed buffer.
    void renderBlock(float* output, std::size_t numFrames) {
        routing_.clearBuses();
        voiceManager_.renderBlock(routing_, sampleRate_);
        routing_.process();

        const auto& mixed = routing_.mainOut();
        const std::size_t n = std::min(numFrames, mixed.size());
        std::copy(mixed.begin(), mixed.begin() + static_cast<std::ptrdiff_t>(n), output);
    }

    double sampleRate() const { return sampleRate_; }
    std::size_t blockSize() const { return routing_.blockSize(); }
    static constexpr std::size_t numBuses() { return NumBuses; }
    static constexpr std::size_t numVoices() { return NumVoices; }

private:
    VoiceManager<NumVoices, NumBuses, QueueCapacity> voiceManager_;
    RoutingEngine<NumBuses> routing_;
    double sampleRate_;
};

} // namespace chilli
