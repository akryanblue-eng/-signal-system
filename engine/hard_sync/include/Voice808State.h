#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

#include "TriggerEvent.h"

// Per-voice playback state for one 808 slot. A trigger on an already-active
// slot is a hard steal: init() resets playback position and envelope so the
// new hit starts clean, with no audio contribution surviving from the old one.
struct Voice808State {
    bool active = false;
    uint32_t startFrameInBlock = 0;

    // Pitch / glide
    float pitchCurrent = 0.0f;
    float pitchTarget = 0.0f;
    float pitchRate = 0.0f;
    bool glideActive = false;

    // Transient bypass: direct sample access for the first N samples, then a
    // short crossfade into the normal interpolated path.
    bool transientBypass = false;
    uint32_t transientBypassSamples = 0;

    // Playback position within the sample. Kept as a float (not an integer sample
    // index) so that fractional step sizes from pitch-shifted playback (e.g. a
    // step of 0.84 for a -0.25 octave start) accumulate correctly instead of being
    // truncated to zero on every sample.
    float sampleOffset = 0.0f;
    uint32_t sampleLength = 0;

    // Amplitude envelope (attack ramp only; this is a minimal harness, not the full engine)
    float aLevel = 0.0f;
    uint32_t attackSamples = 1;
    uint32_t attackCounter = 0;

    // Bumped on every init(); lets callers distinguish "this hit" from "the previous
    // hit on the same slot" when verifying steal behavior.
    uint32_t generation = 0;

    void init(const TriggerEvent& ev, uint32_t startFrameInBlockIn, double sampleRate) {
        active = true;
        startFrameInBlock = startFrameInBlockIn;

        pitchCurrent = ev.pitchStartOctaves;
        pitchTarget = ev.pitchTargetOctaves;
        glideActive = ev.glideSec > 0.0f;
        pitchRate = glideActive ? static_cast<float>(1.0 / (ev.glideSec * sampleRate)) : 1.0f;

        transientBypassSamples = ev.transientBypassSamples;
        transientBypass = transientBypassSamples > 0;

        sampleOffset = 0.0f; // hard reset: no tail from a previous hit on this slot
        sampleLength = ev.sampleLength;

        aLevel = 0.0f;
        attackSamples = std::max<uint32_t>(1, static_cast<uint32_t>(ev.attackSec * sampleRate));
        attackCounter = 0;

        ++generation;
    }

    void updateState(double /*sampleRate*/) {
        if (attackCounter < attackSamples) {
            ++attackCounter;
            aLevel = static_cast<float>(attackCounter) / static_cast<float>(attackSamples);
        } else {
            aLevel = 1.0f;
        }

        if (glideActive) {
            if (std::abs(pitchTarget - pitchCurrent) < 1e-6f) {
                pitchCurrent = pitchTarget;
                glideActive = false;
            }
        }
    }
};
