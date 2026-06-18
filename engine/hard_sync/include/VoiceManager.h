#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <vector>

#include "AtomicRingBuffer.h"
#include "RoutingEngine.h"
#include "TriggerEvent.h"
#include "Voice808State.h"

namespace chilli {

// Owns a fixed pool of voice slots and the trigger queue feeding them, and
// renders every active voice straight into its bus on a RoutingEngine.
//
// Bus assignment is a pure function of the trigger event: TriggerEvent::busId
// is latched into the voice slot once, in init(), and never re-evaluated for
// the life of that voice. There is no per-block routing-table lookup and no
// migration between buses while a voice is active -- moving a sustained
// voice to a different bus means starting a new trigger on that bus, not
// mutating this one. That keeps RoutingEngine::process()'s bus summation
// order independent of anything a voice does after it starts.
//
// Block size and voice/bus counts are fixed at construction, so renderBlock()
// never allocates -- safe to call from the audio thread, same discipline as
// RoutingEngine itself.
template <std::size_t NumVoices, std::size_t NumBuses, std::size_t QueueCapacity = 512>
class VoiceManager {
public:
    explicit VoiceManager(std::size_t blockSize) : blockSize_(blockSize) {
        scratch_.assign(blockSize_, 0.0f);
    }

    void pushTrigger(const TriggerEvent& ev) { queue_.push(ev); }

    // Renders this block's queued triggers into routing's bus buffers.
    // Does not call routing.clearBuses() or routing.process() -- clearing
    // and mixdown are the caller's responsibility, once per block, since
    // multiple independent sources may accumulate into the same buses
    // before mixdown happens.
    void renderBlock(RoutingEngine<NumBuses>& routing, double sampleRate) {
        struct Pending {
            uint32_t frame;
            TriggerEvent ev;
        };
        std::array<Pending, QueueCapacity> pending{};
        std::size_t pendingCount = 0;

        TriggerEvent ev;
        while (pendingCount < pending.size() && queue_.pop(ev)) {
            const uint32_t frameInBlock = (ev.timestamp > globalFrame_)
                ? static_cast<uint32_t>(ev.timestamp - globalFrame_)
                : 0;
            if (frameInBlock >= static_cast<uint32_t>(blockSize_)) {
                continue; // belongs to a later block
            }
            pending[pendingCount++] = Pending{frameInBlock, ev};
        }
        std::sort(pending.begin(), pending.begin() + pendingCount,
                  [](const Pending& a, const Pending& b) { return a.frame < b.frame; });

        // Render in segments split at each trigger's frame, same as the
        // hard-sync harness, so a mid-block steal -- including a steal onto
        // a different bus -- takes effect on its exact target sample.
        uint32_t cursor = 0;
        std::size_t idx = 0;
        while (cursor < static_cast<uint32_t>(blockSize_)) {
            while (idx < pendingCount && pending[idx].frame <= cursor) {
                const auto& triggered = pending[idx].ev;
                voices_[static_cast<std::size_t>(triggered.padIndex)].init(triggered, 0, sampleRate);
                ++idx;
            }
            const uint32_t segmentEnd =
                (idx < pendingCount) ? pending[idx].frame : static_cast<uint32_t>(blockSize_);
            renderSegment(routing, cursor, segmentEnd);
            cursor = segmentEnd;
        }

        globalFrame_ += blockSize_;
    }

private:
    static constexpr uint32_t kCrossfadeSamples = 32;

    void renderSegment(RoutingEngine<NumBuses>& routing, uint32_t start, uint32_t end) {
        if (start >= end) return;
        const uint32_t segmentLen = end - start;

        for (auto& voice : voices_) {
            if (!voice.active || voice.sampleData == nullptr) continue;

            for (uint32_t i = 0; i < segmentLen; ++i) {
                voice.updateState(0.0);

                if (voice.glideActive) {
                    voice.pitchCurrent += (voice.pitchTarget - voice.pitchCurrent) * voice.pitchRate;
                }

                const float remaining = static_cast<float>(voice.transientBypassSamples) - voice.sampleOffset;
                float sample;

                if (voice.transientBypass && remaining > static_cast<float>(kCrossfadeSamples)) {
                    sample = directSample(voice);
                } else if (voice.transientBypass && remaining > 0.0f) {
                    const float w = 1.0f - (remaining / static_cast<float>(kCrossfadeSamples));
                    sample = directSample(voice) * (1.0f - w) + interpolatedSample(voice) * w;
                } else {
                    sample = interpolatedSample(voice);
                }

                scratch_[i] = sample * voice.aLevel;

                voice.sampleOffset += stepSize(voice.pitchCurrent);
                if (voice.sampleOffset >= static_cast<float>(voice.sampleLength)) {
                    voice.sampleOffset = std::fmod(voice.sampleOffset, static_cast<float>(voice.sampleLength));
                }
            }

            routing.bus(voice.busId).accumulate(scratch_.data(), segmentLen, start);
        }
    }

    static float directSample(const Voice808State& voice) {
        const uint32_t i0 = static_cast<uint32_t>(voice.sampleOffset) % voice.sampleLength;
        return voice.sampleData[i0];
    }

    static float interpolatedSample(const Voice808State& voice) {
        const uint32_t i0 = static_cast<uint32_t>(voice.sampleOffset) % voice.sampleLength;
        const uint32_t i1 = (i0 + 1) % voice.sampleLength;
        const float frac = voice.sampleOffset - std::floor(voice.sampleOffset);
        return voice.sampleData[i0] * (1.0f - frac) + voice.sampleData[i1] * frac;
    }

    static float stepSize(float pitchOctaves) { return std::pow(2.0f, pitchOctaves); }

    std::array<Voice808State, NumVoices> voices_{};
    AtomicRingBuffer<TriggerEvent, QueueCapacity> queue_;
    std::vector<float> scratch_;
    std::size_t blockSize_;
    uint64_t globalFrame_ = 0;
};

} // namespace chilli
