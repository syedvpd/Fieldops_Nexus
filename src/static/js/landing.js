(function () {
  var b = document.getElementById("burger"), l = document.getElementById("links");
  if (b && l) {
    b.addEventListener("click", function () {
      var open = l.classList.toggle("open");
      b.setAttribute("aria-expanded", open ? "true" : "false");
    });
    l.addEventListener("click", function (e) { if (e.target.tagName === "A") { l.classList.remove("open"); b.setAttribute("aria-expanded", "false"); } });
  }
  var nav = document.querySelector(".nav");
  window.addEventListener("scroll", function () { nav.classList.toggle("solid", window.scrollY > 24); }, { passive: true });
  // Progressive reveal: only content below the fold is hidden, revealed by scroll position, and ALWAYS shown within 6s.
  var items = document.querySelectorAll(".card,.tile,.shot,.steps li,.eco div,.ind div");
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  var pending = [];
  items.forEach(function (n) { if (n.getBoundingClientRect().top > window.innerHeight) { n.classList.add("rv"); pending.push(n); } });
  var check = function () {
    pending = pending.filter(function (n) {
      if (n.getBoundingClientRect().top < window.innerHeight * 0.96) { n.classList.add("in"); return false; }
      return true;
    });
  };
  window.addEventListener("scroll", check, { passive: true });
  window.addEventListener("resize", check);
  setTimeout(function () { pending.forEach(function (n) { n.classList.add("in"); }); pending = []; }, 6000);
})();
