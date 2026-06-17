// Deterministic test for the offline windowed-sinc resampler.
//
// No file I/O: synthetic sine tones stand in for "imported audio" so the test
// stays fast and reproducible. Checks the three properties that actually
// matter for an anti-aliasing resampler:
//   1. DC is preserved        (ideal lowpass has unity gain at 0 Hz)
//   2. Passband tones survive (signal below the new Nyquist keeps its energy)
//   3. Stopband tones are cut (signal above the new Nyquist is attenuated,
//                              not aliased back into the passband)
#include <cmath>
#include <cstdint>
#include <iostream>
#include <vector>

#include "Resampler.h"
#include "SampleBuffer.h"

namespace {

constexpr double PI = 3.14159265358979323846;

std::vector<float> makeSine(double freqHz, double rate, std::size_t numSamples) {
    std::vector<float> out(numSamples);
    for (std::size_t i = 0; i < numSamples; ++i) {
        out[i] = static_cast<float>(std::sin(2.0 * PI * freqHz * static_cast<double>(i) / rate));
    }
    return out;
}

// RMS over the interior of the buffer, skipping `edge` samples on each side
// where the truncated kernel window introduces transient error.
double rms(const std::vector<float>& x, std::size_t edge) {
    if (x.size() <= 2 * edge) return 0.0;
    double sumSq = 0.0;
    std::size_t n = 0;
    for (std::size_t i = edge; i < x.size() - edge; ++i) {
        sumSq += static_cast<double>(x[i]) * static_cast<double>(x[i]);
        ++n;
    }
    return std::sqrt(sumSq / static_cast<double>(n));
}

} // namespace

bool runResamplerTest() {
    constexpr double SRC_RATE = 48000.0;
    constexpr double DST_RATE = 24000.0; // downsample by 2 -> new Nyquist = 12 kHz
    constexpr std::size_t NUM_SAMPLES = 4800; // 0.1s at 48 kHz
    constexpr std::size_t EDGE = 96;           // skip kernel half-width * ~1.5 at each end
    constexpr double EXPECTED_SINE_RMS = 0.70710678; // 1/sqrt(2)

    bool noNaN = true;
    auto checkFinite = [&](const std::vector<float>& v) {
        for (float s : v) {
            if (!std::isfinite(s)) {
                noNaN = false;
                break;
            }
        }
    };

    // 1. DC preservation
    std::vector<float> dc(NUM_SAMPLES, 0.5f);
    auto dcOut = chilli::resampleBlackmanHarris(dc, SRC_RATE, DST_RATE);
    checkFinite(dcOut);
    double dcAvg = 0.0;
    for (std::size_t i = EDGE; i < dcOut.size() - EDGE; ++i) dcAvg += dcOut[i];
    dcAvg /= static_cast<double>(dcOut.size() - 2 * EDGE);
    const bool dcPreserved = std::abs(dcAvg - 0.5) < 0.01;

    // 2. Passband tone (1 kHz, well under the 12 kHz new Nyquist) keeps its energy
    auto passIn = makeSine(1000.0, SRC_RATE, NUM_SAMPLES);
    auto passOut = chilli::resampleBlackmanHarris(passIn, SRC_RATE, DST_RATE);
    checkFinite(passOut);
    const double passRms = rms(passOut, EDGE);
    const bool passbandPreserved = std::abs(passRms - EXPECTED_SINE_RMS) < 0.05;

    // 3. Stopband tone (16 kHz, above the 12 kHz new Nyquist) is attenuated, not aliased
    auto stopIn = makeSine(16000.0, SRC_RATE, NUM_SAMPLES);
    auto stopOut = chilli::resampleBlackmanHarris(stopIn, SRC_RATE, DST_RATE);
    checkFinite(stopOut);
    const double stopRms = rms(stopOut, EDGE);
    const bool stopbandAttenuated = stopRms < (EXPECTED_SINE_RMS * 0.1); // >20dB down

    // Sanity: SampleBuffer::fromDecodedPCM should round-trip the same data when
    // the source rate already matches the engine rate (no resampling needed).
    auto identity = chilli::SampleBuffer::fromDecodedPCM(passIn, SRC_RATE, SRC_RATE);
    const bool identityPassthrough = identity.samples == passIn && identity.sampleRate == SRC_RATE;

    std::cout << "Resampler Test Results:\n";
    std::cout << "  No NaN/Inf in any output:        " << (noNaN ? "PASS" : "FAIL") << "\n";
    std::cout << "  DC preserved (avg=" << dcAvg << "):       " << (dcPreserved ? "PASS" : "FAIL") << "\n";
    std::cout << "  Passband 1kHz RMS=" << passRms << ":   " << (passbandPreserved ? "PASS" : "FAIL") << "\n";
    std::cout << "  Stopband 16kHz RMS=" << stopRms << ":  " << (stopbandAttenuated ? "PASS" : "FAIL") << "\n";
    std::cout << "  SampleBuffer identity passthrough: " << (identityPassthrough ? "PASS" : "FAIL") << "\n";

    return noNaN && dcPreserved && passbandPreserved && stopbandAttenuated && identityPassthrough;
}

int main() {
    const bool ok = runResamplerTest();
    std::cout << (ok ? "Test: PASS" : "Test: FAIL") << "\n";
    return ok ? 0 : 1;
}
