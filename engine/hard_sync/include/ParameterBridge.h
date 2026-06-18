#pragma once

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <type_traits>

// Lock-free single-writer/multi-reader snapshot publisher. publish() is
// called from whichever thread owns control-domain mutation (UI thread,
// host automation callback, a future network/OSC/MIDI control path); acquire()
// is called from any number of reader threads (typically the audio thread,
// but the design doesn't depend on that) and never blocks or allocates.
//
// Exactly one thread may call publish() at a time -- this is a contract,
// not something this class arbitrates. A second concurrent publisher would
// turn the slot-selection logic below into its own data race (two threads
// computing "the slot one past current" from the same stale read and
// colliding on it). Funnel every mutation source (UI, MIDI, host automation,
// state restore) through a single control-domain caller upstream of this
// class rather than letting them call publish() directly; that keeps this
// primitive's correctness argument to the single-writer case it's actually
// built for, instead of growing CAS loops and writer arbitration to support
// multiple publishers, which is complexity this design exists to avoid.
//
// Three slots, not two: a publish always advances to the slot one past
// whatever's currently published, so it never overwrites the slot a reader
// might still be holding. With only two slots that guarantee breaks the
// moment a second publish happens before the first reader is done -- a
// single long-running acquire() (e.g. spanning an oversized offline render)
// can legitimately outlast more than one control-domain update. With three,
// the slot a reader is on survives two more publishes before it's reused.
// That is a bounded guarantee, not an unconditional one: there is
// deliberately no reclamation protocol here (epochs, refcounts, hazard
// pointers), so a reader stalled across three or more publishes could still
// race a fourth. Closing that for an unbounded number of in-flight readers
// is separate, larger work a future multi-reader design would need.
//
// Deliberately just publish/acquire/generation and nothing else -- no
// smoothing, no automation curves, no parameter metadata, no validation.
// Those are the caller's concern; this primitive's only job is making "the
// latest published T" available to readers without a lock.
//
// Invariants this class maintains:
//   1. Exactly one publishing thread (caller's contract, see above).
//   2. Any number of reader threads; readers never write.
//   3. A returned Snapshot is an immutable copy, owned outright by the
//      reader -- never aliased, never mutated out from under it.
//   4. generation strictly increases with every publish() call.
//   5. A reader may observe generation skip ahead (multiple publishes
//      happened between two of its acquire() calls) but never go backwards,
//      and never see a state/generation pairing that didn't come from the
//      same publish() call (acquire() reads both together, in one go).
//
// T must be trivially copyable: this class moves/copies it with no
// awareness of its contents, and the whole acquire()-returns-an-owned-copy
// guarantee above depends on that copy being a flat, complete, side-effect-
// free duplication. A T containing heap pointers, std::vector/std::string,
// virtual dispatch, or its own internal locking would silently break every
// guarantee this class makes.
template <typename T>
class ParameterBridge {
    static_assert(std::is_trivially_copyable<T>::value,
                  "ParameterBridge<T> requires T to be trivially copyable -- a binary blob, not a graph");

public:
    struct Snapshot {
        T state{};
        // Monotonically increasing with every publish(), independent of
        // whether the published value actually changed -- a diagnostic /
        // replay trail, not a dedup signal.
        uint64_t generation = 0;
    };

    // Writer side: builds the next snapshot, stamps a fresh generation, then
    // makes it visible with a release store -- paired with the acquire load
    // in acquire() below, this guarantees a reader never observes a
    // partially-written Snapshot, no matter when it reads relative to this
    // write.
    void publish(T value) {
        const uint32_t cur = published_.load(std::memory_order_relaxed);
        const uint32_t slot = (cur + 1) % kSlots;
        snapshots_[slot].state = std::move(value);
        snapshots_[slot].generation = ++generationCounter_;
        published_.store(slot, std::memory_order_release);
    }

    // Reader side: the acquire load paired with publish()'s release store
    // guarantees every field of the returned Snapshot, as written by that
    // publish, is visible here too. Returns a copy rather than a reference
    // into snapshots_: a reference would still be subject to the
    // two-publishes-ahead bound documented above (a reader holding it across
    // three or more subsequent publishes could observe it change mid-read),
    // and T here is small/POD-like enough that the copy is unconditionally
    // safe for the reader to hold for as long as it likes -- no bound, no
    // asterisk -- for a cost real-time code can afford.
    Snapshot acquire() const noexcept {
        const uint32_t idx = published_.load(std::memory_order_acquire);
        return snapshots_[idx];
    }

private:
    static constexpr uint32_t kSlots = 3;

    std::array<Snapshot, kSlots> snapshots_{};
    std::atomic<uint32_t> published_{0};
    uint64_t generationCounter_ = 0;
};
