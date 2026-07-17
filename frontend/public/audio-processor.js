class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    // We want 30ms buffers. 16000 * 0.03 = 480 samples.
    this.bufferSize = 480; 
    this.buffer = new Int16Array(this.bufferSize);
    this.bufferIndex = 0;
    this.sourceIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const channelData = input[0]; // mono channel

    // sampleRate is a global constant in the AudioWorkletProcessor environment
    const ratio = sampleRate / this.targetSampleRate;

    for (let i = 0; i < channelData.length; i++) {
      this.sourceIndex += 1;
      if (this.sourceIndex >= ratio) {
        this.sourceIndex -= ratio;

        // Grab sample and clamp to [-1.0, 1.0]
        let sample = channelData[i];
        if (sample > 1.0) sample = 1.0;
        else if (sample < -1.0) sample = -1.0;

        // Convert Float32 [-1.0, 1.0] to Int16 [-32768, 32767]
        let intVal = Math.floor(sample * 32768);
        if (intVal > 32767) intVal = 32767;
        else if (intVal < -32768) intVal = -32768;

        this.buffer[this.bufferIndex++] = intVal;

        // When buffer is full (480 samples = 30ms of 16kHz audio), send to main thread
        if (this.bufferIndex >= this.bufferSize) {
          // Send a copy of the raw Int16 PCM array to main thread
          this.port.postMessage(this.buffer.slice(0));
          this.bufferIndex = 0;
        }
      }
    }

    return true;
  }
}

registerProcessor('audio-processor', AudioProcessor);
