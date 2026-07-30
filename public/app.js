if ("scrollRestoration" in history) {
  history.scrollRestoration = "manual";
}

const forcePageTop = () => {
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
  window.scrollTo(0, 0);
};

const schedulePageTopReset = () => {
  forcePageTop();
  requestAnimationFrame(forcePageTop);
  window.setTimeout(forcePageTop, 0);
  window.setTimeout(forcePageTop, 80);
  window.setTimeout(forcePageTop, 250);
};

document.addEventListener("DOMContentLoaded", schedulePageTopReset, { once: true });
window.addEventListener("load", schedulePageTopReset, { once: true });
window.addEventListener("pageshow", schedulePageTopReset);

const FEED_URL = "feed.xml";
const PUBLIC_FEED_URL =
  "https://irwitzer.github.io/PhilipMaloney-feed/feed.xml";

const escapeHtml = (value) =>
  value.replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      })[character],
  );

const formatDate = (value) => {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? ""
    : new Intl.DateTimeFormat("de-CH", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(date);
};

const formatDuration = (seconds) => {
  const value = Number.parseInt(seconds, 10);

  if (!Number.isFinite(value) || value <= 0) {
    return "";
  }

  return `ca. ${Math.round(value / 60)} Min.`;
};

const renderEpisodes = (items) => {
  const container = document.querySelector("#latest-episodes");
  container.innerHTML = "";

  items.slice(0, 3).forEach((item) => {
    const title =
      item.querySelector("title")?.textContent?.trim() || "Unbenannte Episode";
    const link =
      item.querySelector("link")?.textContent?.trim() || FEED_URL;
    const publicationDate =
      item.querySelector("pubDate")?.textContent?.trim() || "";
    const description =
      item.querySelector("description")?.textContent?.trim() || "";
    const duration =
      item.getElementsByTagNameNS(
        "http://www.itunes.com/dtds/podcast-1.0.dtd",
        "duration",
      )[0]?.textContent?.trim() || "";

    const article = document.createElement("article");
    article.className = "episode-card";
    article.innerHTML = `
      <time datetime="${escapeHtml(publicationDate)}">
        ${escapeHtml(formatDate(publicationDate))}
      </time>
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(description)}</p>
      <a href="${escapeHtml(link)}">
        Fall öffnen${duration ? ` · ${escapeHtml(formatDuration(duration))}` : ""}
      </a>
    `;

    container.append(article);
  });
};

const loadFeed = async () => {
  try {
    const response = await fetch(FEED_URL, { cache: "no-store" });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const xmlText = await response.text();
    const xml = new DOMParser().parseFromString(xmlText, "application/xml");

    if (xml.querySelector("parsererror")) {
      throw new Error("Ungültiges XML");
    }

    const items = Array.from(xml.querySelectorAll("channel > item"));
    document.querySelector("#episode-count").textContent = String(items.length);
    renderEpisodes(items);
    schedulePageTopReset();
  } catch (error) {
    document.querySelector("#episode-count").textContent = "52";
    document.querySelector("#latest-episodes").innerHTML = `
      <article class="episode-card loading-card">
        <h3>Feed erreichbar</h3>
        <p>
          Die Episoden konnten in dieser Ansicht nicht automatisch geladen werden.
        </p>
        <a href="${FEED_URL}">Feed XML öffnen</a>
      </article>
    `;
    console.error("Feed konnte nicht geladen werden:", error);
  }
};

const copyFeedUrl = async () => {
  const status = document.querySelector("#copy-status");

  try {
    await navigator.clipboard.writeText(PUBLIC_FEED_URL);
  } catch {
    const textArea = document.createElement("textarea");
    textArea.value = PUBLIC_FEED_URL;
    textArea.setAttribute("readonly", "");
    textArea.style.position = "fixed";
    textArea.style.opacity = "0";
    document.body.append(textArea);
    textArea.select();
    document.execCommand("copy");
    textArea.remove();
  }

  status.textContent = "Feed-URL wurde kopiert.";

  window.setTimeout(() => {
    status.textContent = "";
  }, 3000);
};

document
  .querySelector("#copy-feed")
  ?.addEventListener("click", copyFeedUrl);

document
  .querySelector("#subscribe-button")
  ?.addEventListener("click", async (event) => {
    event.preventDefault();
    await copyFeedUrl();
    document.querySelector("#copy-status").textContent =
      "Feed-URL kopiert. Füge sie jetzt in deine Podcast-App ein.";
  });

loadFeed();
