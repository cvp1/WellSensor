// Well Tank Monitor PWA
class WellTankMonitor {
    constructor() {
        this.apiBase = '/api';
        this.currentData = null;
        this.historyChart = null;
        this.updateInterval = null;
        this.isOnline = navigator.onLine;
        
        this.init();
    }

    async init() {
        this.setupEventListeners();
        this.setupServiceWorker();
        this.setupOnlineStatus();
        await this.loadInitialData();
        this.startAutoRefresh();
    }

    setupEventListeners() {
        // Header buttons
        document.getElementById('refreshBtn').addEventListener('click', () => this.refreshData());
        document.getElementById('settingsBtn').addEventListener('click', () => this.showSettings());

        // Action buttons
        document.getElementById('forceReadingBtn').addEventListener('click', () => this.forceReading());
        document.getElementById('historyBtn').addEventListener('click', () => this.showHistory());
        document.getElementById('alertsBtn').addEventListener('click', () => this.showAlerts());
        document.getElementById('configBtn').addEventListener('click', () => this.showSettings());
        document.getElementById('viewAllAlertsBtn').addEventListener('click', () => this.showAlerts());

        // Test notification buttons
        document.getElementById('testPushBtn').addEventListener('click', () => this.testPushNotification());
        document.getElementById('testEmailBtn').addEventListener('click', () => this.testEmailAlert());
        
        // Alert system control
        document.getElementById('toggleAlertsBtn').addEventListener('click', () => this.toggleAlertSystem());

        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.target.closest('.modal').classList.remove('show');
            });
        });

        // Modal backdrop clicks
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.remove('show');
                }
            });
        });

        // Settings
        document.getElementById('enableNotifications').addEventListener('change', (e) => {
            this.handleNotificationToggle(e.target.checked);
        });

        document.getElementById('subscribeBtn').addEventListener('click', () => {
            this.subscribeToNotifications();
        });
    }

    setupServiceWorker() {
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js')
                .then(registration => {
                    console.log('SW registered: ', registration);
                })
                .catch(registrationError => {
                    console.log('SW registration failed: ', registrationError);
                });
        }
    }

    setupOnlineStatus() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.showToast('Connection restored', 'success');
            this.refreshData();
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.showToast('Connection lost', 'warning');
        });
    }

    async loadInitialData() {
        try {
            this.showLoading(true);
            await this.refreshData();
            await this.loadRecentAlerts();
            await this.loadConfig();
            await this.loadAlertSystemStatus();
        } catch (error) {
            console.error('Error loading initial data:', error);
            this.showToast('Failed to load data', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async refreshData() {
        try {
            const response = await fetch(`${this.apiBase}/current`);
            if (!response.ok) {
                if (response.status === 404) {
                    // No data available yet - this is normal
                    console.log('No current data available yet');
                    return;
                }
                throw new Error(`HTTP ${response.status}: Failed to fetch data`);
            }
            
            const data = await response.json();
            this.updateUI(data);
            this.currentData = data;
        } catch (error) {
            console.error('Error refreshing data:', error);
            if (!error.message.includes('404')) {
                this.showToast('Failed to refresh data', 'error');
            }
        }
    }

    updateUI(data) {
        // Update tank visualization
        const waterLevel = document.getElementById('waterLevel');
        const fillPercentage = document.getElementById('fillPercentage');
        const percentage = data.fill_percentage || 0;
        
        waterLevel.style.height = `${percentage}%`;
        fillPercentage.textContent = percentage.toFixed(1);

        // Add visual severity indicators
        const tankContainer = document.querySelector('.tank-container');
        tankContainer.classList.remove('emergency', 'critical', 'low', 'normal');
        
        if (percentage <= 5) {
            tankContainer.classList.add('emergency');
        } else if (percentage <= 10) {
            tankContainer.classList.add('critical');
        } else if (percentage <= 20) {
            tankContainer.classList.add('low');
        } else {
            tankContainer.classList.add('normal');
        }

        // Update status details
        document.getElementById('waterLevelCm').textContent = `${(data.water_level_cm || 0).toFixed(1)} cm`;
        document.getElementById('gallons').textContent = `${(data.gallons || 0).toFixed(0)} gal`;
        document.getElementById('distanceCm').textContent = `${(data.distance_cm || 0).toFixed(1)} cm`;
        document.getElementById('wifiRssi').textContent = `${data.wifi_rssi || 0} dBm`;
        
        // Update battery voltage
        const batteryElement = document.getElementById('batteryVoltage');
        if (data.battery_voltage && data.battery_voltage > 0) {
            batteryElement.textContent = `${data.battery_voltage.toFixed(1)} V`;
            
            // Add battery level indicator
            if (data.battery_voltage < 11.0) {
                batteryElement.classList.add('low-battery');
            } else {
                batteryElement.classList.remove('low-battery');
            }
        } else {
            batteryElement.textContent = '-- V';
        }

        // Update timestamp
        const lastUpdate = document.getElementById('lastUpdate');
        lastUpdate.textContent = new Date().toLocaleTimeString();

        // Add fade-in animation
        document.querySelector('.status-card').classList.add('fade-in');
        setTimeout(() => {
            document.querySelector('.status-card').classList.remove('fade-in');
        }, 300);
    }

    async forceReading() {
        try {
            this.showLoading(true);
            const response = await fetch(`${this.apiBase}/force-reading`);
            if (!response.ok) throw new Error('Failed to force reading');
            
            const result = await response.json();
            if (result.success) {
                this.updateUI(result.data);
                this.showToast('New reading taken successfully', 'success');
            } else {
                throw new Error(result.error || 'Failed to take reading');
            }
        } catch (error) {
            console.error('Error forcing reading:', error);
            this.showToast('Failed to take new reading', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async showHistory() {
        try {
            this.showLoading(true);
            const response = await fetch(`${this.apiBase}/history`);
            if (!response.ok) throw new Error('Failed to fetch history');
            
            const history = await response.json();
            this.displayHistory(history);
            document.getElementById('historyModal').classList.add('show');
        } catch (error) {
            console.error('Error loading history:', error);
            this.showToast('Failed to load history', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    displayHistory(history) {
        const historyList = document.getElementById('historyList');
        const chartContainer = document.getElementById('historyChart');
        
        // Clear previous content
        historyList.innerHTML = '';
        
        if (history.length === 0) {
            historyList.innerHTML = '<div class="loading">No history data available</div>';
            return;
        }

        // Create chart
        this.createHistoryChart(history, chartContainer);

        // Create history list
        history.forEach(reading => {
            const item = document.createElement('div');
            item.className = 'history-item';
            
            let timestamp = 'Unknown';
            if (reading.timestamp) {
                if (reading.timestamp.toDate) {
                    timestamp = new Date(reading.timestamp.toDate()).toLocaleString();
                } else if (reading.timestamp.seconds) {
                    timestamp = new Date(reading.timestamp.seconds * 1000).toLocaleString();
                } else {
                    timestamp = new Date(reading.timestamp).toLocaleString();
                }
            }
            
            const percentage = reading.fill_percentage ? reading.fill_percentage.toFixed(1) : '0';
            
            item.innerHTML = `
                <div class="history-info">
                    <div class="history-time">${timestamp}</div>
                    <div class="history-value">${reading.gallons ? reading.gallons.toFixed(0) : '0'} gallons</div>
                </div>
                <div class="history-value">${percentage}%</div>
            `;
            
            historyList.appendChild(item);
        });
    }

    createHistoryChart(history, container) {
        const ctx = document.getElementById('historyCanvas');
        
        // Check if Chart.js is available
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js not loaded, skipping chart creation');
            container.innerHTML = '<div class="loading">Chart.js not available. Please refresh the page.</div>';
            return;
        }
        
        // Destroy existing chart
        if (this.historyChart) {
            this.historyChart.destroy();
        }

        // Prepare data
        const labels = history.map(reading => {
            let date = new Date();
            if (reading.timestamp) {
                if (reading.timestamp.toDate) {
                    date = new Date(reading.timestamp.toDate());
                } else if (reading.timestamp.seconds) {
                    date = new Date(reading.timestamp.seconds * 1000);
                } else {
                    date = new Date(reading.timestamp);
                }
            }
            return date.toLocaleTimeString();
        }).reverse();

        const data = history.map(reading => reading.fill_percentage || 0).reverse();

        try {
            // Create new chart
            this.historyChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Fill Percentage',
                        data: data,
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                callback: function(value) {
                                    return value + '%';
                                }
                            }
                        },
                        x: {
                            ticks: {
                                maxTicksLimit: 8
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error creating chart:', error);
            container.innerHTML = '<div class="loading">Error creating chart. Please try again.</div>';
        }
    }

    async loadRecentAlerts() {
        try {
            const response = await fetch(`${this.apiBase}/alerts?t=${Date.now()}`);
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            
            const alerts = await response.json();
            this.displayRecentAlerts(alerts.slice(0, 5)); // Show only 5 most recent
        } catch (error) {
            console.error('Error loading alerts:', error);
            // Don't show error toast for recent alerts, just log it
        }
    }

    displayRecentAlerts(alerts) {
        const container = document.getElementById('recentAlerts');
        
        if (alerts.length === 0) {
            container.innerHTML = '<div class="loading">No recent alerts</div>';
            return;
        }

        container.innerHTML = alerts.map(alert => {
            let timestamp = 'Unknown';
            if (alert.timestamp) {
                if (alert.timestamp.toDate) {
                    timestamp = new Date(alert.timestamp.toDate()).toLocaleString();
                } else if (alert.timestamp.seconds) {
                    timestamp = new Date(alert.timestamp.seconds * 1000).toLocaleString();
                } else {
                    timestamp = new Date(alert.timestamp).toLocaleString();
                }
            }
            
            const isIncrease = alert.current_level > alert.previous_level;
            const icon = isIncrease ? '📈' : '📉';
            const iconClass = isIncrease ? 'increase' : 'decrease';
            const changeClass = isIncrease ? 'increase' : 'decrease';
            
            return `
                <div class="alert-item">
                    <div class="alert-icon ${iconClass}">${icon}</div>
                    <div class="alert-content">
                        <div class="alert-title">Water level ${isIncrease ? 'increased' : 'decreased'}</div>
                        <div class="alert-time">${timestamp}</div>
                    </div>
                    <div class="alert-change ${changeClass}">
                        ${alert.percent_change ? alert.percent_change.toFixed(1) : '0'}%
                    </div>
                </div>
            `;
        }).join('');
    }

    async showAlerts() {
        try {
            this.showLoading(true);
            const response = await fetch(`${this.apiBase}/alerts?t=${Date.now()}`);
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            
            const alerts = await response.json();
            this.displayAllAlerts(alerts);
            document.getElementById('alertsModal').classList.add('show');
        } catch (error) {
            console.error('Error loading alerts:', error);
            this.showToast(`Failed to load alerts: ${error.message}`, 'error');
        } finally {
            this.showLoading(false);
        }
    }

    displayAllAlerts(alerts) {
        const container = document.getElementById('alertsList');
        
        if (alerts.length === 0) {
            container.innerHTML = '<div class="loading">No alerts found</div>';
            return;
        }

        container.innerHTML = alerts.map(alert => {
            let timestamp = 'Unknown';
            if (alert.timestamp) {
                if (alert.timestamp.toDate) {
                    timestamp = new Date(alert.timestamp.toDate()).toLocaleString();
                } else if (alert.timestamp.seconds) {
                    timestamp = new Date(alert.timestamp.seconds * 1000).toLocaleString();
                } else {
                    timestamp = new Date(alert.timestamp).toLocaleString();
                }
            }
            
            // Determine alert type and severity
            const alertType = alert.type || 'change';
            const severity = alert.severity || 'normal';
            const isIncrease = alert.current_level > alert.previous_level;
            
            // Enhanced icon and title mapping
            const iconMap = {
                'emergency_level': '🚨',
                'critical_level': '⚠️',
                'low_level': '📉',
                'rapid_drop': '⬇️',
                'predictive': '🔮',
                'low_battery': '🔋'
            };
            
            const titleMap = {
                'emergency_level': 'EMERGENCY - Tank Nearly Empty',
                'critical_level': 'CRITICAL - Very Low Water Level',
                'low_level': 'Low Water Level Warning',
                'rapid_drop': 'Rapid Water Level Drop',
                'predictive': 'Predictive Low Water Alert',
                'low_battery': 'Low Battery Alert'
            };
            
            const icon = iconMap[alertType] || (isIncrease ? '📈' : '📉');
            const iconClass = severity;
            const changeClass = isIncrease ? 'increase' : 'decrease';
            const title = titleMap[alertType] || `Water level ${isIncrease ? 'increased' : 'decreased'}`;
            
            // Build alert details based on type
            let alertDetails = '';
            if (alertType === 'predictive') {
                const hoursRemaining = alert.hours_remaining || 0;
                alertDetails = `Estimated ${hoursRemaining.toFixed(1)} hours remaining`;
            } else if (alertType === 'low_battery') {
                const batteryVoltage = alert.battery_voltage || 0;
                alertDetails = `Battery voltage: ${batteryVoltage.toFixed(1)}V`;
            } else {
                alertDetails = `From ${alert.previous_level ? alert.previous_level.toFixed(1) : '0'}% to ${alert.current_level ? alert.current_level.toFixed(1) : '0'}%`;
            }
            
            const changeText = alertType === 'predictive' || alertType === 'low_battery' 
                ? `${alert.current_gallons ? alert.current_gallons.toFixed(0) : '0'} gal`
                : `${alert.percent_change ? alert.percent_change.toFixed(1) : '0'}%`;
            
            return `
                <div class="alert-item ${severity}">
                    <div class="alert-icon ${iconClass}">${icon}</div>
                    <div class="alert-content">
                        <div class="alert-title">${title}</div>
                        <div class="alert-time">${timestamp}</div>
                        <div class="alert-details">${alertDetails}</div>
                        ${alert.usage_rate ? `<div class="alert-usage">Usage rate: ${alert.usage_rate.toFixed(2)} gal/hr</div>` : ''}
                    </div>
                    <div class="alert-change ${changeClass}">
                        ${changeText}
                    </div>
                </div>
            `;
        }).join('');
    }

    async loadConfig() {
        try {
            const response = await fetch(`${this.apiBase}/config`);
            if (!response.ok) throw new Error('Failed to fetch config');
            
            const config = await response.json();
            this.updateConfigUI(config);
        } catch (error) {
            console.error('Error loading config:', error);
        }
    }

    updateConfigUI(config) {
        document.getElementById('esp32Ip').textContent = config.esp32_ip || '--';
        document.getElementById('alertThreshold').textContent = `${config.alert_threshold || 0}%`;
        document.getElementById('alertCooldown').textContent = `${config.alert_cooldown || 0} min`;
        document.getElementById('firebaseStatus').textContent = config.firebase_connected ? 'Connected' : 'Disconnected';
        
        // Update enhanced alert configuration
        if (config.enhanced_alerts) {
            const enhancedConfig = config.enhanced_alerts;
            const configDetails = document.getElementById('enhancedConfigDetails') || this.createEnhancedConfigSection();
            
            configDetails.innerHTML = `
                <h4>Enhanced Alert Thresholds</h4>
                <div class="config-item">Low Level: ${enhancedConfig.low_level_threshold}%</div>
                <div class="config-item">Critical Level: ${enhancedConfig.critical_level_threshold}%</div>
                <div class="config-item">Emergency Level: ${enhancedConfig.emergency_level_threshold}%</div>
                <div class="config-item">Rapid Drop: ${enhancedConfig.rapid_drop_threshold}%</div>
                <div class="config-item">Email Alerts: ${enhancedConfig.email_alerts_enabled ? 'Enabled' : 'Disabled'}</div>
            `;
        }
        
        // Update usage statistics
        if (config.usage_stats) {
            const usageStats = config.usage_stats;
            const usageDetails = document.getElementById('usageStatsDetails') || this.createUsageStatsSection();
            
            const usageRateText = usageStats.current_usage_rate_gph > 0 
                ? `${usageStats.current_usage_rate_gph.toFixed(2)} gal/hr`
                : 'Calculating...';
                
            const daysRemainingText = usageStats.days_remaining !== null && usageStats.days_remaining > 0
                ? `${usageStats.days_remaining.toFixed(1)} days`
                : 'N/A';
            
            usageDetails.innerHTML = `
                <h4>Usage Statistics</h4>
                <div class="config-item">Current Usage Rate: ${usageRateText}</div>
                <div class="config-item">Estimated Days Remaining: ${daysRemainingText}</div>
            `;
        }
    }
    
    createEnhancedConfigSection() {
        const settingsContent = document.querySelector('#settingsModal .modal-content');
        const enhancedSection = document.createElement('div');
        enhancedSection.id = 'enhancedConfigDetails';
        enhancedSection.className = 'enhanced-config-section';
        settingsContent.appendChild(enhancedSection);
        return enhancedSection;
    }
    
    createUsageStatsSection() {
        const settingsContent = document.querySelector('#settingsModal .modal-content');
        const usageSection = document.createElement('div');
        usageSection.id = 'usageStatsDetails';
        usageSection.className = 'usage-stats-section';
        settingsContent.appendChild(usageSection);
        return usageSection;
    }

    showSettings() {
        document.getElementById('settingsModal').classList.add('show');
    }

    async handleNotificationToggle(enabled) {
        const subscribeBtn = document.getElementById('subscribeBtn');
        
        if (enabled) {
            if ('Notification' in window) {
                try {
                    const permission = await Notification.requestPermission();
                    if (permission === 'granted') {
                        subscribeBtn.disabled = false;
                        this.showToast('Notifications enabled', 'success');
                    } else if (permission === 'denied') {
                        document.getElementById('enableNotifications').checked = false;
                        this.showToast('Notification permission denied. Please enable notifications in your browser settings.', 'error');
                    } else {
                        document.getElementById('enableNotifications').checked = false;
                        this.showToast('Notification permission cancelled', 'warning');
                    }
                } catch (error) {
                    document.getElementById('enableNotifications').checked = false;
                    this.showToast('Push notifications require HTTPS. Use https://localhost:8443 for notifications.', 'error');
                }
            } else {
                document.getElementById('enableNotifications').checked = false;
                this.showToast('Notifications not supported in this browser', 'error');
            }
        } else {
            subscribeBtn.disabled = true;
        }
    }

    async subscribeToNotifications() {
        try {
            // This would integrate with Firebase Cloud Messaging
            // For now, we'll just show a success message
            this.showToast('Subscribed to alerts', 'success');
        } catch (error) {
            console.error('Error subscribing to notifications:', error);
            this.showToast('Failed to subscribe', 'error');
        }
    }

    startAutoRefresh() {
        // Refresh data every 30 seconds
        this.updateInterval = setInterval(() => {
            if (this.isOnline) {
                this.refreshData();
            }
        }, 30000);
    }

    showLoading(show) {
        const overlay = document.getElementById('loadingOverlay');
        if (show) {
            overlay.classList.add('show');
        } else {
            overlay.classList.remove('show');
        }
    }

    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const id = Date.now();
        toast.innerHTML = `
            <div class="toast-header">
                <div class="toast-title">${this.getToastTitle(type)}</div>
                <button class="toast-close" onclick="this.parentElement.parentElement.remove()">&times;</button>
            </div>
            <div class="toast-message">${message}</div>
        `;
        
        container.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 5000);
    }

    getToastTitle(type) {
        switch (type) {
            case 'success': return 'Success';
            case 'error': return 'Error';
            case 'warning': return 'Warning';
            default: return 'Info';
        }
    }

    async testPushNotification() {
        try {
            this.showLoading(true);
            const response = await fetch(`${this.apiBase}/test-push-notification`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showToast('Test push notification sent successfully!', 'success');
            } else {
                throw new Error(result.error || 'Failed to send test push notification');
            }
        } catch (error) {
            console.error('Error sending test push notification:', error);
            this.showToast(`Failed to send test push notification: ${error.message}`, 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async testEmailAlert() {
        try {
            this.showLoading(true);
            const response = await fetch(`${this.apiBase}/test-email`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showToast('Test email sent successfully! Check your inbox.', 'success');
            } else {
                throw new Error(result.error || 'Failed to send test email');
            }
        } catch (error) {
            console.error('Error sending test email:', error);
            this.showToast(`Failed to send test email: ${error.message}`, 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async loadAlertSystemStatus() {
        try {
            const response = await fetch(`${this.apiBase}/alerts/status`);
            if (!response.ok) throw new Error('Failed to fetch alert status');
            
            const status = await response.json();
            this.updateAlertSystemUI(status);
        } catch (error) {
            console.error('Error loading alert system status:', error);
            this.updateAlertSystemUI({ alerts_enabled: false, error: true });
        }
    }

    updateAlertSystemUI(status) {
        const statusElement = document.getElementById('alertSystemStatus');
        const toggleBtn = document.getElementById('toggleAlertsBtn');
        const toggleText = document.getElementById('toggleAlertsText');
        const toggleIcon = toggleBtn.querySelector('i');

        if (status.error) {
            statusElement.textContent = 'Error';
            statusElement.className = 'status-value disabled';
            toggleText.textContent = 'Error';
            toggleBtn.disabled = true;
            return;
        }

        const isEnabled = status.alerts_enabled;
        
        // Update status display
        statusElement.textContent = isEnabled ? 'Enabled' : 'Disabled';
        statusElement.className = `status-value ${isEnabled ? 'enabled' : 'disabled'}`;
        
        // Update toggle button
        toggleText.textContent = isEnabled ? 'Disable' : 'Enable';
        toggleIcon.className = isEnabled ? 'fas fa-toggle-on' : 'fas fa-toggle-off';
        toggleBtn.className = `btn ${isEnabled ? 'btn-primary' : 'btn-secondary'}`;
        toggleBtn.disabled = false;
    }

    async toggleAlertSystem() {
        try {
            this.showLoading(true);
            const response = await fetch(`${this.apiBase}/alerts/toggle`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: '{}' // Always send a valid JSON body
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.updateAlertSystemUI({ alerts_enabled: result.alerts_enabled });
                this.showToast(`Alert system ${result.alerts_enabled ? 'enabled' : 'disabled'}`, 'success');
            } else {
                throw new Error(result.error || 'Failed to toggle alert system');
            }
        } catch (error) {
            console.error('Error toggling alert system:', error);
            this.showToast(`Failed to toggle alert system: ${error.message}`, 'error');
        } finally {
            this.showLoading(false);
        }
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new WellTankMonitor();
});

// Handle beforeinstallprompt for PWA installation
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    
    // Show install button or prompt
    // You can add an install button to your UI here
});

// Handle app installed
window.addEventListener('appinstalled', () => {
    console.log('PWA was installed');
    deferredPrompt = null;
}); 