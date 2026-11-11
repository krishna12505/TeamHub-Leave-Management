
document.addEventListener("DOMContentLoaded", function () {

    // =========================================
    // 1. ELEMENT REFERENCES
    // =========================================

    const tableSearch = document.getElementById("tableSearch");
    const globalSearch = document.getElementById("globalSearch");
    const statusFilter = document.getElementById("statusFilter");
    const noResults = document.getElementById("noResults");

    const leaveRows = Array.from(
        document.querySelectorAll("#leaveTable tbody .leave-row")
    );

    const employeeLeaveCards = Array.from(
        document.querySelectorAll(".employee-leave")
    );

    // =========================================
    // 2. SEARCH AND FILTER TABLE
    // =========================================

    function filterLeaveTable() {

        const searchValue = (
            tableSearch?.value || ""
        ).trim().toLowerCase();

        const selectedStatus = (
            statusFilter?.value || "all"
        ).toLowerCase();

        let visibleRows = 0;

        leaveRows.forEach(row => {

            const rowText = (
                row.textContent || ""
            ).replace(/\s+/g, " ").trim().toLowerCase();

            const rowStatus = (
                row.dataset.status || ""
            ).toLowerCase().trim();

            const matchesSearch =
                rowText.includes(searchValue);

            const matchesStatus =
                selectedStatus === "all" ||
                rowStatus === selectedStatus;

            const shouldDisplay =
                matchesSearch && matchesStatus;

            row.style.display =
                shouldDisplay ? "" : "none";

            if (shouldDisplay) {
                visibleRows++;
            }

        });

        if (noResults) {

            noResults.style.display =
                leaveRows.length > 0 && visibleRows === 0
                    ? "block"
                    : "none";

        }

    }

    // Table search
    if (tableSearch) {

        tableSearch.addEventListener("input", function () {

            // Keep the top search synchronized.
            if (globalSearch) {
                globalSearch.value = this.value;
            }

            filterLeaveTable();

        });

    }

    // Status filter
    if (statusFilter) {
        statusFilter.addEventListener(
            "change",
            filterLeaveTable
        );
    }

    // Global search
    if (globalSearch) {

        globalSearch.addEventListener("input", function () {

            const searchValue = this.value;

            if (tableSearch) {
                tableSearch.value = searchValue;
            }

            // Search table records.
            filterLeaveTable();

        });

    }

    // =========================================
    // 3. LEAVE DURATION CALCULATION
    // =========================================

    document.querySelectorAll(".duration-cell").forEach(cell => {

        const startDate = cell.dataset.start;
        const endDate = cell.dataset.end;

        function parseDate(value) {

            if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) {
                return null;
            }

            const [year, month, day] =
                value.split("-").map(Number);

            const date = new Date(
                Date.UTC(year, month - 1, day)
            );

            if (
                date.getUTCFullYear() !== year ||
                date.getUTCMonth() !== month - 1 ||
                date.getUTCDate() !== day
            ) {
                return null;
            }

            return date.getTime();

        }

        const start = parseDate(startDate);
        const end = parseDate(endDate);

        if (
            start === null ||
            end === null ||
            end < start
        ) {
            cell.textContent = "-";
            return;
        }

        const days =
            Math.round((end - start) / 86400000) + 1;

        cell.textContent =
            days + (days === 1 ? " Day" : " Days");

    });

    // =========================================
    // 4. READ CALENDAR DATA
    // =========================================

    let leavePeriods = [];

    const leaveDataElement =
        document.getElementById("leaveData");

    if (leaveDataElement) {

        try {

            const parsedData = JSON.parse(
                leaveDataElement.textContent
            );

            if (Array.isArray(parsedData)) {
                leavePeriods = parsedData;
            }

        } catch (error) {

            console.error(
                "Calendar data error:",
                error
            );

        }

    }

    // =========================================
    // 5. CALENDAR ELEMENTS
    // =========================================

    const calendarGrid =
        document.getElementById("calendarGrid");

    const calendarMonth =
        document.getElementById("calendarMonth");

    const previousButton =
        document.getElementById("prevMonth");

    const nextButton =
        document.getElementById("nextMonth");

    if (calendarGrid && calendarMonth) {

        let currentMonth = new Date();
        const today = new Date();

        const todayString =
            today.getFullYear() + "-" +
            String(today.getMonth() + 1).padStart(2, "0") + "-" +
            String(today.getDate()).padStart(2, "0");

        // =====================================
        // 6. CHECK APPROVED LEAVE DATES
        // =====================================

        function isLeaveDate(dateString) {

            return leavePeriods.some(period => {

                if (!period.start || !period.end) {
                    return false;
                }

                return (
                    dateString >= period.start &&
                    dateString <= period.end
                );

            });

        }

        // =====================================
        // 7. RENDER CALENDAR
        // =====================================

        function renderCalendar() {

            calendarGrid.innerHTML = "";

            const year = currentMonth.getFullYear();
            const month = currentMonth.getMonth();

            calendarMonth.textContent =
                currentMonth.toLocaleDateString("en-US", {
                    month: "long",
                    year: "numeric"
                });

            const weekdays = [
                "Sun", "Mon", "Tue",
                "Wed", "Thu", "Fri", "Sat"
            ];

            weekdays.forEach(day => {

                const element =
                    document.createElement("div");

                element.className = "calendar-day-name";
                element.textContent = day;

                calendarGrid.appendChild(element);

            });

            const firstDay =
                new Date(year, month, 1).getDay();

            const daysInMonth =
                new Date(year, month + 1, 0).getDate();

            for (let i = 0; i < firstDay; i++) {

                const empty =
                    document.createElement("div");

                empty.className = "calendar-day empty";

                calendarGrid.appendChild(empty);

            }

            for (let day = 1; day <= daysInMonth; day++) {

                const element =
                    document.createElement("div");

                element.className = "calendar-day";
                element.textContent = day;

                const dateString =
                    year + "-" +
                    String(month + 1).padStart(2, "0") + "-" +
                    String(day).padStart(2, "0");

                if (dateString === todayString) {

                    element.classList.add("today");
                    element.title = "Today";

                }

                if (isLeaveDate(dateString)) {

                    element.classList.add("leave-day");
                    element.title = "Approved employee leave";

                }

                calendarGrid.appendChild(element);

            }

        }

        // Previous month
        if (previousButton) {

            previousButton.addEventListener("click", function () {

                currentMonth = new Date(
                    currentMonth.getFullYear(),
                    currentMonth.getMonth() - 1,
                    1
                );

                renderCalendar();

            });

        }

        // Next month
        if (nextButton) {

            nextButton.addEventListener("click", function () {

                currentMonth = new Date(
                    currentMonth.getFullYear(),
                    currentMonth.getMonth() + 1,
                    1
                );

                renderCalendar();

            });

        }

        renderCalendar();

    }

    // =========================================
    // 8. SIDEBAR NAVIGATION
    // =========================================

    const sidebarLinks =
        document.querySelectorAll(".nav-menu .nav-link");

    sidebarLinks.forEach(link => {

        const href = link.getAttribute("href");

        if (href && href.startsWith("#")) {

            link.addEventListener("click", function (event) {

                const target =
                    document.querySelector(href);

                if (target) {

                    event.preventDefault();

                    target.scrollIntoView({
                        behavior: "smooth",
                        block: "start"
                    });

                    sidebarLinks.forEach(item => {
                        item.classList.remove("active");
                    });

                    this.classList.add("active");

                }

            });

        }

    });

    // =========================================
    // 9. INITIALIZE
    // =========================================

    filterLeaveTable();

    console.log(
        "TeamHub Manager Dashboard initialized successfully."
    );

});
