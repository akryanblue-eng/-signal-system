#pragma once

#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <optional>
#include <vector>

namespace chilli {

struct DecodedAudio {
    std::vector<float> samples; // mono, normalized to [-1, 1]
    double sampleRate = 0.0;
};

namespace detail {

inline uint32_t readU32LE(const uint8_t* p) {
    return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
           (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
}
inline uint16_t readU16LE(const uint8_t* p) {
    return static_cast<uint16_t>(p[0]) | static_cast<uint16_t>(static_cast<uint16_t>(p[1]) << 8);
}

inline int32_t signExtend24(uint32_t v) {
    if (v & 0x00800000u) v |= 0xFF000000u;
    return static_cast<int32_t>(v);
}

inline bool isSupportedFormat(uint16_t formatTag, uint16_t bitsPerSample) {
    if (formatTag == 1) { // integer PCM
        return bitsPerSample == 8 || bitsPerSample == 16 || bitsPerSample == 24 || bitsPerSample == 32;
    }
    if (formatTag == 3) { // IEEE float
        return bitsPerSample == 32;
    }
    return false;
}

inline float decodeOneSample(const uint8_t* s, uint16_t formatTag, uint16_t bitsPerSample) {
    if (formatTag == 3) {
        float f;
        std::memcpy(&f, s, sizeof(float));
        return f;
    }
    switch (bitsPerSample) {
        case 8:
            return (static_cast<float>(s[0]) - 128.0f) / 128.0f;
        case 16: {
            int16_t raw;
            std::memcpy(&raw, s, sizeof(int16_t));
            return static_cast<float>(raw) / 32768.0f;
        }
        case 24: {
            const uint32_t raw = static_cast<uint32_t>(s[0]) | (static_cast<uint32_t>(s[1]) << 8) |
                                  (static_cast<uint32_t>(s[2]) << 16);
            return static_cast<float>(signExtend24(raw)) / 8388608.0f; // 2^23
        }
        case 32: {
            int32_t raw;
            std::memcpy(&raw, s, sizeof(int32_t));
            return static_cast<float>(raw) / 2147483648.0f; // 2^31
        }
        default:
            return 0.0f;
    }
}

} // namespace detail

// Minimal, dependency-free decoder for canonical PCM WAV: format tag 1
// (integer PCM, 8/16/24/32-bit) and format tag 3 (32-bit IEEE float).
// Multi-channel files are downmixed to mono by averaging channels, since
// every voice in this engine plays a single-channel sample. Anything else
// (ADPCM, WAVE_FORMAT_EXTENSIBLE, compressed formats) returns std::nullopt
// rather than silently misinterpreting the bytes.
inline std::optional<DecodedAudio> decodeWavFile(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return std::nullopt;

    std::vector<uint8_t> data((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    if (data.size() < 12 || std::memcmp(data.data(), "RIFF", 4) != 0 ||
        std::memcmp(data.data() + 8, "WAVE", 4) != 0) {
        return std::nullopt;
    }

    uint16_t formatTag = 0, numChannels = 0, bitsPerSample = 0;
    uint32_t sampleRate = 0;
    const uint8_t* pcmData = nullptr;
    uint32_t pcmSize = 0;

    std::size_t pos = 12;
    while (pos + 8 <= data.size()) {
        const uint32_t chunkSize = detail::readU32LE(&data[pos + 4]);
        const std::size_t chunkDataStart = pos + 8;
        if (chunkDataStart + chunkSize > data.size()) break; // truncated/corrupt

        if (std::memcmp(&data[pos], "fmt ", 4) == 0 && chunkSize >= 16) {
            const uint8_t* f = &data[chunkDataStart];
            formatTag = detail::readU16LE(f + 0);
            numChannels = detail::readU16LE(f + 2);
            sampleRate = detail::readU32LE(f + 4);
            bitsPerSample = detail::readU16LE(f + 14);
        } else if (std::memcmp(&data[pos], "data", 4) == 0) {
            pcmData = &data[chunkDataStart];
            pcmSize = chunkSize;
        }

        pos = chunkDataStart + chunkSize + (chunkSize % 2); // chunks are word-aligned
    }

    if (pcmData == nullptr || numChannels == 0 || sampleRate == 0) return std::nullopt;
    if (!detail::isSupportedFormat(formatTag, bitsPerSample)) return std::nullopt;

    const std::size_t bytesPerSample = bitsPerSample / 8;
    const std::size_t frameStride = bytesPerSample * numChannels;
    if (frameStride == 0) return std::nullopt;
    const std::size_t numFrames = pcmSize / frameStride;

    DecodedAudio out;
    out.sampleRate = static_cast<double>(sampleRate);
    out.samples.resize(numFrames);

    for (std::size_t i = 0; i < numFrames; ++i) {
        float frameSum = 0.0f;
        const uint8_t* frame = pcmData + i * frameStride;
        for (uint16_t ch = 0; ch < numChannels; ++ch) {
            frameSum += detail::decodeOneSample(frame + ch * bytesPerSample, formatTag, bitsPerSample);
        }
        out.samples[i] = frameSum / static_cast<float>(numChannels);
    }

    return out;
}

} // namespace chilli
