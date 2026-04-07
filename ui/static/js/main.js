// Global utilities and routing

window.showToast = function(message, type="info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    // Auto remove after 3s
    setTimeout(() => {
        toast.style.animation = "slideInRight 0.3s reverse forwards";
        setTimeout(() => toast.remove(), 300);
    }, 3000);
};

// Clock
function updateClock() {
    const now = new Date();
    document.getElementById("header-date").textContent = now.toISOString().split("T")[0];
    document.getElementById("header-time").textContent = now.toTimeString().split(" ")[0];
}
setInterval(updateClock, 1000);
updateClock();

// Routing logic
document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", () => {
        // Remove active class from all navs
        document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
        // Hide all pages
        document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
        
        // Activate selected
        item.classList.add("active");
        const targetId = item.getAttribute("data-target");
        document.getElementById(targetId).classList.add("active");
        
        const titleText = item.querySelector('.nav-text').textContent;
        document.getElementById("page-title").textContent = `${titleText.toUpperCase()} OVERVIEW`;
    });
});

// Sidebar Toggle
document.getElementById("toggle-sidebar").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("collapsed");
});

// Global API Fetch helper
window.apiFetch = async function(url, options={}) {
    try {
        const response = await fetch(url, options);
        if(!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch(err) {
        console.error("API Error:", err);
        return null;
    }
}
