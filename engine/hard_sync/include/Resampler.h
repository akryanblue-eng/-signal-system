#pragma once

#include <algorithm>
#include <cmath>
#include <vector>

namespace chilli {

// Blackman-Harris window. n ranges over [0, M]; returns the tap weight at n.
inline double blackmanHarris(double n, double M) {
    constexpr double a0 = 0.35875;
    constexpr double a1 = 0.48829;
    constexpr double a2 = 0.14128;
    constexpr double a3 = 0.01168;
    const double arg = (2.0 * M_PI * n) / M;
    return a0 - a1 * std::cos(arg) + a2 * std::cos(2.0 * arg) - a3 * std::cos(3.0 * arg);
}

inline double sinc(double x) {
    if (std::abs(x) < 1e-9) return 1.0;
    const double px = M_PI * x;
    return std::sin(px) / px;
}

// Offline, band-limited windowed-sinc resampler. Not real-time safe (allocates,
// no bounded time budget) by design -- this belongs in the sample import path,
// never the audio render path, so it can afford a wide kernel and a
// Blackman-Harris window for strong stopband rejection instead of the cheap
// linear interpolation used by the real-time voice (getInterpolatedSample).
//
// halfWidth taps are summed on each side of the ideal (fractional) source
// position. When downsampling, the kernel's cutoff is narrowed to the new
// Nyquist so content above it is attenuated by the window instead of folding
// back as aliasing.
inline std::vector<float> resampleBlackmanHarris(const std::vector<float>& input,
                                                  double srcRate,
                                                  double dstRate,
                                                  int halfWidth = 32) {
    if (input.empty() || srcRate <= 0.0 || dstRate <= 0.0) return {};
    if (srcRate == dstRate) return input;

    const double ratio = srcRate / dstRate;             // input samples per output sample
    const double cutoff = std::min(1.0, dstRate / srcRate);
    const double M = 2.0 * halfWidth;                   // window support width

    const std::size_t outLen =
        static_cast<std::size_t>(std::floor((input.size() - 1) / ratio)) + 1;
    std::vector<float> output(outLen, 0.0f);

    for (std::size_t outIdx = 0; outIdx < outLen; ++outIdx) {
        const double srcPos = static_cast<double>(outIdx) * ratio;
        const long center = static_cast<long>(std::floor(srcPos));
        const double frac = srcPos - static_cast<double>(center);

        double acc = 0.0;
        for (long k = -halfWidth + 1; k <= halfWidth; ++k) {
            const long srcIdx = center + k;
            if (srcIdx < 0 || srcIdx >= static_cast<long>(input.size())) continue;

            const double d = static_cast<double>(k) - frac; // distance from ideal pos to this tap
            const double windowArg = d + halfWidth;          // shift into [0, M] for the window
            if (windowArg < 0.0 || windowArg > M) continue;

            const double weight = cutoff * sinc(cutoff * d) * blackmanHarris(windowArg, M);
            acc += input[static_cast<std::size_t>(srcIdx)] * weight;
        }
        output[outIdx] = static_cast<float>(acc);
    }
    return output;
}

} // namespace chilli
