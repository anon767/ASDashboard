document.addEventListener('DOMContentLoaded', function() {
    const submitButton = document.getElementById('submitButton');
    const ctx = document.getElementById('asChart').getContext('2d');
    let myChart;

    async function fetchDashboardData() {
        const response = await fetch('/dashboard');
        const data = await response.json();
        document.getElementById('totalAS').textContent = data.total_as;
        document.getElementById('totalBlockedIPs').textContent = data.total_blocked_ips;
        document.getElementById('mostBlacklistedAS').textContent = data.most_blacklisted.as_number;
        document.getElementById('mostBlacklistedASName').textContent = data.most_blacklisted.as_name;
        document.getElementById('mostBlacklistedCount').textContent = data.most_blacklisted.count;
    }
    fetchDashboardData();

    function getAsnFromUrl() {
        const hash = window.location.hash;
        if (hash.startsWith('#asn')) {
            return hash.substring(4);
        }
        return null;
    }

    async function fetchData(asNumber) {
        const response = await fetch(`/data?asNumber=${encodeURIComponent(asNumber)}`);
        const data = await response.json();
        return data;
    }

    if (userAsn) {
        fetchData(userAsn).then(data => {
            if (data && data.datasets.length > 0) {
                    if (myChart) {
                        myChart.destroy(); // Destroy the previous chart instance if exists
                    }
                    myChart = new Chart(ctx, {
                        type: 'line',
                        data: data,
                        options: {
                            scales: {
                                y: {
                                    beginAtZero: true
                                }
                            }
                        }
                    });
                    } else {
                        console.log('No data available for the auto-detected ASN.');
                    }
        }).catch(error => console.error('Error fetching the data for the auto-detected ASN:', error));
    }
    
    function updateChart(data) {
        if (myChart) {
            myChart.destroy();
        }
        myChart = new Chart(ctx, {
            type: 'line',
            data: data,
            options: {
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }

    function updateUrl(asNumber) {
        window.location.hash = `#asn${asNumber}`;
    }

    const asnFromUrl = getAsnFromUrl();
    if (asnFromUrl) {
        document.getElementById('asNumberInput').value = asnFromUrl;
        fetchData(asnFromUrl).then(data => {
            if (data && data.datasets.length > 0) {
                updateChart(data);
            } else {
                console.log('No data available for the specified ASN.');
            }
        }).catch(error => console.error('Error fetching the data for the specified ASN:', error));
    }

    submitButton.addEventListener('click', function() {
        const asNumber = document.getElementById('asNumberInput').value;
        if (!asNumber) {
            alert("Please enter a valid AS number.");
            return;
        }
        fetchData(asNumber).then(data => {
            updateChart(data);
            updateUrl(asNumber);
        }).catch(error => console.error('Error fetching the data:', error));
    });
});
