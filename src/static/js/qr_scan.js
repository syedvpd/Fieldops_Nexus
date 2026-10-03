/* M12 camera scanning: isolated, progressive enhancement. Uses the browser BarcodeDetector API where it exists;
   everywhere else the typed-code form on the page keeps working. The scanned text is only SUBMITTED to the server,
   which authorizes the caller after resolving it. */
(function () {
  "use strict";
  var camera = document.getElementById("scan-camera");
  if (!camera) { return; }
  var startBtn = document.getElementById("scan-start");
  var stopBtn = document.getElementById("scan-stop");
  var video = document.getElementById("scan-video");
  var errorBox = document.getElementById("scan-error");
  var unsupported = document.getElementById("scan-unsupported");
  var form = document.getElementById("scan-form");
  var field = document.getElementById("scan-token");
  var stream = null;
  var timer = null;

  if (!("BarcodeDetector" in window) || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { return; }
  unsupported.hidden = true;
  startBtn.hidden = false;

  function stop() {
    if (timer) { clearInterval(timer); timer = null; }
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
    camera.hidden = true;
    startBtn.hidden = false;
  }

  startBtn.addEventListener("click", function () {
    errorBox.textContent = "";
    var detector = new window.BarcodeDetector({ formats: ["qr_code", "code_128"] });
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } }).then(function (s) {
      stream = s;
      video.srcObject = s;
      camera.hidden = false;
      startBtn.hidden = true;
      return video.play();
    }).then(function () {
      timer = setInterval(function () {
        detector.detect(video).then(function (codes) {
          if (codes.length) {
            field.value = codes[0].rawValue;
            stop();
            form.submit();
          }
        }).catch(function () { /* frame not ready: try again */ });
      }, 400);
    }).catch(function () {
      stop();
      errorBox.textContent = "The camera could not be opened. Enter the code instead.";
    });
  });
  stopBtn.addEventListener("click", stop);
  window.addEventListener("pagehide", stop);
})();
