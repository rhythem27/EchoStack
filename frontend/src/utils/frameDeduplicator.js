/**
 * Structural Video Frame Deduplication Utility (SSIM)
 * Downsamples HTML5 Canvas frames to a low-res matrix (e.g. 64x64) and computes
 * Structural Similarity Index (SSIM) and Mean Absolute Error (MAE) against previous frames.
 * Prevents redundant static video frames from consuming bandwidth and vision API tokens.
 */
export class FrameDeduplicator {
  constructor(options = {}) {
    this.matrixSize = options.matrixSize || 64; // 64x64 sampling grid
    this.threshold = options.threshold !== undefined ? options.threshold : 0.15; // SSIM diff threshold
    this.forceKeyframeIntervalMs = options.forceKeyframeIntervalMs || 15000; // Force resend keyframe every 15s

    // Offscreen canvas setup
    this.canvas = document.createElement('canvas');
    this.canvas.width = this.matrixSize;
    this.canvas.height = this.matrixSize;
    this.ctx = this.canvas.getContext('2d', { willReadFrequently: true });

    // Internal state
    this.previousMatrix = null;
    this.lastSentTime = 0;

    // Telemetry counters
    this.totalFrames = 0;
    this.sentFrames = 0;
    this.skippedFrames = 0;
    this.lastDiff = 0.0;
  }

  /**
   * Resets all internal frame buffers and stats counters.
   */
  reset() {
    this.previousMatrix = null;
    this.lastSentTime = 0;
    this.totalFrames = 0;
    this.sentFrames = 0;
    this.skippedFrames = 0;
    this.lastDiff = 0.0;
  }

  /**
   * Configures a new difference threshold.
   * @param {number} newThreshold - New diff threshold (0.0 to 1.0)
   */
  setThreshold(newThreshold) {
    if (typeof newThreshold === 'number' && !isNaN(newThreshold)) {
      this.threshold = Math.max(0.01, Math.min(1.0, newThreshold));
    }
  }

  /**
   * Computes downsampled grayscale luminance array (Y = 0.299R + 0.587G + 0.114B).
   * @private
   */
  _extractGrayscaleMatrix(sourceCanvas) {
    this.ctx.clearRect(0, 0, this.matrixSize, this.matrixSize);
    this.ctx.drawImage(sourceCanvas, 0, 0, this.matrixSize, this.matrixSize);
    const imgData = this.ctx.getImageData(0, 0, this.matrixSize, this.matrixSize).data;
    const numPixels = this.matrixSize * this.matrixSize;
    const gray = new Float32Array(numPixels);

    for (let i = 0; i < numPixels; i++) {
      const offset = i * 4;
      gray[i] = 0.299 * imgData[offset] + 0.587 * imgData[offset + 1] + 0.114 * imgData[offset + 2];
    }
    return gray;
  }

  /**
   * Calculates Structural Similarity Index (SSIM) between two grayscale arrays.
   * SSIM value ranges from -1.0 to 1.0 (1.0 = perfectly identical).
   * @private
   */
  _computeSSIM(arr1, arr2) {
    const n = arr1.length;
    let sumX = 0;
    let sumY = 0;

    for (let i = 0; i < n; i++) {
      sumX += arr1[i];
      sumY += arr2[i];
    }
    const muX = sumX / n;
    const muY = sumY / n;

    let varX = 0;
    let varY = 0;
    let covXY = 0;

    for (let i = 0; i < n; i++) {
      const devX = arr1[i] - muX;
      const devY = arr2[i] - muY;
      varX += devX * devX;
      varY += devY * devY;
      covXY += devX * devY;
    }
    varX /= n;
    varY /= n;
    covXY /= n;

    // Standard SSIM stability constants for 8-bit dynamic range (L=255)
    const C1 = (0.01 * 255) ** 2; // 6.5025
    const C2 = (0.03 * 255) ** 2; // 58.5225

    const num = (2 * muX * muY + C1) * (2 * covXY + C2);
    const den = (muX * muX + muY * muY + C1) * (varX + varY + C2);

    return den === 0 ? 1.0 : num / den;
  }

  /**
   * Calculates Mean Absolute Error (MAE) normalized between 0.0 and 1.0.
   * @private
   */
  _computeMAE(arr1, arr2) {
    const n = arr1.length;
    let diffSum = 0;
    for (let i = 0; i < n; i++) {
      diffSum += Math.abs(arr1[i] - arr2[i]);
    }
    return diffSum / (n * 255);
  }

  /**
   * Processes current source HTML5 Canvas frame and decides whether it should be sent.
   * @param {HTMLCanvasElement} sourceCanvas - Active camera/screen capture canvas element
   * @returns {Object} { shouldSend: boolean, diff: number, isKeyframe: boolean, stats: Object }
   */
  processFrame(sourceCanvas) {
    if (!sourceCanvas || sourceCanvas.width === 0 || sourceCanvas.height === 0) {
      return { shouldSend: false, diff: 0, isKeyframe: false, stats: this.getStats() };
    }

    const now = Date.now();
    const currentMatrix = this._extractGrayscaleMatrix(sourceCanvas);

    // Initial frame or forced keyframe trigger
    const isForceKeyframe = this.previousMatrix !== null && (now - this.lastSentTime >= this.forceKeyframeIntervalMs);
    const isFirstFrame = this.previousMatrix === null;

    if (isFirstFrame || isForceKeyframe) {
      this.previousMatrix = currentMatrix;
      this.lastSentTime = now;
      this.totalFrames++;
      this.sentFrames++;
      this.lastDiff = 1.0;

      return {
        shouldSend: true,
        diff: 1.0,
        isKeyframe: true,
        stats: this.getStats()
      };
    }

    // Calculate SSIM and MAE difference
    const ssim = this._computeSSIM(this.previousMatrix, currentMatrix);
    const ssimDiff = Math.max(0, 1.0 - ssim);
    const maeDiff = this._computeMAE(this.previousMatrix, currentMatrix);

    // Combined effective difference score
    const effectiveDiff = Math.max(ssimDiff, maeDiff);
    this.lastDiff = effectiveDiff;

    if (effectiveDiff >= this.threshold) {
      this.previousMatrix = currentMatrix;
      this.lastSentTime = now;
      this.totalFrames++;
      this.sentFrames++;

      return {
        shouldSend: true,
        diff: effectiveDiff,
        isKeyframe: false,
        stats: this.getStats()
      };
    } else {
      this.totalFrames++;
      this.skippedFrames++;

      return {
        shouldSend: false,
        diff: effectiveDiff,
        isKeyframe: false,
        stats: this.getStats()
      };
    }
  }

  /**
   * Retrieves summary telemetry statistics.
   * @returns {Object} Telemetry statistics
   */
  getStats() {
    const skipPercentage = this.totalFrames > 0 
      ? Math.round((this.skippedFrames / this.totalFrames) * 100) 
      : 0;

    return {
      totalFrames: this.totalFrames,
      sentFrames: this.sentFrames,
      skippedFrames: this.skippedFrames,
      skipPercentage,
      lastDiff: Number(this.lastDiff.toFixed(4)),
      threshold: this.threshold
    };
  }
}

export default FrameDeduplicator;
