class Dashboard {
    constructor() {
        this.charts = {};
        this.data = null;
        this.filterValues = {
            resourceType: '',
            statusCode: '',
            searchQuery: ''
        };
        this.networkGraph = null;
    }
    
    initialize() {
        
        document.querySelectorAll('.tab-btn').forEach(button => {
            button.addEventListener('click', () => this.switchTab(button.dataset.tab));
        });
        
        
        document.getElementById('requestFilter').addEventListener('input', (e) => {
            this.filterValues.searchQuery = e.target.value;
            this.applyFilters();
        });
        
        
        this.initNetworkGraph();
        
        
        this.initWaterfallChart();
        
        // After all initialization is done, display the timeline
        this.displayThreatTimeline();
    }
    
    initNetworkGraph() {
        
        if (!this.data) return;
        
        const container = document.getElementById('network-graph');
        if (!container) return;
        
        
        
    }
    
    initWaterfallChart() {
        
        if (!this.data) return;
        
        const container = document.getElementById('waterfall-chart');
        if (!container) return;
        
        
        const sortedRequests = this.data.all_requests
            .filter(req => req.duration)
            .sort((a, b) => {
                const aTime = new Date(a.timestamp).getTime();
                const bTime = new Date(b.timestamp).getTime();
                return aTime - bTime;
            });
            
        
    }

    
    async loadRequests(analysisId, page = 1) {
        try {
            const response = await fetch(`/api/requests?id=${analysisId}&page=${page}&per_page=50`);
            const data = await response.json();
            
            if (data.error) {
                console.error('Error loading requests:', data.error);
                return;
            }
            
            
            this.currentPage = data.page;
            this.totalPages = data.total_pages;
            
            
            this.displayRequests(data.requests);
            this.updatePagination();
        } catch (error) {
            console.error('Failed to load requests:', error);
        }
    }

    createOrUpdateChart(canvasId, type, data, options) {
        // Destroy existing chart if it exists
        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
        }
        
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;
        
        // Create new chart
        this.charts[canvasId] = new Chart(canvas.getContext('2d'), {
            type: type,
            data: data,
            options: options
        });
        
        return this.charts[canvasId];
    }

    setupPagination(elementId, data, itemsPerPage, renderFunction) {
        const container = document.getElementById(elementId);
        if (!container) return;
        
        const paginationContainer = document.createElement('div');
        paginationContainer.className = 'pagination';
        container.appendChild(paginationContainer);
        
        const totalPages = Math.ceil(data.length / itemsPerPage);
        let currentPage = 1;
        
        const renderPage = (page) => {
            const start = (page - 1) * itemsPerPage;
            const end = start + itemsPerPage;
            const pageItems = data.slice(start, end);
            
            // Clear previous content
            container.innerHTML = '';
            
            // Render the items
            renderFunction(container, pageItems);
            
            // Add pagination controls
            const pagination = document.createElement('div');
            pagination.className = 'pagination';
            
            // Previous button
            if (page > 1) {
                const prev = document.createElement('button');
                prev.innerText = 'Previous';
                prev.onclick = () => renderPage(page - 1);
                pagination.appendChild(prev);
            }
            
            // Page indicator
            const pageInfo = document.createElement('span');
            pageInfo.innerText = `Page ${page} of ${totalPages}`;
            pagination.appendChild(pageInfo);
            
            // Next button
            if (page < totalPages) {
                const next = document.createElement('button');
                next.innerText = 'Next';
                next.onclick = () => renderPage(page + 1);
                pagination.appendChild(next);
            }
            
            container.appendChild(pagination);
        };
        
        // Initial render
        renderPage(currentPage);
    }
    
    displayRequestsWithPagination(requests) {
        const renderRequests = (container, items) => {
            const table = document.createElement('table');
            table.className = 'data-table';
            
            // Create header
            const thead = document.createElement('thead');
            const headerRow = document.createElement('tr');
            ['URL', 'Method', 'Status', 'Type', 'Duration'].forEach(header => {
                const th = document.createElement('th');
                th.textContent = header;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);
            table.appendChild(thead);
            
            // Create body
            const tbody = document.createElement('tbody');
            items.forEach(req => {
                const row = document.createElement('tr');
                
                const urlCell = document.createElement('td');
                urlCell.textContent = this.truncateText(req.url, 50);
                urlCell.title = req.url;
                row.appendChild(urlCell);
                
                const methodCell = document.createElement('td');
                methodCell.textContent = req.method;
                row.appendChild(methodCell);
                
                const statusCell = document.createElement('td');
                statusCell.textContent = req.status_code || 'N/A';
                if (req.status_code >= 400) {
                    statusCell.className = 'error';
                }
                row.appendChild(statusCell);
                
                const typeCell = document.createElement('td');
                typeCell.textContent = req.resource_type || req.resourceType || 'unknown';
                row.appendChild(typeCell);
                
                const durationCell = document.createElement('td');
                durationCell.textContent = req.duration ? `${req.duration}ms` : 'N/A';
                row.appendChild(durationCell);
                
                tbody.appendChild(row);
            });
            table.appendChild(tbody);
            container.appendChild(table);
        };
        
        this.setupPagination('requestsContainer', requests, 20, renderRequests);
    }
    
    truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    paginateTable(tableId, data, pageSize = 20) {
        const table = document.getElementById(tableId);
        if (!table) return;
        
        const tbody = table.querySelector('tbody');
        if (!tbody) return;
        
        // Save all rows
        if (!this.tableData) this.tableData = {};
        this.tableData[tableId] = data;
        
        // Create pagination controls if they don't exist
        let paginationDiv = document.getElementById(`${tableId}-pagination`);
        if (!paginationDiv) {
            paginationDiv = document.createElement('div');
            paginationDiv.id = `${tableId}-pagination`;
            paginationDiv.className = 'pagination-controls';
            table.parentNode.insertBefore(paginationDiv, table.nextSibling);
        }
        
        // Display first page and setup pagination
        this.displayTablePage(tableId, 1, pageSize);
    }
    
    displayTablePage(tableId, page, pageSize) {
        const table = document.getElementById(tableId);
        const data = this.tableData[tableId];
        if (!table || !data) return;
        
        const tbody = table.querySelector('tbody');
        if (!tbody) return;
        
        // Calculate page data
        const totalPages = Math.ceil(data.length / pageSize);
        const start = (page - 1) * pageSize;
        const end = Math.min(start + pageSize, data.length);
        const pageData = data.slice(start, end);
        
        // Clear existing rows
        tbody.innerHTML = '';
        
        // Add rows for current page
        pageData.forEach(item => {
            const row = this.createRow(item);
            tbody.appendChild(row);
        });
        
        // Update pagination controls
        const paginationDiv = document.getElementById(`${tableId}-pagination`);
        if (paginationDiv) {
            paginationDiv.innerHTML = '';
            
            // Only show pagination if needed
            if (totalPages > 1) {
                // Previous button
                if (page > 1) {
                    const prevBtn = document.createElement('button');
                    prevBtn.innerText = 'Previous';
                    prevBtn.onclick = () => this.displayTablePage(tableId, page - 1, pageSize);
                    paginationDiv.appendChild(prevBtn);
                }
                
                // Page indicator
                const pageText = document.createElement('span');
                pageText.innerText = ` Page ${page} of ${totalPages} `;
                paginationDiv.appendChild(pageText);
                
                // Next button
                if (page < totalPages) {
                    const nextBtn = document.createElement('button');
                    nextBtn.innerText = 'Next';
                    nextBtn.onclick = () => this.displayTablePage(tableId, page + 1, pageSize);
                    paginationDiv.appendChild(nextBtn);
                }
            }
        }
    }
    
    createRow(item) {
        // Override this in specific implementations
        const row = document.createElement('tr');
        Object.values(item).forEach(value => {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.appendChild(cell);
        });
        return row;
    }

    displayThreatIndicator(result) {
        const threatLevel = result.safety_assessment.threat_level || 0;
        const threatColor = result.safety_assessment.threat_color || 'green';
        
        // Create the threat indicator element if it doesn't exist
        if (!this.threatIndicator) {
            this.threatIndicator = document.createElement('div');
            this.threatIndicator.className = 'threat-indicator';
            this.threatIndicator.innerHTML = `
                <h3>Threat Level</h3>
                <div class="threat-bar-container">
                    <div class="threat-bar"></div>
                </div>
                <div class="threat-value"></div>
                <div class="threat-label"></div>
            `;
            
            // Insert at the top of the results section
            const resultsContainer = document.querySelector('#analysis-results');
            resultsContainer.insertBefore(this.threatIndicator, resultsContainer.firstChild);
        }
        
        // Update the threat indicator
        const bar = this.threatIndicator.querySelector('.threat-bar');
        const value = this.threatIndicator.querySelector('.threat-value');
        const label = this.threatIndicator.querySelector('.threat-label');
        
        bar.style.width = `${threatLevel}%`;
        bar.style.backgroundColor = threatColor;
        value.textContent = `${threatLevel}%`;
        
        // Set label based on threat level
        if (threatLevel < 30) {
            label.textContent = 'Low Risk';
            label.style.color = 'green';
        } else if (threatLevel < 70) {
            label.textContent = 'Moderate Risk';
            label.style.color = 'orange';
        } else {
            label.textContent = 'High Risk';
            label.style.color = 'red';
        }
        
        // Make indicator visible
        this.threatIndicator.style.display = 'block';
    }

    displayResults(result) {
        // ...existing code
        
        this.displayThreatIndicator(result);
        
        // Display WHOIS info if we have a URL
        if (result.url) {
            this.displayWhoisInfo(result.url);
        }
        
        // Display recommendations
        this.displayRecommendations(result);
        
        // Add export buttons
        this.addExportButtons(result.id);
        
        // Add filters and search functionality
        this.addFiltersAndSearch();
        
        // ...rest of your displayResults code
        
        // Display anomalies with confidence level attribute
        if (result.anomalies && result.anomalies.length > 0) {
            // ...existing anomalies display code
            
            // Add confidence level to each anomaly row
            result.anomalies.forEach(anomaly => {
                // Determine confidence level based on anomaly type
                let confidence = 'medium';
                
                // Higher confidence for server errors, security issues
                if (['server_error', 'security_headers', 'mixed_content', 'outdated_tls'].includes(anomaly.anomaly_type)) {
                    confidence = 'high';
                }
                // Lower confidence for statistical anomalies
                else if (['statistical_outlier', 'slow_request'].includes(anomaly.anomaly_type)) {
                    confidence = 'low';
                }
                
                // Add attributes to the row
                const row = /* your row element */;
                row.setAttribute('data-type', anomaly.anomaly_type);
                row.setAttribute('data-confidence', confidence);
                
                // Add visible confidence badge
                const confidenceCell = document.createElement('td');
                confidenceCell.className = `confidence-badge ${confidence}`;
                confidenceCell.textContent = confidence.charAt(0).toUpperCase() + confidence.slice(1);
                row.appendChild(confidenceCell);
            });
        }
    }

    async displayThreatTimeline() {
        try {
            // Create timeline container if it doesn't exist
            if (!this.timelineContainer) {
                this.timelineContainer = document.createElement('div');
                this.timelineContainer.id = 'threat-timeline-container';
                this.timelineContainer.innerHTML = `
                    <h3>Threat Timeline</h3>
                    <div class="chart-container">
                        <canvas id="threat-timeline-chart"></canvas>
                    </div>
                `;
                
                // Add to the dashboard in an appropriate location
                document.querySelector('#dashboard-container').appendChild(this.timelineContainer);
            }
            
            // Fetch timeline data
            const response = await fetch('/api/threat-timeline');
            if (!response.ok) throw new Error('Failed to fetch timeline data');
            
            const timelineData = await response.json();
            if (timelineData.length === 0) {
                this.timelineContainer.innerHTML += '<p>No history data available to display timeline.</p>';
                return;
            }
            
            // Format data for Chart.js
            const labels = timelineData.map(item => {
                const date = new Date(item.date);
                return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
            });
            
            const threatLevels = timelineData.map(item => item.threat_level);
            const anomalyCounts = timelineData.map(item => item.anomalies_found);
            const urls = timelineData.map(item => item.url);
            const ids = timelineData.map(item => item.id);
            
            // Create or update chart
            if (this.timelineChart) {
                this.timelineChart.destroy();
            }
            
            const ctx = document.getElementById('threat-timeline-chart').getContext('2d');
            this.timelineChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Threat Level',
                            data: threatLevels,
                            borderColor: 'rgb(255, 99, 132)',
                            backgroundColor: 'rgba(255, 99, 132, 0.2)',
                            yAxisID: 'y',
                            tension: 0.2
                        },
                        {
                            label: 'Anomalies Found',
                            data: anomalyCounts,
                            borderColor: 'rgb(54, 162, 235)',
                            backgroundColor: 'rgba(54, 162, 235, 0.2)',
                            yAxisID: 'y1',
                            tension: 0.2
                        }
                    ]
                },
                options: {
                    responsive: true,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    stacked: false,
                    scales: {
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {
                                display: true,
                                text: 'Threat Level'
                            },
                            min: 0,
                            max: 100
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            grid: {
                                drawOnChartArea: false,
                            },
                            title: {
                                display: true,
                                text: 'Anomalies Count'
                            },
                            min: 0
                        }
                    },
                    onClick: (event, elements) => {
                        if (elements.length > 0) {
                            const index = elements[0].index;
                            const analysisId = ids[index];
                            // Navigate to analysis details or load the analysis
                            this.loadAnalysisById(analysisId);
                        }
                    },
                    plugins: {
                        tooltip: {
                            callbacks: {
                                title: function(tooltipItems) {
                                    return labels[tooltipItems[0].dataIndex];
                                },
                                afterTitle: function(tooltipItems) {
                                    return urls[tooltipItems[0].dataIndex];
                                }
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error displaying threat timeline:', error);
            this.timelineContainer.innerHTML += `<p class="error">Error loading timeline: ${error.message}</p>`;
        }
    }

    async loadAnalysisById(id) {
        try {
            // Show loading spinner
            this.showSpinner();
            
            // Get analysis from history
            const response = await fetch(`/api/history`);
            if (!response.ok) throw new Error('Failed to fetch history');
            
            const history = await response.json();
            const analysis = history.find(item => item.id === id);
            
            if (!analysis) throw new Error('Analysis not found');
            
            // Display the results
            this.displayResults(analysis);
            
            // Hide loading spinner
            this.hideSpinner();
        } catch (error) {
            console.error('Error loading analysis by ID:', error);
            this.hideSpinner();
            this.showError(`Failed to load analysis: ${error.message}`);
        }
    }

    async displayWhoisInfo(url) {
        try {
            // Create WHOIS container if it doesn't exist
            if (!this.whoisContainer) {
                this.whoisContainer = document.createElement('div');
                this.whoisContainer.id = 'whois-info-container';
                this.whoisContainer.className = 'panel';
                this.whoisContainer.innerHTML = `
                    <h3>Domain Information</h3>
                    <div class="whois-loading">Loading domain information...</div>
                    <div class="whois-content"></div>
                `;
                
                // Add to the dashboard
                document.querySelector('#analysis-results').appendChild(this.whoisContainer);
            }
            
            // Show loading
            this.whoisContainer.querySelector('.whois-loading').style.display = 'block';
            this.whoisContainer.querySelector('.whois-content').innerHTML = '';
            
            // Fetch WHOIS info
            const response = await fetch(`/api/whois?url=${encodeURIComponent(url)}`);
            const whoisData = await response.json();
            
            // Hide loading
            this.whoisContainer.querySelector('.whois-loading').style.display = 'none';
            
            // Display error if any
            if (response.status !== 200 || whoisData.error) {
                this.whoisContainer.querySelector('.whois-content').innerHTML = `
                    <div class="error-message">
                        <p>${whoisData.error || 'Failed to retrieve domain information'}</p>
                        <p>${whoisData.message || ''}</p>
                    </div>
                `;
                return;
            }
            
            // Format and display the WHOIS data
            let html = `<div class="whois-info">`;
            
            // Domain section
            html += `<div class="whois-section">
                <h4>Domain: ${whoisData.domain}</h4>
                <div class="whois-grid">
                    ${whoisData.registrar ? `<div class="whois-item"><span>Registrar:</span> ${whoisData.registrar}</div>` : ''}
                    ${whoisData.creation_date ? `<div class="whois-item"><span>Created:</span> ${this.formatDate(whoisData.creation_date)}</div>` : ''}
                    ${whoisData.expiration_date ? `<div class="whois-item"><span>Expires:</span> ${this.formatDate(whoisData.expiration_date)}</div>` : ''}
                    ${whoisData.updated_date ? `<div class="whois-item"><span>Updated:</span> ${this.formatDate(whoisData.updated_date)}</div>` : ''}
                </div>
            </div>`;
            
            // Registrant section (if available)
            if (whoisData.name || whoisData.org) {
                html += `<div class="whois-section">
                    <h4>Registrant</h4>
                    <div class="whois-grid">
                        ${whoisData.name ? `<div class="whois-item"><span>Name:</span> ${whoisData.name}</div>` : ''}
                        ${whoisData.org ? `<div class="whois-item"><span>Organization:</span> ${whoisData.org}</div>` : ''}
                        ${whoisData.address ? `<div class="whois-item"><span>Address:</span> ${whoisData.address}</div>` : ''}
                        ${whoisData.city ? `<div class="whois-item"><span>City:</span> ${whoisData.city}</div>` : ''}
                        ${whoisData.state ? `<div class="whois-item"><span>State/Province:</span> ${whoisData.state}</div>` : ''}
                        ${whoisData.country ? `<div class="whois-item"><span>Country:</span> ${whoisData.country}</div>` : ''}
                        ${whoisData.zipcode ? `<div class="whois-item"><span>Postal Code:</span> ${whoisData.zipcode}</div>` : ''}
                    </div>
                </div>`;
            }
            
            // DNS section
            if (whoisData.name_servers) {
                let nameServers = Array.isArray(whoisData.name_servers) ? whoisData.name_servers : [whoisData.name_servers];
                html += `<div class="whois-section">
                    <h4>Name Servers</h4>
                    <ul class="name-servers-list">
                        ${nameServers.map(ns => `<li>${ns}</li>`).join('')}
                    </ul>
                </div>`;
            }
            
            html += `</div>`;
            
            this.whoisContainer.querySelector('.whois-content').innerHTML = html;
        } catch (error) {
            console.error('Error displaying WHOIS info:', error);
            this.whoisContainer.querySelector('.whois-loading').style.display = 'none';
            this.whoisContainer.querySelector('.whois-content').innerHTML = `
                <div class="error-message">
                    <p>Error retrieving domain information: ${error.message}</p>
                </div>
            `;
        }
    }

    // Helper function to format dates
    formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        } catch (e) {
            return dateStr; // Return as is if parsing fails
        }
    }

    displayRecommendations(result) {
        if (!result.safety_assessment || !result.safety_assessment.recommendations) {
            return;
        }
        
        // Create recommendations container if it doesn't exist
        if (!this.recommendationsContainer) {
            this.recommendationsContainer = document.createElement('div');
            this.recommendationsContainer.id = 'recommendations-container';
            this.recommendationsContainer.className = 'panel';
            this.recommendationsContainer.innerHTML = `
                <h3>Security Recommendations</h3>
                <div class="recommendations-content"></div>
            `;
            
            // Add to the dashboard
            document.querySelector('#analysis-results').appendChild(this.recommendationsContainer);
        }
        
        const recommendations = result.safety_assessment.recommendations;
        
        if (recommendations.length === 0) {
            this.recommendationsContainer.querySelector('.recommendations-content').innerHTML = `
                <p class="no-recommendations">No security recommendations at this time. The site appears to follow good security practices.</p>
            `;
            return;
        }
        
        // Display recommendations as a prioritized list
        let html = `<ul class="recommendations-list">`;
        
        recommendations.forEach((rec, index) => {
            const priority = index < 3 ? 'high' : (index < 6 ? 'medium' : 'low');
            html += `
                <li class="recommendation-item priority-${priority}">
                    <div class="recommendation-icon ${priority}"></div>
                    <div class="recommendation-text">
                        <span class="priority-label">${priority.charAt(0).toUpperCase() + priority.slice(1)} Priority:</span>
                        ${rec}
                    </div>
                </li>
            `;
        });
        
        html += `</ul>`;
        
        this.recommendationsContainer.querySelector('.recommendations-content').innerHTML = html;
    }

    addExportButtons(resultId) {
        // Create export container if it doesn't exist
        if (!this.exportContainer) {
            this.exportContainer = document.createElement('div');
            this.exportContainer.id = 'export-container';
            this.exportContainer.className = 'export-buttons';
            
            // Add to the results section
            const resultsHeader = document.querySelector('#analysis-results h2');
            if (resultsHeader) {
                resultsHeader.insertAdjacentElement('afterend', this.exportContainer);
            } else {
                document.querySelector('#analysis-results').prepend(this.exportContainer);
            }
        }
        
        // Update the container with export buttons
        this.exportContainer.innerHTML = `
            <h4>Export Report</h4>
            <div class="button-group">
                <button class="export-btn" data-format="pdf">
                    <i class="fas fa-file-pdf"></i> PDF Report
                </button>
                <button class="export-btn" data-format="csv">
                    <i class="fas fa-file-csv"></i> CSV Data
                </button>
                <button class="export-btn" data-format="json">
                    <i class="fas fa-file-code"></i> JSON Data
                </button>
            </div>
        `;
        
        // Add event listeners
        this.exportContainer.querySelectorAll('.export-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const format = btn.getAttribute('data-format');
                this.exportData(resultId, format);
            });
        });
    }

    exportData(resultId, format) {
        if (!resultId) {
            this.showError('No analysis data to export');
            return;
        }
        
        let url;
        switch (format) {
            case 'pdf':
                url = `/api/export-pdf?id=${resultId}`;
                window.open(url, '_blank');
                break;
            case 'csv':
                url = `/api/export?id=${resultId}&format=csv`;
                window.open(url, '_blank');
                break;
            case 'json':
                url = `/api/export?id=${resultId}&format=json`;
                window.open(url, '_blank');
                break;
            default:
                this.showError('Unsupported export format');
        }
    }

    addFiltersAndSearch() {
        // Create filters container if it doesn't exist
        if (!this.filtersContainer) {
            this.filtersContainer = document.createElement('div');
            this.filtersContainer.id = 'filters-container';
            this.filtersContainer.className = 'filters-panel';
            this.filtersContainer.innerHTML = `
                <h3>Filter Results</h3>
                <div class="search-box">
                    <input type="text" id="search-input" placeholder="Search by URL or content...">
                    <button id="search-button">
                        <i class="fas fa-search"></i>
                    </button>
                </div>
                <div class="filter-options">
                    <div class="filter-group">
                        <label>Anomaly Type</label>
                        <select id="anomaly-type-filter">
                            <option value="">All Types</option>
                            <option value="client_error">Client Error</option>
                            <option value="server_error">Server Error</option>
                            <option value="slow_request">Slow Request</option>
                            <option value="security_headers">Security Headers</option>
                            <option value="mixed_content">Mixed Content</option>
                            <option value="connection_error">Connection Error</option>
                            <option value="large_response">Large Response</option>
                            <option value="outdated_tls">Outdated TLS</option>
                            <option value="statistical_outlier">Statistical Outlier</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Confidence Level</label>
                        <select id="confidence-filter">
                            <option value="">All Levels</option>
                            <option value="high">High</option>
                            <option value="medium">Medium</option>
                            <option value="low">Low</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Status Code</label>
                        <select id="status-code-filter">
                            <option value="">All Status Codes</option>
                            <option value="2xx">2xx (Success)</option>
                            <option value="3xx">3xx (Redirection)</option>
                            <option value="4xx">4xx (Client Error)</option>
                            <option value="5xx">5xx (Server Error)</option>
                        </select>
                    </div>
                </div>
                <div class="filter-actions">
                    <button id="apply-filters" class="primary-button">Apply Filters</button>
                    <button id="reset-filters">Reset</button>
                </div>
            `;
            
            // Add to the dashboard in appropriate location
            const resultsContainer = document.querySelector('#analysis-results');
            const resultsHeader = resultsContainer.querySelector('h2');
            if (resultsHeader) {
                resultsHeader.insertAdjacentElement('afterend', this.filtersContainer);
            } else {
                resultsContainer.prepend(this.filtersContainer);
            }
            
            // Add event listeners
            this.filtersContainer.querySelector('#search-button').addEventListener('click', () => {
                this.applyFilters();
            });
            
            this.filtersContainer.querySelector('#search-input').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.applyFilters();
                }
            });
            
            this.filtersContainer.querySelector('#apply-filters').addEventListener('click', () => {
                this.applyFilters();
            });
            
            this.filtersContainer.querySelector('#reset-filters').addEventListener('click', () => {
                this.resetFilters();
            });
        }
    }

    applyFilters() {
        // Get filter values
        const searchText = document.getElementById('search-input').value.toLowerCase();
        const anomalyType = document.getElementById('anomaly-type-filter').value;
        const confidenceLevel = document.getElementById('confidence-filter').value;
        const statusCodeFilter = document.getElementById('status-code-filter').value;
        
        // Apply filters to the anomalies table
        const table = document.querySelector('#anomalies-table');
        if (!table) return;
        
        const rows = table.querySelectorAll('tbody tr');
        let visibleCount = 0;
        
        rows.forEach(row => {
            const url = row.querySelector('td:nth-child(1)').textContent.toLowerCase();
            const type = row.getAttribute('data-type') || '';
            const confidence = row.getAttribute('data-confidence') || '';
            const statusCode = row.querySelector('td:nth-child(2)').textContent;
            
            let visible = true;
            
            // Apply search filter
            if (searchText && !url.includes(searchText)) {
                visible = false;
            }
            
            // Apply anomaly type filter
            if (anomalyType && type !== anomalyType) {
                visible = false;
            }
            
            // Apply confidence filter
            if (confidenceLevel && confidence !== confidenceLevel) {
                visible = false;
            }
            
            // Apply status code filter
            if (statusCodeFilter) {
                const firstDigit = statusCode.charAt(0);
                if (statusCodeFilter === '2xx' && firstDigit !== '2') visible = false;
                if (statusCodeFilter === '3xx' && firstDigit !== '3') visible = false;
                if (statusCodeFilter === '4xx' && firstDigit !== '4') visible = false;
                if (statusCodeFilter === '5xx' && firstDigit !== '5') visible = false;
            }
            
            // Show or hide the row
            row.style.display = visible ? '' : 'none';
            if (visible) visibleCount++;
        });
        
        // Show a message if no results found
        const noResultsMessage = document.getElementById('no-filter-results');
        if (visibleCount === 0) {
            if (!noResultsMessage) {
                const message = document.createElement('div');
                message.id = 'no-filter-results';
                message.className = 'no-results-message';
                message.textContent = 'No anomalies match the selected filters.';
                table.parentNode.appendChild(message);
            }
        } else if (noResultsMessage) {
            noResultsMessage.remove();
        }
        
        // Update the filter summary
        this.updateFilterSummary(visibleCount, rows.length);
    }

    resetFilters() {
        document.getElementById('search-input').value = '';
        document.getElementById('anomaly-type-filter').value = '';
        document.getElementById('confidence-filter').value = '';
        document.getElementById('status-code-filter').value = '';
        
        this.applyFilters();
    }

    updateFilterSummary(visibleCount, totalCount) {
        let summaryElement = document.getElementById('filter-summary');
        
        if (!summaryElement) {
            summaryElement = document.createElement('div');
            summaryElement.id = 'filter-summary';
            summaryElement.className = 'filter-summary';
            
            // Add after the filter actions
            const filterActions = document.querySelector('.filter-actions');
            filterActions.insertAdjacentElement('afterend', summaryElement);
        }
        
        summaryElement.textContent = `Showing ${visibleCount} of ${totalCount} anomalies`;
        
        // Only show if filters are active
        if (visibleCount < totalCount) {
            summaryElement.style.display = 'block';
        } else {
            summaryElement.style.display = 'none';
        }
    }

    displayAnomalies(result) {
        if (!result.anomalies || result.anomalies.length === 0) {
            return;
        }
        
        // Create anomalies container if it doesn't exist
        if (!this.anomaliesContainer) {
            this.anomaliesContainer = document.createElement('div');
            this.anomaliesContainer.id = 'anomalies-container';
            this.anomaliesContainer.className = 'panel';
            this.anomaliesContainer.innerHTML = `
                <h3>Detected Anomalies</h3>
                <div class="table-responsive">
                    <table id="anomalies-table" class="data-table">
                        <thead>
                            <tr>
                                <th>URL</th>
                                <th>Status</th>
                                <th>Type</th>
                                <th>Reason</th>
                                <th>AI Confidence</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            `;
            
            // Add to the dashboard
            document.querySelector('#analysis-results').appendChild(this.anomaliesContainer);
        }
        
        const tableBody = this.anomaliesContainer.querySelector('tbody');
        tableBody.innerHTML = '';
        
        // Add each anomaly as a row
        result.anomalies.forEach(anomaly => {
            const row = document.createElement('tr');
            
            // Set data attributes for filtering
            row.setAttribute('data-type', anomaly.anomaly_type || '');
            row.setAttribute('data-confidence', anomaly.confidence_level || 'medium');
            
            // Create cells
            const urlCell = document.createElement('td');
            urlCell.className = 'url-cell';
            urlCell.textContent = this.truncateUrl(anomaly.url || 'N/A');
            urlCell.title = anomaly.url || 'N/A';
            
            const statusCell = document.createElement('td');
            statusCell.className = 'status-cell';
            statusCell.textContent = anomaly.status_code || 'N/A';
            
            const typeCell = document.createElement('td');
            typeCell.className = 'type-cell';
            typeCell.textContent = this.formatAnomalyType(anomaly.anomaly_type || 'unknown');
            
            const reasonCell = document.createElement('td');
            reasonCell.className = 'reason-cell';
            reasonCell.textContent = anomaly.reason || 'Unknown';
            
            // Create confidence cell with visual indicator
            const confidenceCell = document.createElement('td');
            confidenceCell.className = 'confidence-cell';
            
            const confidenceScore = anomaly.confidence_score || 0.7;
            const confidenceLevel = anomaly.confidence_level || 'medium';
            
            confidenceCell.innerHTML = `
                <div class="confidence-indicator">
                    <div class="confidence-bar ${confidenceLevel}" style="width: ${confidenceScore * 100}%"></div>
                    <span class="confidence-value">${Math.round(confidenceScore * 100)}%</span>
                </div>
            `;
            
            // Add cells to row
            row.appendChild(urlCell);
            row.appendChild(statusCell);
            row.appendChild(typeCell);
            row.appendChild(reasonCell);
            row.appendChild(confidenceCell);
            
            // Add row to table
            tableBody.appendChild(row);
        });
    }

    // Helper method to format anomaly types
    formatAnomalyType(type) {
        const formatMap = {
            'client_error': 'Client Error',
            'server_error': 'Server Error',
            'slow_request': 'Slow Request',
            'security_headers': 'Security Headers',
            'mixed_content': 'Mixed Content',
            'connection_error': 'Connection Error',
            'large_response': 'Large Response',
            'outdated_tls': 'Outdated TLS',
            'statistical_outlier': 'Statistical Outlier'
        };
        
        return formatMap[type] || type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    // Helper method to truncate URLs for display
    truncateUrl(url) {
        if (!url) return 'N/A';
        
        const maxLength = 50;
        if (url.length <= maxLength) return url;
        
        // Truncate in the middle
        const start = url.substring(0, 25);
        const end = url.substring(url.length - 20);
        return `${start}...${end}`;
    }
}


document.addEventListener('DOMContentLoaded', () => {
    // Use window.dashboard to make it global
    window.dashboard = new Dashboard();
    window.dashboard.initialize();
});


export default Dashboard;