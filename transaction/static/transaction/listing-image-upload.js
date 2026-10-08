/* Resize listing photographs before upload.  This keeps ordinary phone photos
 * quick to upload while the server remains responsible for its final image
 * processing and validation. */
(function (window) {
  'use strict';

  var MAX_DIMENSION = 2000;
  var TARGET_BYTES = 3.5 * 1024 * 1024;
  var MAX_SOURCE_BYTES = 20 * 1024 * 1024;

  function loadImage(file) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(file);
      var image = new Image();
      image.onload = function () {
        URL.revokeObjectURL(url);
        resolve(image);
      };
      image.onerror = function () {
        URL.revokeObjectURL(url);
        reject(new Error('This image format cannot be prepared in this browser.'));
      };
      image.src = url;
    });
  }

  function canvasBlob(canvas, quality) {
    return new Promise(function (resolve, reject) {
      canvas.toBlob(function (blob) {
        if (blob) { resolve(blob); }
        else { reject(new Error('Your browser could not prepare this photo.')); }
      }, 'image/jpeg', quality);
    });
  }

  function jpegName(name) {
    return (name || 'listing-photo').replace(/\.[^.]+$/, '') + '.jpg';
  }

  async function prepareImage(file) {
    if (!file.type || file.type.indexOf('image/') !== 0 ||
        file.type === 'image/gif' || file.type === 'image/svg+xml') {
      return file;
    }

    var image;
    try {
      image = await loadImage(file);
    } catch (error) {
      if (file.size > MAX_SOURCE_BYTES) { throw error; }
      return file;
    }

    if (image.naturalWidth <= MAX_DIMENSION && image.naturalHeight <= MAX_DIMENSION &&
        file.size <= TARGET_BYTES) {
      return file;
    }

    var scale = Math.min(1, MAX_DIMENSION / image.naturalWidth, MAX_DIMENSION / image.naturalHeight);
    var width = Math.max(1, Math.round(image.naturalWidth * scale));
    var height = Math.max(1, Math.round(image.naturalHeight * scale));
    var canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    canvas.getContext('2d').drawImage(image, 0, 0, width, height);

    var quality = 0.84;
    var blob = await canvasBlob(canvas, quality);
    while (blob.size > TARGET_BYTES && quality > 0.5) {
      quality -= 0.08;
      blob = await canvasBlob(canvas, quality);
    }

    return new File([blob], jpegName(file.name), {
      type: 'image/jpeg',
      lastModified: file.lastModified
    });
  }

  async function prepare(files, onProgress) {
    var output = [];
    for (var i = 0; i < files.length; i += 1) {
      if (onProgress) { onProgress(i + 1, files.length); }
      output.push(await prepareImage(files[i]));
    }
    return output;
  }

  window.RentalutionListingImages = { prepare: prepare };
})(window);
