const topbar = document.querySelector(".topbar");

function updateHeader() {
  if (!topbar) return;
  const scrolled = window.scrollY > 24;
  topbar.style.background = scrolled
    ? "rgba(13, 18, 22, 0.9)"
    : "rgba(13, 18, 22, 0.72)";
}

window.addEventListener("scroll", updateHeader, { passive: true });
updateHeader();
