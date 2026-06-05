export interface AudioFeatures {
  energy:   number; // [0, 1]
  bass:     number; // [0, 1]
  treble:   number; // [0, 1]
  centroid: number; // [0, 1]
}

/**
 * Captures microphone audio and extracts real-time spectral features
 * using the Web Audio API AnalyserNode.
 */
export class AudioInputEngine {
  private ctx!: AudioContext;
  private analyser!: AnalyserNode;
  private dataArray!: Uint8Array<ArrayBuffer>;

  public features: AudioFeatures = { energy: 0, bass: 0, treble: 0, centroid: 0 };

  async init(): Promise<void> {
    this.ctx = new AudioContext();
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 1024;
    this.dataArray = new Uint8Array(this.analyser.frequencyBinCount) as Uint8Array<ArrayBuffer>;
  }

  async connectMicrophone(): Promise<void> {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const source = this.ctx.createMediaStreamSource(stream);
    source.connect(this.analyser);
  }

  /** Call on each animation frame to update features. */
  update(): AudioFeatures {
    this.analyser.getByteFrequencyData(this.dataArray);

    let bassSum = 0;
    let trebleSum = 0;
    let totalSum = 0;

    for (let i = 0; i < this.dataArray.length; i++) {
      const v = this.dataArray[i] ?? 0;
      totalSum += v;
      if (i < 10) bassSum  += v;  // sub-bass / bass bins
      if (i > 60) trebleSum += v; // upper mid / treble bins
    }

    const count = this.dataArray.length;
    this.features = {
      energy:   totalSum / (count * 255),
      bass:     bassSum  / (10 * 255),
      treble:   trebleSum / ((count - 61) * 255),
      centroid: totalSum  / (count * 255),
    };

    return this.features;
  }

  suspend(): void {
    this.ctx?.suspend();
  }

  resume(): void {
    this.ctx?.resume();
  }
}
