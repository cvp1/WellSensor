import os
import json
import requests
import schedule
import time
import threading
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

# Global variables
last_reading = None
last_alert_time = None
alert_history = []

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

def check_for_alerts(current_data, previous_data):
    """Check for significant changes and send alerts"""
    global last_alert_time
    
    if not previous_data or not firebase_initialized:
        return
    
    current_percent = current_data.get('fill_percentage', 0)
    previous_percent = previous_data.get('fill_percentage', 0)
    
    # Calculate percentage change
    percent_change = abs(current_percent - previous_percent)
    
    # Check if change exceeds threshold
    if percent_change >= ALERT_THRESHOLD:
        # Check cooldown period
        if (last_alert_time is None or 
            datetime.now() - last_alert_time > timedelta(minutes=ALERT_COOLDOWN)):
            
            # Send alert
            send_alert(current_data, previous_data, percent_change)
            last_alert_time = datetime.now()
            
            # Store alert in Firebase
            store_alert(current_data, previous_data, percent_change)
    
    # Check for low battery alert
    battery_voltage = current_data.get('battery_voltage', 0)
    if battery_voltage > 0 and battery_voltage < 11.0:  # Alert if battery below 11V
        # Check cooldown period for battery alerts
        if (last_alert_time is None or 
            datetime.now() - last_alert_time > timedelta(minutes=ALERT_COOLDOWN)):
            
            # Send battery alert
            send_battery_alert(current_data, battery_voltage)
            last_alert_time = datetime.now()
            
            # Store battery alert in Firebase
            store_battery_alert(current_data, battery_voltage)

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
    return jsonify({
        'esp32_ip': ESP32_IP,
        'alert_threshold': ALERT_THRESHOLD,
        'alert_cooldown': ALERT_COOLDOWN,
        'firebase_connected': firebase_initialized
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False) 