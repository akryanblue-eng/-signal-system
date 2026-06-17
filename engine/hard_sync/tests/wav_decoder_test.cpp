// Deterministic test for the dependency-free WAV decoder.
//
// There are no on-disk fixture files: every test builds its own minimal
// RIFF/WAVE byte buffer in memory (including odd-sized padding chunks and
// malformed headers) and feeds it to decodeWavFile via a temp file, so the
// test is fully self-contained and exercises the exact chunk-walking logic
// the decoder uses on real-world files.
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <vector>

#include "WavDecoder.h"

namespace {

void appendU32LE(std::vector<uint8_t>& out, uint32_t v) {
    out.push_back(static_cast<uint8_t>(v & 0xFF));
    out.push_back(static_cast<uint8_t>((v >> 8) & 0xFF));
    out.push_back(static_cast<uint8_t>((v >> 16) & 0xFF));
    out.push_back(static_cast<uint8_t>((v >> 24) & 0xFF));
}
void appendU16LE(std::vector<uint8_t>& out, uint16_t v) {
    out.push_back(static_cast<uint8_t>(v & 0xFF));
    out.push_back(static_cast<uint8_t>((v >> 8) & 0xFF));
}
void appendTag(std::vector<uint8_t>& out, const char* tag) {
    out.insert(out.end(), tag, tag + 4);
}

// Builds a canonical RIFF/WAVE byte buffer with a "fmt " chunk and a "data"
// chunk, optionally preceded by a junk chunk of arbitrary (possibly odd)
// size to exercise word-alignment padding skip logic.
std::vector<uint8_t> buildWav(uint16_t formatTag, uint16_t numChannels, uint32_t sampleRate,
                               uint16_t bitsPerSample, const std::vector<uint8_t>& pcmBytes,
                               std::size_t junkChunkSize = 0) {
    std::vector<uint8_t> fmtChunk;
    appendU16LE(fmtChunk, formatTag);
    appendU16LE(fmtChunk, numChannels);
    appendU32LE(fmtChunk, sampleRate);
    const uint32_t byteRate = sampleRate * numChannels * (bitsPerSample / 8);
    appendU32LE(fmtChunk, byteRate);
    appendU16LE(fmtChunk, static_cast<uint16_t>(numChannels * (bitsPerSample / 8)));
    appendU16LE(fmtChunk, bitsPerSample);

    std::vector<uint8_t> body;
    appendTag(body, "WAVE");

    appendTag(body, "fmt ");
    appendU32LE(body, static_cast<uint32_t>(fmtChunk.size()));
    body.insert(body.end(), fmtChunk.begin(), fmtChunk.end());

    if (junkChunkSize > 0) {
        appendTag(body, "JUNK");
        appendU32LE(body, static_cast<uint32_t>(junkChunkSize));
        body.insert(body.end(), junkChunkSize, 0xAB);
        if (junkChunkSize % 2 != 0) body.push_back(0x00); // word-align padding
    }

    appendTag(body, "data");
    appendU32LE(body, static_cast<uint32_t>(pcmBytes.size()));
    body.insert(body.end(), pcmBytes.begin(), pcmBytes.end());
    if (pcmBytes.size() % 2 != 0) body.push_back(0x00);

    std::vector<uint8_t> out;
    appendTag(out, "RIFF");
    appendU32LE(out, static_cast<uint32_t>(body.size()));
    out.insert(out.end(), body.begin(), body.end());
    return out;
}

std::filesystem::path writeTempFile(const std::vector<uint8_t>& bytes, const char* name) {
    const auto path = std::filesystem::temp_directory_path() / name;
    std::ofstream out(path, std::ios::binary);
    out.write(reinterpret_cast<const char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    return path;
}

} // namespace

bool runWavDecoderTest() {
    bool allPass = true;

    // 1. 16-bit mono round trip: known sample values decode to the exact
    // expected normalized floats.
    {
        const std::vector<int16_t> raw = {0, 16384, -16384, 32767, -32768};
        std::vector<uint8_t> pcm;
        for (int16_t s : raw) {
            pcm.push_back(static_cast<uint8_t>(s & 0xFF));
            pcm.push_back(static_cast<uint8_t>((s >> 8) & 0xFF));
        }
        const auto wav = buildWav(1, 1, 44100, 16, pcm);
        const auto path = writeTempFile(wav, "chilli_wav_test_16bit_mono.wav");
        const auto decoded = chilli::decodeWavFile(path);
        std::filesystem::remove(path);

        bool ok = decoded.has_value();
        if (ok) {
            ok &= decoded->sampleRate == 44100.0;
            ok &= decoded->samples.size() == raw.size();
            for (std::size_t i = 0; ok && i < raw.size(); ++i) {
                const float expected = static_cast<float>(raw[i]) / 32768.0f;
                ok &= decoded->samples[i] == expected;
            }
        }
        std::cout << "  16-bit mono round trip (exact):    " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 2. Stereo downmix: L=+1.0, R=-1.0 on every frame must average to 0.0.
    {
        constexpr std::size_t kFrames = 8;
        std::vector<uint8_t> pcm;
        for (std::size_t i = 0; i < kFrames; ++i) {
            const int16_t left = 32767;
            const int16_t right = -32767;
            pcm.push_back(static_cast<uint8_t>(left & 0xFF));
            pcm.push_back(static_cast<uint8_t>((left >> 8) & 0xFF));
            pcm.push_back(static_cast<uint8_t>(right & 0xFF));
            pcm.push_back(static_cast<uint8_t>((right >> 8) & 0xFF));
        }
        const auto wav = buildWav(1, 2, 48000, 16, pcm);
        const auto path = writeTempFile(wav, "chilli_wav_test_stereo_downmix.wav");
        const auto decoded = chilli::decodeWavFile(path);
        std::filesystem::remove(path);

        bool ok = decoded.has_value();
        if (ok) {
            ok &= decoded->samples.size() == kFrames;
            for (float s : decoded->samples) ok &= (s == 0.0f);
        }
        std::cout << "  Stereo downmix (+1/-1 -> 0.0):     " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 3. 32-bit IEEE float passthrough: values pass through with full precision.
    {
        const std::vector<float> raw = {0.0f, 0.5f, -0.75f, 1.0f, -1.0f, 0.123456f};
        std::vector<uint8_t> pcm(raw.size() * sizeof(float));
        std::memcpy(pcm.data(), raw.data(), pcm.size());
        const auto wav = buildWav(3, 1, 96000, 32, pcm);
        const auto path = writeTempFile(wav, "chilli_wav_test_float32.wav");
        const auto decoded = chilli::decodeWavFile(path);
        std::filesystem::remove(path);

        bool ok = decoded.has_value();
        if (ok) {
            ok &= decoded->sampleRate == 96000.0;
            ok &= decoded->samples.size() == raw.size();
            for (std::size_t i = 0; ok && i < raw.size(); ++i) ok &= decoded->samples[i] == raw[i];
        }
        std::cout << "  32-bit float passthrough (exact):  " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 4. Word-alignment padding: an odd-sized junk chunk before "data" must
    // be skipped correctly so the data chunk is still found and parsed.
    {
        const std::vector<int16_t> raw = {100, -200, 300};
        std::vector<uint8_t> pcm;
        for (int16_t s : raw) {
            pcm.push_back(static_cast<uint8_t>(s & 0xFF));
            pcm.push_back(static_cast<uint8_t>((s >> 8) & 0xFF));
        }
        const auto wav = buildWav(1, 1, 44100, 16, pcm, /*junkChunkSize=*/5); // odd size
        const auto path = writeTempFile(wav, "chilli_wav_test_padding.wav");
        const auto decoded = chilli::decodeWavFile(path);
        std::filesystem::remove(path);

        bool ok = decoded.has_value() && decoded->samples.size() == raw.size();
        for (std::size_t i = 0; ok && i < raw.size(); ++i) {
            ok &= decoded->samples[i] == static_cast<float>(raw[i]) / 32768.0f;
        }
        std::cout << "  Odd-sized chunk padding skipped:   " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    // 5. Malformed input is rejected, not misinterpreted: bad magic, no data
    // chunk, and an unsupported format tag all must return nullopt.
    {
        auto wav = buildWav(1, 1, 44100, 16, {0, 0, 0, 0});
        wav[0] = 'X'; // corrupt "RIFF" magic
        const auto path = writeTempFile(wav, "chilli_wav_test_bad_magic.wav");
        const bool rejectsBadMagic = !chilli::decodeWavFile(path).has_value();
        std::filesystem::remove(path);

        // No data chunk: fmt-only body.
        std::vector<uint8_t> fmtChunk;
        appendU16LE(fmtChunk, 1);
        appendU16LE(fmtChunk, 1);
        appendU32LE(fmtChunk, 44100);
        appendU32LE(fmtChunk, 88200);
        appendU16LE(fmtChunk, 2);
        appendU16LE(fmtChunk, 16);
        std::vector<uint8_t> body;
        appendTag(body, "WAVE");
        appendTag(body, "fmt ");
        appendU32LE(body, static_cast<uint32_t>(fmtChunk.size()));
        body.insert(body.end(), fmtChunk.begin(), fmtChunk.end());
        std::vector<uint8_t> noDataWav;
        appendTag(noDataWav, "RIFF");
        appendU32LE(noDataWav, static_cast<uint32_t>(body.size()));
        noDataWav.insert(noDataWav.end(), body.begin(), body.end());
        const auto path2 = writeTempFile(noDataWav, "chilli_wav_test_no_data.wav");
        const bool rejectsMissingData = !chilli::decodeWavFile(path2).has_value();
        std::filesystem::remove(path2);

        // Unsupported format tag (e.g. ADPCM == 2).
        const auto adpcmWav = buildWav(2, 1, 44100, 4, {0, 0, 0, 0});
        const auto path3 = writeTempFile(adpcmWav, "chilli_wav_test_unsupported_format.wav");
        const bool rejectsUnsupportedFormat = !chilli::decodeWavFile(path3).has_value();
        std::filesystem::remove(path3);

        const bool ok = rejectsBadMagic && rejectsMissingData && rejectsUnsupportedFormat;
        std::cout << "  Malformed input rejected (no crash/misparse): " << (ok ? "PASS" : "FAIL") << "\n";
        allPass &= ok;
    }

    return allPass;
}

int main() {
    std::cout << "WavDecoder Test Results:\n";
    const bool ok = runWavDecoderTest();
    std::cout << (ok ? "Test: PASS" : "Test: FAIL") << "\n";
    return ok ? 0 : 1;
}
