#pragma once

#include <cstdint>
#include <vector>

#include "Resampler.h"

namespace chilli {

// Canonical, already-decoded PCM held by the engine. File decoding (WAV/AIFF)
// and rate conversion both happen before a SampleBuffer exists -- this struct
// only ever holds mono float32 data at engineSampleRate, so the real-time
// voice code never has to reason about source format.
struct SampleBuffer {
    std::vector<float> samples;
    double sampleRate = 0.0;

    bool empty() const { return samples.empty(); }

    // Builds a SampleBuffer at sourceRate, then runs it through the offline
    // windowed-sinc resampler if engineSampleRate differs. This is the only
    // place SRC happens: once, at import, off the audio thread.
    static SampleBuffer fromDecodedPCM(std::vector<float> decoded,
                                        double sourceRate,
                                        double engineSampleRate,
                                        int resamplerHalfWidth = 32) {
        SampleBuffer buf;
        if (sourceRate == engineSampleRate) {
            buf.samples = std::move(decoded);
        } else {
            buf.samples = resampleBlackmanHarris(decoded, sourceRate, engineSampleRate,
                                                  resamplerHalfWidth);
        }
        buf.sampleRate = engineSampleRate;
        return buf;
    }
};

} // namespace chilli
