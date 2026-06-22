const reportsGrid = document.getElementById("reportsGrid");
const searchInput = document.getElementById("searchInput");
const clearSearchButton = document.getElementById("clearSearch");
const filterButtons = document.querySelectorAll(".filter-button");
const resultsSummary = document.getElementById("resultsSummary");
const activeCategoryLabel = document.getElementById("activeCategory");
const emptyState = document.getElementById("emptyState");
const reportCount = document.getElementById("reportCount");

let activeCategory = "All";
let reports = [];

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

function getFilteredReports() {
    const query = searchInput.value.trim().toLowerCase();

    return reports.filter((report) => {
        const matchesCategory = activeCategory === "All" || report.category === activeCategory;
        const searchableText = [
            report.title,
            report.category,
            report.summary,
            report.id
        ].join(" ").toLowerCase();

        return matchesCategory && searchableText.includes(query);
    });
}

function createReportCard(report) {
    const article = document.createElement("article");
    article.className = "report-card";

    article.innerHTML = `
        <div class="report-meta">
            <span class="category-badge">${escapeHtml(report.category || "Other")}</span>
            <span class="date-badge">${formatDate(report.publicationDate)}</span>
        </div>
        <h3>${escapeHtml(report.title || "Untitled CRS Report")}</h3>
        <p>${escapeHtml(report.summary || "Summary not available.")}</p>
        <a class="report-link" href="${escapeHtml(report.url || "#")}" target="_blank" rel="noopener noreferrer">
            View CRS Report
        </a>
    `;

    return article;
}

function updateSummary(visibleCount) {
    const query = searchInput.value.trim();
    const categoryText = activeCategory === "All" ? "all categories" : activeCategory;
    const reportWord = visibleCount === 1 ? "report" : "reports";

    if (query) {
        resultsSummary.textContent = `Showing ${visibleCount} ${reportWord} matching "${query}" in ${categoryText}.`;
    } else {
        resultsSummary.textContent = `Showing ${visibleCount} ${reportWord} in ${categoryText}.`;
    }

    activeCategoryLabel.textContent = activeCategory === "All" ? "All categories" : activeCategory;
}

function renderReports() {
    const filteredReports = getFilteredReports();

    reportsGrid.innerHTML = "";
    filteredReports.forEach((report) => {
        reportsGrid.appendChild(createReportCard(report));
    });

    emptyState.hidden = filteredReports.length > 0;
    reportsGrid.hidden = filteredReports.length === 0;
    reportCount.textContent = reports.length;
    updateSummary(filteredReports.length);
}

filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
        activeCategory = button.dataset.category;

        filterButtons.forEach((filterButton) => {
            filterButton.classList.toggle("active", filterButton === button);
        });

        renderReports();
    });
});

searchInput.addEventListener("input", renderReports);

clearSearchButton.addEventListener("click", () => {
    searchInput.value = "";
    searchInput.focus();
    renderReports();
});

async function loadReports() {
    try {
        const response = await fetch("reports.json", { cache: "no-store" });
        if (!response.ok) {
            throw new Error(`reports.json returned ${response.status}`);
        }

        reports = await response.json();
        renderReports();
    } catch (error) {
        reports = [];
        reportCount.textContent = "0";
        resultsSummary.textContent = "Unable to load reports.json. Start a local server and refresh the page.";
        emptyState.hidden = false;
        reportsGrid.hidden = true;
        console.error(error);
    }
}

loadReports();
