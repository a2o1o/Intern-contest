const topbar = document.querySelector(".topbar");

function updateHeader() {
  if (!topbar) return;
  const scrolled = window.scrollY > 24;
  topbar.style.background = scrolled
    ? "rgba(247, 245, 240, 0.98)"
    : "rgba(247, 245, 240, 0.92)";
}

window.addEventListener("scroll", updateHeader, { passive: true });
updateHeader();
