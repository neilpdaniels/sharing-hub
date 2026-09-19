/* Prepare high-quality uploads using the browser's native media encoder. */
(() => {
  const prepared = new WeakSet();
  const submitting = new WeakSet();
  const passThrough = new WeakSet();
  const workerUrl = document.currentScript.dataset.workerUrl;
  const allowInsecureUpload = document.currentScript.dataset.allowInsecureUpload === 'true';

  async function compress(file, progress) {
    if (prepared.has(file)) return file;
    const worker = new Worker(workerUrl);
    let timer;
    try {
      const result = await new Promise((resolve, reject) => {
        worker.onmessage = ({data}) => {
          if (data.error) reject(new Error(data.error));
          else if (data.buffer) resolve(data);
          else if (data.progress !== undefined) progress(data.progress);
        };
        worker.onerror = () => reject(new Error('Unable to load video compression. Refresh the page and try again.'));
        timer = setTimeout(() => reject(new Error('Video preparation timed out. Please try a shorter recording.')), 15 * 60 * 1000);
        worker.postMessage(file);
      });
      const compressed = new File([result.buffer], file.name.replace(/\.[^.]+$/, '') + result.extension, {type: result.type});
      prepared.add(compressed);
      return compressed;
    } finally {
      clearTimeout(timer);
      worker.terminate();
    }
  }

  document.addEventListener('submit', async event => {
    const form = event.target;
    if (passThrough.delete(form)) return;
    const inputs = [...form.querySelectorAll('input[type=file]')]
      .filter(input => [...input.files].some(file => file.type.startsWith('video/')));
    if (!inputs.length) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (submitting.has(form)) return;
    submitting.add(form);
    form.dataset.videoBusy = "true";
    const submitter = event.submitter;
    let status = form.querySelector('[data-video-preparation]');
    if (!status) {
      status = document.createElement('div');
      status.dataset.videoPreparation = 'true';
      status.className = 'alert alert-info';
      status.setAttribute('role', 'status');
      form.appendChild(status);
    }
    if (submitter) submitter.disabled = true;
    try {
      if (!window.isSecureContext && allowInsecureUpload) {
        const tooLarge = inputs.some(input => [...input.files].some(file => file.size > 50 * 1024 * 1024));
        if (tooLarge) throw new Error('This development connection uploads the original video. Please choose a video under 50 MB.');
        status.textContent = 'Uploading original video from this development address. Keep this page open.';
        passThrough.add(form);
        if (submitter) submitter.disabled = false;
        form.requestSubmit(submitter || undefined);
        return;
      }
      for (const input of inputs) {
        const files = new DataTransfer();
        for (const file of input.files) {
          status.textContent = 'Preparing high-quality video… Keep this page open.';
          files.items.add(file.type.startsWith('video/') ? await compress(file, percent => {
            status.textContent = `Preparing video: ${percent}%. Keep this page open.`;
          }) : file);
        }
        input.files = files.files;
      }
      status.textContent = 'Video prepared. Uploading…';
      passThrough.add(form);
      if (submitter) submitter.disabled = false;
      form.requestSubmit(submitter || undefined);
    } catch (error) {
      status.className = 'alert alert-danger';
      status.textContent = error.message || 'Unable to prepare the video. Please try again.';
    } finally {
      submitting.delete(form);
      delete form.dataset.videoBusy;
      if (submitter) submitter.disabled = false;
    }
  }, true);
})();
