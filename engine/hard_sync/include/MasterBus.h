#pragma once

#include <cmath>
#include <cstddef>

namespace chilli {

// Soft-saturating output stage: a single continuous tanh nonlinearity, not
// a hard-knee/threshold model. tanh is smooth (infinitely differentiable)
// everywhere, so there's no discrete transition point whose slope could be
// discontinuous -- the usual failure mode of piecewise/hard-knee limiters
// -- and it's already odd-symmetric (tanh(-x) == -tanh(x)), so positive and
// negative excursions saturate identically with no separate logic needed.
//
// Deliberately not wired into Engine::renderBlock(): Engine's existing
// tests rely on its output being exact linear gain (e.g.
// output[i] == sample[i] * busGain), and even the slight curvature tanh
// introduces near zero would break that bit-exactness. MasterBus is a
// separate stage a caller applies to the buffer Engine::renderBlock() just
// filled, the same way PatternSequencer sits upstream of Engine rather than
// inside it -- composable, optional, and zero-cost if never called.
//
// Allocation-free and stateless across calls (every call only reads its own
// sample), so it's safe to use from the audio thread alongside Engine and
// VoiceManager/RoutingEngine.
class MasterBus {
public:
    explicit MasterBus(float ceiling = 1.0f) : ceiling_(ceiling) {}

    // The asymptote the output approaches as |input| -> infinity. Input is
    // never reflected past this value, only approaches it.
    void setCeiling(float ceiling) { ceiling_ = ceiling; }

    // Scales the input before saturation: higher drive pushes the same
    // input further around the curve toward ceiling_, without moving where
    // the curve flattens out. Below roughly ceiling_/drive_ in amplitude the
    // curve is close to linear, so quiet material passes through close to
    // unchanged.
    void setDrive(float drive) { drive_ = drive; }

    float process(float sample) const { return ceiling_ * std::tanh(sample * drive_ / ceiling_); }

    void processBlock(float* buffer, std::size_t numFrames) const {
        for (std::size_t i = 0; i < numFrames; ++i) buffer[i] = process(buffer[i]);
    }

private:
    float ceiling_;
    float drive_ = 1.0f;
};

} // namespace chilli
