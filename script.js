const reportsGrid = document.getElementById("reportsGrid");
const searchInput = document.getElementById("searchInput");
const clearSearchButton = document.getElementById("clearSearch");
const sourceFilters = document.getElementById("sourceFilters");
const resultsSummary = document.getElementById("resultsSummary");
const activeSourceLabel = document.getElementById("activeSource");
const emptyState = document.getElementById("emptyState");
const reportCount = document.getElementById("reportCount");
const lastUpdated = document.getElementById("lastUpdated");

let activeSource = "All";
let publications = [];

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatDate(dateString) {
    if (!dateString) {
        return "Date unavailable";
    }

    const date = new Date(`${dateString}T00:00:00`);
    if (Number.isNaN(date.getTime())) {
        return "Date unavailable";
    }

    return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric"
    }).format(date);
}

function updateLastUpdated() {
    const latestDate = publications
        .map((report) => new Date(`${report.publicationDate}T00:00:00`))
        .filter((date) => !Number.isNaN(date.getTime()))
        .sort((first, second) => second - first)[0];

    if (!latestDate) {
        lastUpdated.textContent = "Last Updated: Date unavailable";
        return;
    }

    lastUpdated.textContent = `Last Updated: ${new Intl.DateTimeFormat("en-US", {
        month: "long",
        day: "numeric",
        year: "numeric"
    }).format(latestDate)}`;
}

function getFilteredReports() {
    const query = searchInput.value.trim().toLowerCase();

    return publications.filter((report) => {
        const matchesSource = activeSource === "All" || report.source === activeSource;
        const searchableText = [
            report.source,
            report.title,
            report.category,
            report.summary,
            report.id
        ].join(" ").toLowerCase();

        return matchesSource && searchableText.includes(query);
    });
}

function createReportCard(report) {
    const article = document.createElement("article");
    article.className = "report-card";

    article.innerHTML = `
        <div class="report-meta">
            <span class="source-badge">${escapeHtml(report.source || "Unknown Source")}</span>
            <span class="category-badge">${escapeHtml(report.category || "Other")}</span>
            <span class="date-badge">${formatDate(report.publicationDate)}</span>
        </div>
        <h3>${escapeHtml(report.title || "Untitled Publication")}</h3>
        <p>${escapeHtml(report.summary || "Summary not available.")}</p>
        <a class="report-link" href="${escapeHtml(report.url || "#")}" target="_blank" rel="noopener noreferrer">
            View Original
        </a>
    `;

    return article;
}

function updateSummary(visibleCount) {
    const query = searchInput.value.trim();
    const sourceText = activeSource === "All" ? "all sources" : activeSource;
    const reportWord = visibleCount === 1 ? "item" : "items";

    if (query) {
        resultsSummary.textContent = `Showing ${visibleCount} ${reportWord} matching "${query}" from ${sourceText}.`;
    } else {
        resultsSummary.textContent = `Showing ${visibleCount} ${reportWord} from ${sourceText}.`;
    }

    activeSourceLabel.textContent = activeSource === "All" ? "All sources" : activeSource;
}

function renderReports() {
    const filteredReports = getFilteredReports();

    reportsGrid.innerHTML = "";
    filteredReports.forEach((report) => {
        reportsGrid.appendChild(createReportCard(report));
    });

    emptyState.hidden = filteredReports.length > 0;
    reportsGrid.hidden = filteredReports.length === 0;
    reportCount.textContent = publications.length;
    updateSummary(filteredReports.length);
}

function renderSourceFilters() {
    const sources = [...new Set(publications.map((report) => report.source).filter(Boolean))].sort();

    sourceFilters.innerHTML = "";
    ["All", ...sources].forEach((source) => {
        const button = document.createElement("button");
        button.className = "filter-button";
        button.type = "button";
        button.dataset.source = source;
        button.textContent = source === "All" ? "All Sources" : source;
        button.classList.toggle("active", source === activeSource);
        sourceFilters.appendChild(button);
    });
}

sourceFilters.addEventListener("click", (event) => {
    const button = event.target.closest(".filter-button");
    if (!button) {
        return;
    }

    activeSource = button.dataset.source;
    renderSourceFilters();
    renderReports();
});

searchInput.addEventListener("input", renderReports);

clearSearchButton.addEventListener("click", () => {
    searchInput.value = "";
    searchInput.focus();
    renderReports();
});

async function loadReports() {
    try {
        const response = await fetch("sources.json", { cache: "no-store" });
        if (!response.ok) {
            throw new Error(`sources.json returned ${response.status}`);
        }

        publications = await response.json();
        updateLastUpdated();
        renderSourceFilters();
        renderReports();
    } catch (error) {
        publications = [];
        reportCount.textContent = "0";
        lastUpdated.textContent = "Last Updated: Date unavailable";
        resultsSummary.textContent = "Unable to load sources.json. Start a local server and refresh the page.";
        emptyState.hidden = false;
        reportsGrid.hidden = true;
        console.error(error);
    }
}

loadReports();
