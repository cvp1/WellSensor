import os
import json
import requests
import schedule
import time
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
ESP32_IP = os.getenv('ESP32_IP', '192.168.86.90')
ESP32_PORT = os.getenv('ESP32_PORT', '80')
ALERT_THRESHOLD = float(os.getenv('ALERT_THRESHOLD_PERCENT', '10'))
ALERT_COOLDOWN = int(os.getenv('ALERT_COOLDOWN_MINUTES', '30'))

# Enhanced Alert Thresholds
LOW_LEVEL_THRESHOLD = float(os.getenv('LOW_LEVEL_THRESHOLD', '20'))
CRITICAL_LEVEL_THRESHOLD = float(os.getenv('CRITICAL_LEVEL_THRESHOLD', '10'))
EMERGENCY_LEVEL_THRESHOLD = float(os.getenv('EMERGENCY_LEVEL_THRESHOLD', '5'))
RAPID_DROP_THRESHOLD = float(os.getenv('RAPID_DROP_THRESHOLD', '15'))
SUSTAINED_DROP_THRESHOLD = float(os.getenv('SUSTAINED_DROP_THRESHOLD', '5'))

# Cooldown Settings
NORMAL_COOLDOWN = int(os.getenv('NORMAL_COOLDOWN', '30'))
DROP_COOLDOWN = int(os.getenv('DROP_COOLDOWN', '15'))
CRITICAL_COOLDOWN = int(os.getenv('CRITICAL_COOLDOWN', '5'))
EMERGENCY_COOLDOWN = int(os.getenv('EMERGENCY_COOLDOWN', '0'))

# Email Configuration
ENABLE_EMAIL_ALERTS = os.getenv('ENABLE_EMAIL_ALERTS', 'false').lower() == 'true'
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
ALERT_EMAIL = os.getenv('ALERT_EMAIL')
ALERT_EMAIL_PASSWORD = os.getenv('ALERT_EMAIL_PASSWORD')

# Global variables
last_reading = None
last_alert_time = None
last_critical_alert_time = None
last_emergency_alert_time = None
alert_history = []
usage_history = []

# Initialize Firebase
try:
    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": os.getenv('FIREBASE_PROJECT_ID'),
        "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
        "private_key": os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n'),
        "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
        "client_id": os.getenv('FIREBASE_CLIENT_ID'),
        "auth_uri": os.getenv('FIREBASE_AUTH_URI'),
        "token_uri": os.getenv('FIREBASE_TOKEN_URI'),
        "auth_provider_x509_cert_url": os.getenv('FIREBASE_AUTH_PROVIDER_X509_CERT_URL'),
        "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL')
    })
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    firebase_initialized = True
    print("Firebase initialized successfully")
except Exception as e:
    print(f"Firebase initialization failed: {e}")
    firebase_initialized = False

def get_esp32_data():
    """Fetch data from ESP32 sensor"""
    try:
        url = f"http://{ESP32_IP}:{ESP32_PORT}/status"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching ESP32 data: {e}")
        return None

def send_email_alert(subject, body):
    """Send email alert"""
    if not ENABLE_EMAIL_ALERTS or not ALERT_EMAIL or not ALERT_EMAIL_PASSWORD:
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = ALERT_EMAIL
        msg['To'] = ALERT_EMAIL
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(ALERT_EMAIL, ALERT_EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(ALERT_EMAIL, ALERT_EMAIL, text)
        server.quit()
        
        print(f"Email alert sent: {subject}")
        return True
    except Exception as e:
        print(f"Error sending email alert: {e}")
        return False

def get_alert_severity(current_percent, is_drop=False, percent_change=0):
    """Determine alert severity based on current level and change"""
    if current_percent <= EMERGENCY_LEVEL_THRESHOLD:
        return 'emergency'
    elif current_percent <= CRITICAL_LEVEL_THRESHOLD:
        return 'critical'
    elif current_percent <= LOW_LEVEL_THRESHOLD:
        return 'low'
    elif is_drop and percent_change >= RAPID_DROP_THRESHOLD:
        return 'rapid_drop'
    else:
        return 'normal'

def get_cooldown_for_severity(severity):
    """Get appropriate cooldown time based on severity"""
    cooldown_map = {
        'emergency': EMERGENCY_COOLDOWN,
        'critical': CRITICAL_COOLDOWN,
        'low': DROP_COOLDOWN,
        'rapid_drop': DROP_COOLDOWN,
        'normal': NORMAL_COOLDOWN
    }
    return cooldown_map.get(severity, NORMAL_COOLDOWN)

def should_send_alert(severity, last_alert_time_for_type):
    """Check if alert should be sent based on severity and cooldown"""
    cooldown_minutes = get_cooldown_for_severity(severity)
    
    if cooldown_minutes == 0:  # Emergency - always send
        return True
    
    if last_alert_time_for_type is None:
        return True
    
    return datetime.now() - last_alert_time_for_type > timedelta(minutes=cooldown_minutes)

def calculate_usage_rate():
    """Calculate water usage rate from historical data"""
    if len(usage_history) < 2:
        return 0
    
    # Get last 24 hours of data
    recent_data = [r for r in usage_history if 
                  datetime.now() - r['timestamp'] <= timedelta(hours=24)]
    
    if len(recent_data) < 2:
        return 0
    
    # Calculate gallons used per hour
    time_diff = (recent_data[-1]['timestamp'] - recent_data[0]['timestamp']).total_seconds() / 3600
    gallon_diff = recent_data[0]['gallons'] - recent_data[-1]['gallons']
    
    if time_diff > 0:
        return gallon_diff / time_diff
    return 0

def calculate_days_remaining(current_gallons):
    """Calculate estimated days until tank is empty"""
    usage_rate = calculate_usage_rate()
    
    if usage_rate <= 0:
        return None
    
    # Calculate gallons per day
    gallons_per_day = usage_rate * 24
    
    if gallons_per_day <= 0:
        return None
    
    return current_gallons / gallons_per_day

def check_for_alerts(current_data, previous_data):
    """Enhanced alert checking with multiple severity levels and drop detection"""
    global last_alert_time, last_critical_alert_time, last_emergency_alert_time, usage_history
    
    if not previous_data or not firebase_initialized:
        return
    
    current_percent = current_data.get('fill_percentage', 0)
    previous_percent = previous_data.get('fill_percentage', 0)
    current_gallons = current_data.get('gallons', 0)
    
    # Update usage history
    usage_history.append({
        'timestamp': datetime.now(),
        'gallons': current_gallons,
        'fill_percentage': current_percent
    })
    
    # Keep only last 48 hours of usage data
    cutoff_time = datetime.now() - timedelta(hours=48)
    usage_history = [r for r in usage_history if r['timestamp'] > cutoff_time]
    
    # Calculate changes
    percent_change = abs(current_percent - previous_percent)
    is_drop = current_percent < previous_percent
    
    # Determine severity
    severity = get_alert_severity(current_percent, is_drop, percent_change)
    
    # Check if we should send alerts based on different criteria
    should_alert = False
    alert_type = 'change'
    
    # 1. Check for rapid drops
    if is_drop and percent_change >= RAPID_DROP_THRESHOLD:
        should_alert = should_send_alert('rapid_drop', last_alert_time)
        alert_type = 'rapid_drop'
    
    # 2. Check for critical/emergency levels
    elif severity in ['emergency', 'critical']:
        last_time = last_emergency_alert_time if severity == 'emergency' else last_critical_alert_time
        should_alert = should_send_alert(severity, last_time)
        alert_type = f'{severity}_level'
    
    # 3. Check for regular threshold changes
    elif percent_change >= ALERT_THRESHOLD:
        should_alert = should_send_alert('normal', last_alert_time)
        alert_type = 'change'
    
    # 4. Check for low level alerts
    elif current_percent <= LOW_LEVEL_THRESHOLD:
        should_alert = should_send_alert('low', last_alert_time)
        alert_type = 'low_level'
    
    if should_alert:
        # Send alerts
        send_enhanced_alert(current_data, previous_data, percent_change, severity, alert_type)
        
        # Update alert times
        now = datetime.now()
        if severity == 'emergency':
            last_emergency_alert_time = now
        elif severity == 'critical':
            last_critical_alert_time = now
        last_alert_time = now
        
        # Store alert in Firebase
        store_enhanced_alert(current_data, previous_data, percent_change, severity, alert_type)
    
    # Check for predictive alerts
    check_predictive_alerts(current_gallons)
    
    # Check for low battery alert (unchanged)
    battery_voltage = current_data.get('battery_voltage', 0)
    if battery_voltage > 0 and battery_voltage < 11.0:
        if should_send_alert('normal', last_alert_time):
            send_battery_alert(current_data, battery_voltage)
            last_alert_time = datetime.now()
            store_battery_alert(current_data, battery_voltage)

def check_predictive_alerts(current_gallons):
    """Check if predictive alerts should be sent"""
    global last_critical_alert_time
    
    days_remaining = calculate_days_remaining(current_gallons)
    
    if days_remaining is not None and days_remaining <= 1:
        # Send predictive alert if less than 24 hours remaining
        if should_send_alert('critical', last_critical_alert_time):
            send_predictive_alert(current_gallons, days_remaining)
            last_critical_alert_time = datetime.now()

def send_predictive_alert(current_gallons, days_remaining):
    """Send predictive alert for low water estimate"""
    try:
        hours_remaining = days_remaining * 24
        
        # Firebase notification
        message = messaging.Message(
            notification=messaging.Notification(
                title='⚠️ Water Running Low',
                body=f'Estimated {hours_remaining:.1f} hours of water remaining ({current_gallons:.0f} gallons)'
            ),
            data={
                'type': 'predictive',
                'current_gallons': str(current_gallons),
                'days_remaining': str(days_remaining),
                'hours_remaining': str(hours_remaining),
                'timestamp': str(datetime.now().isoformat())
            },
            topic='tank_alerts'
        )
        
        response = messaging.send(message)
        print(f"Predictive alert sent: {response}")
        
        # Email alert
        if ENABLE_EMAIL_ALERTS:
            subject = f"Well Tank - Water Running Low ({hours_remaining:.1f}h remaining)"
            body = f"""
Well Tank Water Alert

Current Status:
- Water Level: {current_gallons:.0f} gallons
- Estimated Time Remaining: {hours_remaining:.1f} hours ({days_remaining:.1f} days)

Based on recent usage patterns, your well tank is running low and may be empty soon.

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            send_email_alert(subject, body)
        
    except Exception as e:
        print(f"Error sending predictive alert: {e}")

def send_enhanced_alert(current_data, previous_data, percent_change, severity, alert_type):
    """Send enhanced alert with severity-based messaging"""
    try:
        current_percent = current_data.get('fill_percentage', 0)
        previous_percent = previous_data.get('fill_percentage', 0)
        current_gallons = current_data.get('gallons', 0)
        
        # Determine alert details based on type and severity
        icons = {
            'emergency': '🚨',
            'critical': '⚠️',
            'low': '📉',
            'rapid_drop': '⬇️',
            'normal': '📊'
        }
        
        titles = {
            'rapid_drop': f"{icons[severity]} Rapid Water Level Drop",
            'emergency_level': f"{icons['emergency']} EMERGENCY - Tank Nearly Empty",
            'critical_level': f"{icons['critical']} CRITICAL - Very Low Water Level",
            'low_level': f"{icons['low']} Low Water Level Warning",
            'change': f"{icons['normal']} Water Level Change"
        }
        
        title = titles.get(alert_type, f"{icons['normal']} Tank Alert")
        
        if current_percent > previous_percent:
            direction = "increased"
        else:
            direction = "decreased"
        
        body = f"Water level {direction} by {percent_change:.1f}% (now {current_percent:.1f}% - {current_gallons:.0f} gallons)"
        
        # Firebase notification
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data={
                'type': alert_type,
                'severity': severity,
                'current_level': str(current_percent),
                'previous_level': str(previous_percent),
                'change': str(percent_change),
                'current_gallons': str(current_gallons),
                'timestamp': str(datetime.now().isoformat())
            },
            topic='tank_alerts'
        )
        
        response = messaging.send(message)
        print(f"Enhanced alert sent ({severity}): {response}")
        
        # Send email for critical/emergency alerts
        if severity in ['emergency', 'critical'] and ENABLE_EMAIL_ALERTS:
            subject = f"Well Tank Alert - {severity.upper()}: {current_percent:.1f}% ({current_gallons:.0f} gallons)"
            email_body = f"""
Well Tank {severity.upper()} Alert

Current Status:
- Water Level: {current_percent:.1f}% ({current_gallons:.0f} gallons)
- Previous Level: {previous_percent:.1f}%
- Change: {percent_change:.1f}% {direction}

Alert Type: {alert_type.replace('_', ' ').title()}
Severity: {severity.upper()}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please check your well tank immediately.
"""
            send_email_alert(subject, email_body)
        
    except Exception as e:
        print(f"Error sending enhanced alert: {e}")

def store_enhanced_alert(current_data, previous_data, percent_change, severity, alert_type):
    """Store enhanced alert data in Firebase Firestore"""
    try:
        alert_data = {
            'timestamp': firestore.SERVER_TIMESTAMP,
            'type': alert_type,
            'severity': severity,
            'current_level': current_data.get('fill_percentage', 0),
            'previous_level': previous_data.get('fill_percentage', 0),
            'percent_change': percent_change,
            'current_gallons': current_data.get('gallons', 0),
            'previous_gallons': previous_data.get('gallons', 0),
            'device_id': current_data.get('device_id', 'unknown'),
            'usage_rate': calculate_usage_rate()
        }
        
        # Add days remaining if available
        days_remaining = calculate_days_remaining(current_data.get('gallons', 0))
        if days_remaining is not None:
            alert_data['days_remaining'] = days_remaining
        
        db.collection('alerts').add(alert_data)
        print(f"Enhanced alert stored in Firestore: {alert_type} - {severity}")
        
    except Exception as e:
        print(f"Error storing enhanced alert: {e}")

def send_alert(current_data, previous_data, percent_change):
    """Send push notification via Firebase"""
    try:
        current_percent = current_data.get('fill_percentage', 0)
        previous_percent = previous_data.get('fill_percentage', 0)
        
        # Determine if level increased or decreased
        if current_percent > previous_percent:
            direction = "increased"
            icon = "📈"
        else:
            direction = "decreased"
            icon = "📉"
        
        message = messaging.Message(
            notification=messaging.Notification(
                title=f"{icon} Tank Water Level Alert",
                body=f"Water level {direction} by {percent_change:.1f}% (now {current_percent:.1f}%)"
            ),
            data={
                'current_level': str(current_percent),
                'previous_level': str(previous_percent),
                'change': str(percent_change),
                'timestamp': str(datetime.now().isoformat())
            },
            topic='tank_alerts'  # You'll need to subscribe devices to this topic
        )
        
        response = messaging.send(message)
        print(f"Alert sent successfully: {response}")
        
    except Exception as e:
        print(f"Error sending alert: {e}")

def store_alert(current_data, previous_data, percent_change):
    """Store alert in Firebase Firestore"""
    try:
        alert_data = {
            'timestamp': firestore.SERVER_TIMESTAMP,
            'current_level': current_data.get('fill_percentage', 0),
            'previous_level': previous_data.get('fill_percentage', 0),
            'percent_change': percent_change,
            'current_gallons': current_data.get('gallons', 0),
            'previous_gallons': previous_data.get('gallons', 0),
            'device_id': current_data.get('device_id', 'unknown')
        }
        
        db.collection('alerts').add(alert_data)
        print("Alert stored in Firestore")
        
    except Exception as e:
        print(f"Error storing alert: {e}")

def send_battery_alert(current_data, battery_voltage):
    """Send battery low push notification via Firebase"""
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title='Low Battery Alert',
                body=f'Well sensor battery is low: {battery_voltage:.1f}V. Please check power source.'
            ),
            data={
                'battery_voltage': str(battery_voltage),
                'gallons': str(current_data.get('gallons', 0)),
                'timestamp': str(datetime.now().isoformat())
            },
            topic='tank_alerts'
        )
        
        response = messaging.send(message)
        print(f'Battery alert sent: {response}')
    except Exception as e:
        print(f'Error sending battery alert: {e}')

def store_battery_alert(current_data, battery_voltage):
    """Store battery alert in Firebase Firestore"""
    try:
        alert_data = {
            'timestamp': firestore.SERVER_TIMESTAMP,
            'type': 'low_battery',
            'battery_voltage': battery_voltage,
            'gallons': current_data.get('gallons', 0),
            'fill_percentage': current_data.get('fill_percentage', 0),
            'device_id': current_data.get('device_id', 'unknown')
        }
        
        db.collection('alerts').add(alert_data)
        print(f"Battery alert stored in Firestore: {battery_voltage:.1f}V")
    except Exception as e:
        print(f"Error storing battery alert: {e}")

def store_reading(data):
    """Store sensor reading in Firebase Firestore"""
    if not firebase_initialized:
        return
    
    try:
        reading_data = {
            'timestamp': firestore.SERVER_TIMESTAMP,
            'distance_cm': data.get('distance_cm', 0),
            'water_level_cm': data.get('water_level_cm', 0),
            'gallons': data.get('gallons', 0),
            'fill_percentage': data.get('fill_percentage', 0),
            'battery_voltage': data.get('battery_voltage', 0),
            'wifi_rssi': data.get('wifi_rssi', 0),
            'device_id': data.get('device_id', 'unknown')
        }
        
        db.collection('readings').add(reading_data)
        
    except Exception as e:
        print(f"Error storing reading: {e}")

def scheduled_reading():
    """Scheduled function to fetch and process sensor data"""
    global last_reading
    
    data = get_esp32_data()
    if data:
        # Check for alerts
        if last_reading:
            check_for_alerts(data, last_reading)
        
        # Store reading
        store_reading(data)
        
        # Update last reading
        last_reading = data
        
        print(f"Scheduled reading completed: {data.get('fill_percentage', 0):.1f}%")

# Schedule readings every 5 minutes
schedule.every(5).minutes.do(scheduled_reading)

def run_scheduler():
    """Run the scheduler in a separate thread"""
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start scheduler thread
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'firebase_connected': firebase_initialized
    })

@app.route('/current')
def get_current_reading():
    """Get current sensor reading"""
    global last_reading
    
    if not last_reading:
        # Try to fetch fresh data if none available
        data = get_esp32_data()
        if data:
            last_reading = data
            store_reading(data)
        else:
            return jsonify({'error': 'No sensor data available'}), 404
    
    return jsonify(last_reading)

@app.route('/history')
def get_history():
    """Get historical readings from Firebase"""
    if not firebase_initialized:
        # Return empty list if Firebase not connected
        return jsonify([])
    
    try:
        # Get last 24 hours of readings
        yesterday = datetime.now() - timedelta(days=1)
        
        readings = db.collection('readings')\
            .where('timestamp', '>=', yesterday)\
            .order_by('timestamp', direction=firestore.Query.DESCENDING)\
            .limit(100)\
            .stream()
        
        history = []
        for reading in readings:
            data = reading.to_dict()
            data['id'] = reading.id
            history.append(data)
        
        return jsonify(history)
        
    except Exception as e:
        print(f"Firebase error: {e}")
        # Return empty list on error
        return jsonify([])

@app.route('/alerts')
def get_alerts():
    """Get recent alerts"""
    if not firebase_initialized:
        # Return empty list if Firebase not connected
        return jsonify([])
    
    try:
        # Get last 7 days of alerts
        week_ago = datetime.now() - timedelta(days=7)
        
        alerts = db.collection('alerts')\
            .where('timestamp', '>=', week_ago)\
            .order_by('timestamp', direction=firestore.Query.DESCENDING)\
            .limit(50)\
            .stream()
        
        alert_list = []
        for alert in alerts:
            data = alert.to_dict()
            data['id'] = alert.id
            alert_list.append(data)
        
        return jsonify(alert_list)
        
    except Exception as e:
        print(f"Firebase error: {e}")
        # Return empty list on error
        return jsonify([])

@app.route('/force-reading')
def force_reading():
    """Force a new reading from ESP32"""
    try:
        # Trigger new reading on ESP32
        url = f"http://{ESP32_IP}:{ESP32_PORT}/reading"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Wait a moment for the reading to complete
        time.sleep(2)
        
        # Get the updated data
        data = get_esp32_data()
        if data:
            global last_reading
            if last_reading:
                check_for_alerts(data, last_reading)
            store_reading(data)
            last_reading = data
            
            return jsonify({
                'success': True,
                'data': data
            })
        else:
            return jsonify({'error': 'Failed to get updated reading'}), 500
            
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to trigger reading: {str(e)}'}), 500

@app.route('/tank-data', methods=['POST'])
def receive_tank_data():
    """Receive tank data from ESP32"""
    global last_reading
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
        
        # Validate required fields
        required_fields = ['device_id', 'distance_cm', 'water_level_cm', 'gallons', 'fill_percentage']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Check for alerts
        if last_reading:
            check_for_alerts(data, last_reading)
        
        # Store reading
        store_reading(data)
        
        # Update last reading
        last_reading = data
        
        print(f"Received tank data: {data.get('fill_percentage', 0):.1f}%")
        
        return jsonify({
            'success': True,
            'message': 'Data received successfully'
        })
        
    except Exception as e:
        print(f"Error processing tank data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/config')
def get_config():
    """Get current configuration"""
    current_gallons = last_reading.get('gallons', 0) if last_reading else 0
    usage_rate = calculate_usage_rate()
    days_remaining = calculate_days_remaining(current_gallons)
    
    return jsonify({
        'esp32_ip': ESP32_IP,
        'alert_threshold': ALERT_THRESHOLD,
        'alert_cooldown': ALERT_COOLDOWN,
        'firebase_connected': firebase_initialized,
        'enhanced_alerts': {
            'low_level_threshold': LOW_LEVEL_THRESHOLD,
            'critical_level_threshold': CRITICAL_LEVEL_THRESHOLD,
            'emergency_level_threshold': EMERGENCY_LEVEL_THRESHOLD,
            'rapid_drop_threshold': RAPID_DROP_THRESHOLD,
            'email_alerts_enabled': ENABLE_EMAIL_ALERTS
        },
        'usage_stats': {
            'current_usage_rate_gph': usage_rate,
            'days_remaining': days_remaining
        }
    })

@app.route('/test-push-notification', methods=['POST'])
def test_push_notification():
    """Send a test push notification"""
    if not firebase_initialized:
        return jsonify({'error': 'Firebase not initialized'}), 500
    
    try:
        # Create a test message
        message = messaging.Message(
            notification=messaging.Notification(
                title='Test Alert - Well Tank Monitor',
                body='This is a test push notification from your well tank monitoring system.'
            ),
            data={
                'type': 'test',
                'timestamp': datetime.now().isoformat(),
                'severity': 'info'
            },
            topic='well_tank_alerts'  # Send to all subscribers
        )
        
        # Send the message
        response = messaging.send(message)
        
        return jsonify({
            'success': True,
            'message': 'Test push notification sent successfully',
            'message_id': response
        })
        
    except Exception as e:
        print(f"Error sending test push notification: {e}")
        return jsonify({'error': f'Failed to send test notification: {str(e)}'}), 500

@app.route('/test-email', methods=['POST'])
def test_email():
    """Send a test email alert"""
    if not ENABLE_EMAIL_ALERTS:
        return jsonify({'error': 'Email alerts are disabled'}), 400
    
    if not ALERT_EMAIL:
        return jsonify({'error': 'No alert email configured'}), 400
    
    try:
        subject = 'Test Alert - Well Tank Monitor'
        body = f"""
Test Email Alert

This is a test email from your well tank monitoring system.

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
System Status: Operational
Current Water Level: {last_reading.get('fill_percentage', 0):.1f}% (if available)

This email confirms that your email alert system is working correctly.

---
Well Tank Monitor System
        """
        
        success = send_email_alert(subject, body)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Test email sent successfully'
            })
        else:
            return jsonify({'error': 'Failed to send test email'}), 500
            
    except Exception as e:
        print(f"Error sending test email: {e}")
        return jsonify({'error': f'Failed to send test email: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False) 