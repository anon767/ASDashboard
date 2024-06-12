document.addEventListener('DOMContentLoaded', function() {
    const submitButton = document.getElementById('submitButton');
    const ctx = document.getElementById('asChart').getContext('2d');
    

    let myChart;
    async function fetchDashboardData() {
        const response = await fetch('/dashboard');
        const data = await response.json();
	console.log(data);
        document.getElementById('totalAS').textContent = data.total_as;
        document.getElementById('totalBlockedIPs').textContent = data.total_blocked_ips;
        document.getElementById('mostBlacklistedAS').textContent = data.most_blacklisted.as_number;
        document.getElementById('mostBlacklistedASName').textContent = data.most_blacklisted.as_name;
        document.getElementById('mostBlacklistedCount').textContent = data.most_blacklisted.count;
        
	
    }
    fetchDashboardData();

    console.log(userAsn) 
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
    

    submitButton.addEventListener('click', function() {
        const asNumber = document.getElementById('asNumberInput').value;
        if (!asNumber) {
            alert("Please enter a valid AS number.");
            return;
        }
        fetchData(asNumber).then(data => {
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
        }).catch(error => console.error('Error fetching the data:', error));
    });

    async function fetchData(asNumber) {
        const response = await fetch(`/data?asNumber=${encodeURIComponent(asNumber)}`);
        const data = await response.json();
        return data;
    }
});
