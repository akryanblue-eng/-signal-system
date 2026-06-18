#pragma once

#include <cstdint>

// A single 808 trigger, as queued from the UI/sequencer thread to the audio thread.
struct TriggerEvent {
    uint64_t timestamp = 0;            // global sample frame the hit should start on
    int padIndex = 0;                  // voice slot to (re)trigger; same slot == hard steal
    float velocity = 1.0f;

    float pitchStartOctaves = 0.0f;
    float pitchTargetOctaves = 0.0f;
    float attackSec = 0.005f;
    float glideSec = 0.0f;

    uint32_t transientBypassSamples = 0; // direct-access window before falling back to interpolation
    uint32_t sampleLength = 4096;

    // Non-owning pointer into an already-decoded, already-resampled sample
    // (e.g. AssetManager::getOrResample(...).samples.data()); the caller
    // owns the lifetime, which must outlive every voice playing it.
    const float* sampleData = nullptr;

    // Destination bus, decided here at trigger time. VoiceManager latches
    // this into the voice slot once at init() and never re-evaluates it for
    // the life of that voice -- routing a sustained voice elsewhere means a
    // new trigger on a new bus, not a mutation of this one.
    uint8_t busId = 0;
};
