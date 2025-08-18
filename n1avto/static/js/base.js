document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("searchForm");
    const input = document.getElementById("searchInput");
    const table = document.getElementById("resultsTable");
    const tbody = table.querySelector("tbody");
    const noResults = document.getElementById("noResults");
    const loadMoreContainer = document.getElementById("loadMoreContainer");
    const loadMoreBtn = document.getElementById("loadMoreBtn");
    const searchBtn = form.querySelector("button[type='submit']");
    const spinner = searchBtn.querySelector(".spinner");
    const buttonText = searchBtn.querySelector("span");

    let allResults = [];
    let currentPage = 0;
    const itemsPerPage = 10;

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        const query = input.value.trim();

        if (!query) {
            table.style.display = "none";
            noResults.style.display = "none";
            loadMoreContainer.style.display = "none";
            return;
        }

        // Show loading spinner
        searchBtn.classList.add("loading");
        spinner.style.display = "inline-block";
        buttonText.style.display = "none";
        searchBtn.disabled = true;

        fetch(`?q=${encodeURIComponent(query)}`, {
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
        .then(res => res.json())
        .then(data => {
            allResults = data.results;
            currentPage = 0;
            
            if (allResults.length > 0) {
                displayResults();
                table.style.display = "table";
                noResults.style.display = "none";
                
                // Show load more button if there are more than 10 results
                if (allResults.length > itemsPerPage) {
                    loadMoreContainer.style.display = "block";
                } else {
                    loadMoreContainer.style.display = "none";
                }
            } else {
                table.style.display = "none";
                noResults.style.display = "block";
                loadMoreContainer.style.display = "none";
            }
        })
        .finally(() => {
            // Hide loading spinner
            searchBtn.classList.remove("loading");
            spinner.style.display = "none";
            buttonText.style.display = "inline";
            searchBtn.disabled = false;
        });
    });

    function displayResults() {
        const startIndex = currentPage * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const currentResults = allResults.slice(startIndex, endIndex);
        
        // Clear table only on first page, append on subsequent pages
        if (currentPage === 0) {
            tbody.innerHTML = "";
        }
        
        currentResults.forEach(m => {
            const row = `<tr>
                <td><img src="${m.sekil}" alt="${m.adi}" style="width:60px;height:auto;"></td>
                <td>${m.adi}</td>
                <td>${m.firma}</td>
                <td>${m.kod}</td>
                <td>${m.qiymet}</td>
                <td>${m.stok}</td>
            </tr>`;
            tbody.insertAdjacentHTML("beforeend", row);
        });

        // Update load more button state
        if (endIndex >= allResults.length) {
            loadMoreBtn.disabled = true;
            loadMoreBtn.textContent = "Bütün nəticələr göstərildi";
        } else {
            loadMoreBtn.disabled = false;
            loadMoreBtn.textContent = `Daha Çox Göstər (${allResults.length - endIndex} qalıb)`;
        }
    }

    loadMoreBtn.addEventListener("click", function() {
        // Store current scroll position
        const currentScrollPos = window.pageYOffset;
        
        currentPage++;
        displayResults();
        
        // Restore scroll position (no automatic scrolling)
        window.scrollTo(0, currentScrollPos);
    });
});
