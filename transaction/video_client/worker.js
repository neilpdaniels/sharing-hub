import {Input, BlobSource, ALL_FORMATS, Output, BufferTarget, Conversion,
  Mp4OutputFormat, WebMOutputFormat, canEncodeVideo, canEncodeAudio, Quality} from 'mediabunny';

self.onmessage = async ({data: file}) => {
  let input;
  let conversion;
  try {
    if (!self.VideoEncoder || !self.AudioEncoder) {
      throw new Error('Video compression requires a current browser over HTTPS. Please use the mobile app on this device.');
    }
    input = new Input({source: new BlobSource(file), formats: ALL_FORMATS});
    const video = await input.getPrimaryVideoTrack();
    if (!video) throw new Error('No readable video track found.');
    const width = await video.getDisplayWidth();
    const height = await video.getDisplayHeight();
    const scale = Math.min(1, 1920 / Math.max(width, height), 1080 / Math.min(width, height));
    const outWidth = Math.max(2, Math.floor(width * scale / 2) * 2);
    const outHeight = Math.max(2, Math.floor(height * scale / 2) * 2);
    const mp4 = await canEncodeVideo('avc', {width: outWidth, height: outHeight}) && await canEncodeAudio('aac');
    const target = new BufferTarget();
    const output = new Output({format: mp4 ? new Mp4OutputFormat({fastStart: 'in-memory'}) : new WebMOutputFormat(), target});
    conversion = await Conversion.init({input, output,
      video: {width: outWidth, height: outHeight, fit: 'contain', frameRate: 30,
        codec: mp4 ? 'avc' : 'vp9', quality: new Quality({bitrate: 6000000}), forceTranscode: true},
      audio: {codec: mp4 ? 'aac' : 'opus', quality: new Quality({bitrate: 128000}), forceTranscode: true},
    });
    if (!conversion.isValid || conversion.discardedTracks.some(({track}) => ['video', 'audio'].includes(track.type))) {
      console.warn('Video conversion unsupported:', conversion.discardedTracks.map(({track, reason}) => ({type: track.type, reason})));
      throw new Error('This browser cannot preserve all video and audio tracks. Please use the mobile app or another recording.');
    }
    let oversized = false;
    target.onwrite = (_start, end) => {
      if (end > 50 * 1024 * 1024) {
        oversized = true;
        void conversion.cancel();
      }
    };
    conversion.onProgress = progress => self.postMessage({progress: Math.floor(progress * 100)});
    try {
      await conversion.execute();
    } catch (error) {
      if (oversized) throw new Error('The compressed video is over 50 MB. Please use a shorter recording.');
      throw error;
    }
    if (!target.buffer?.byteLength || target.buffer.byteLength > 50 * 1024 * 1024) {
      throw new Error('Please choose a shorter recording (50 MB maximum after compression).');
    }
    self.postMessage({buffer: target.buffer, type: mp4 ? 'video/mp4' : 'video/webm', extension: mp4 ? '.mp4' : '.webm'}, [target.buffer]);
  } catch (error) {
    self.postMessage({error: error.message || 'Unable to compress this video. Please try another recording.'});
  } finally {
    input?.dispose();
  }
};
