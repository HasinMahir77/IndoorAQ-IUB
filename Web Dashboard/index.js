document.addEventListener("DOMContentLoaded", () => {
  const tableBody = document.getElementById("table-body");
  const loadingIndicator = document.getElementById("loading");
  const chartSection = document.querySelector(".chart-section");
  const chartTitle = document.getElementById("chart-title");
  const chartPlaceholder = document.getElementById("chart-placeholder");
  const chartContainer = document.getElementById("chart-container");
  let selectedDeviceId = null; // Track the selected device ID
  let selectedRow = null;      // Track the currently selected row

  // Chart instances
  let tempChart = null;
  let humiChart = null;
  let pressureChart = null;
  let pm1Chart = null;
  let pm25Chart = null;
  let pm10Chart = null;
  let co2Chart = null;

  // Redacted server endpoints
  const API_GET_LATEST_ALL = "";
  const API_GET_LAST_50_PREFIX = "";

  const fetchData = async () => {
    try {
      const response = await fetch(API_GET_LATEST_ALL);
      if (!response.ok) {
        throw new Error(`Failed to fetch data (status ${response.status})`);
      }
      const result = await response.json();
      if (result.status === "success") {
        populateTable(result.data);
      } else {
        console.error("Error in response:", result.message);
      }
    } catch (error) {
      console.error("Error fetching data:", error);
    } finally {
      loadingIndicator.style.display = "none";
    }
  };

  const fetchChartData = async () => {
    if (!selectedDeviceId) return; // No device selected

    try {
      const response = await fetch(`${API_GET_LAST_50_PREFIX}${selectedDeviceId}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch chart data (status ${response.status})`);
      }
      const result = await response.json();

      if (result.time && result.temperature && result.humidity) {
        updateCharts(
          result.time,
          result.temperature,
          result.humidity,
          result.pressure || [],
          result.pm1 || [],
          result.pm2_5 || [],
          result.pm10 || [],
          result.co2 || []
        );
      } else {
        console.error("Chart data missing required fields:", result);
      }
    } catch (error) {
      console.error("Error fetching chart data:", error);
    }
  };

  const getDevicePosition = (deviceId) => {
    const positions = {
      '1': 'North',
      '2': 'East North',
      '3': 'East South',
      '4': 'East',
      '5': 'South',
      '6': 'West South',
      '7': 'West',
      '8': 'South West',
      '9': 'West North',
      '10': 'North West'
    };
    return positions[deviceId] || 'Unknown';
  };

  const populateTable = (data) => {
    tableBody.innerHTML = ""; // Clear existing rows
    data.forEach((item) => {
      const row = document.createElement("tr");
      const timestamp = new Date(item.timestamp);
      const now = new Date();
      const minutesDiff = (now - timestamp) / (1000 * 60); // Convert to minutes
      
      row.innerHTML = `
        <td>${item.deviceid}</td>
        <td>${getDevicePosition(item.deviceid)}</td>
        <td>${item.air_temperature}</td>
        <td>${item.humidity}</td>
        <td>${item.pressure}</td>
        <td>${item.pm1}</td>
        <td>${item.pm2_5}</td>
        <td>${item.pm10}</td>
        <td>${item.co2}</td>
        <td>${timestamp.toLocaleString()}</td>
      `;
      
      // Add light red background if data is more than 10 minutes old
      if (minutesDiff > 10) {
        row.style.backgroundColor = '#ffebee'; // Light red color
      }
      
      row.addEventListener("click", () => handleRowClick(row, item.deviceid));
      tableBody.appendChild(row);
    });
  };

  const handleRowClick = (row, deviceId) => {
    // Un-highlight previous row
    if (selectedRow) {
      selectedRow.classList.remove("table-primary");
    }
    // Highlight new row
    row.classList.add("table-primary");
    selectedRow = row;

    selectedDeviceId = deviceId;
    chartTitle.textContent = `Device ${deviceId} Charts`;
    chartPlaceholder.style.display = "none";
    chartContainer.style.display = "flex";

    fetchChartData();
  };

  const updateCharts = (labels, temperatures, humidities, pressures, pm1s, pm25s, pm10s, co2s) => {
    tempChart     = createOrUpdateChart(tempChart,    "tempChart",     "Temperature (°C)", labels, temperatures);
    humiChart     = createOrUpdateChart(humiChart,    "humiChart",     "Humidity (%)",    labels, humidities);
    pressureChart = createOrUpdateChart(pressureChart,"pressureChart", "Pressure (Pa)",   labels, pressures);
    pm1Chart      = createOrUpdateChart(pm1Chart,     "pm1Chart",      "PM1 (µg/m³)",      labels, pm1s);
    pm25Chart     = createOrUpdateChart(pm25Chart,    "pm25Chart",     "PM2.5 (µg/m³)",    labels, pm25s);
    pm10Chart     = createOrUpdateChart(pm10Chart,    "pm10Chart",     "PM10 (µg/m³)",     labels, pm10s);
    co2Chart      = createOrUpdateChart(co2Chart,     "co2Chart",      "CO₂ (ppm)",        labels, co2s);
  };

  const createOrUpdateChart = (chart, canvasId, label, labels, data) => {
    const ctx = document.getElementById(canvasId).getContext("2d");
    if (chart) {
      chart.data.labels = labels;
      chart.data.datasets[0].data = data;
      chart.update();
    } else {
      chart = new Chart(ctx, {
        type: "line",
        data: {
          labels: labels,
          datasets: [{
            label: label,
            data: data,
            // styling can be customized in CSS or Chart.js options
            borderWidth: 1,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            legend: { display: true },
          },
        },
      });
    }
    return chart;
  };

  // Initial load
  fetchData();
  setInterval(fetchData, 4000);
  setInterval(fetchChartData, 4000);
});