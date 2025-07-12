# Well Tank Monitor

A Progressive Web App (PWA) with Python backend for monitoring well tank water levels using ESP32 sensors with Firebase integration and Docker deployment.

## Features

- **Real-time Monitoring**: Live water level tracking with visual tank representation
- **Alert System**: Firebase-powered notifications for significant water level changes
- **Historical Data**: Chart visualization of water level trends over time
- **Progressive Web App**: Installable on mobile and desktop devices
- **Offline Support**: Works offline with cached data
- **Docker Deployment**: Easy containerized deployment
- **Firebase Integration**: Cloud storage and push notifications

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ESP32 Sensor  │    │  Python Backend │    │  PWA Frontend   │
│                 │    │                 │    │                 │
│ • Ultrasonic    │───▶│ • Flask API     │───▶│ • React-like UI │
│ • WiFi          │    │ • Firebase      │    │ • Charts        │
│ • Web Server    │    │ • Alerts        │    │ • Offline Cache │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │    Firebase     │
                       │                 │
                       │ • Firestore     │
                       │ • Cloud Messaging│
                       │ • Authentication│
                       └─────────────────┘
```

## Prerequisites

- Docker and Docker Compose
- ESP32 development board with ultrasonic sensor
- Firebase project
- Python 3.11+ (for local development)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd WellSensor
```

### 2. Configure Environment Variables

Copy the example environment file and configure it:

```bash
cp env.example .env
```

Edit `.env` with your configuration:

```env
# ESP32 Configuration
ESP32_IP=192.168.86.90
ESP32_PORT=80

# Firebase Configuration
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY_ID=your-private-key-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYour private key here\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project-id.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=your-client-id
FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token
FIREBASE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
FIREBASE_CLIENT_X509_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-xxxxx%40your-project-id.iam.gserviceaccount.com

# Alert Configuration
ALERT_THRESHOLD_PERCENT=10
ALERT_COOLDOWN_MINUTES=30

# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
```

### 3. Setup Firebase

1. Create a Firebase project at [Firebase Console](https://console.firebase.google.com/)
2. Enable Firestore Database
3. Enable Cloud Messaging
4. Create a service account and download the JSON key
5. Update the Firebase configuration in `.env`

### 4. Deploy with Docker

```bash
# Build and start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

The application will be available at:
- Frontend: http://localhost:8091
- Backend API: http://localhost:8090

## ESP32 Setup

### Hardware Requirements

- ESP32 development board
- HC-SR04 ultrasonic sensor
- Power supply (12V recommended)
- Enclosure for outdoor use

### Wiring

```
ESP32 Pin 5  ──► HC-SR04 TRIG
ESP32 Pin 18 ──► HC-SR04 ECHO
ESP32 3.3V   ──► HC-SR04 VCC
ESP32 GND    ──► HC-SR04 GND
```

### Configuration

Update the ESP32 code (`WellSensor.cpp`) with your settings:

```cpp
// WiFi Configuration
const char* ssid = "YourWiFiSSID";
const char* password = "YourWiFiPassword";

// Tank Configuration
#define TANK_HEIGHT_CM 183    // Your tank height in cm
#define TANK_CAPACITY_GALLONS 1550  // Your tank capacity
#define SENSOR_HEIGHT_CM 200  // Height of sensor above tank bottom
```

### Upload to ESP32

1. Install Arduino IDE with ESP32 board support
2. Install required libraries:
   - WiFi
   - HTTPClient
   - WebServer
   - ArduinoJson
   - NewPing
3. Upload the code to your ESP32
4. Note the IP address assigned to the ESP32

## API Endpoints

### Backend API (Flask)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/current` | GET | Get current sensor reading |
| `/history` | GET | Get historical readings |
| `/alerts` | GET | Get recent alerts |
| `/force-reading` | GET | Force new reading from ESP32 |
| `/config` | GET | Get system configuration |

### ESP32 API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Get current sensor data (JSON) |
| `/reading` | GET | Trigger new sensor reading |
| `/` | GET | Basic web interface |

## Features in Detail

### Real-time Monitoring

- Automatic data collection every 5 minutes
- Visual tank representation with water level
- Real-time updates via WebSocket-like polling
- Responsive design for mobile and desktop

### Alert System

- Configurable threshold for water level changes
- Cooldown period to prevent spam alerts
- Firebase Cloud Messaging for push notifications
- Alert history stored in Firestore

### Historical Data

- Chart visualization using Chart.js
- 24-hour reading history
- Trend analysis
- Export capabilities

### Progressive Web App

- Installable on mobile and desktop
- Offline functionality with service worker
- App-like experience
- Push notifications

## Development

### Local Development Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run backend
cd backend
python app.py

# Serve frontend (in another terminal)
cd frontend
python -m http.server 8000
```

### Project Structure

```
WellSensor/
├── backend/
│   ├── __init__.py
│   └── app.py              # Flask application
├── frontend/
│   ├── index.html          # Main HTML file
│   ├── styles.css          # CSS styles
│   ├── app.js              # JavaScript application
│   ├── sw.js               # Service worker
│   └── manifest.json       # PWA manifest
├── WellSensor.cpp          # ESP32 code
├── requirements.txt        # Python dependencies
├── Dockerfile              # Backend container
├── docker-compose.yml      # Multi-container setup
├── nginx.conf              # Nginx configuration
├── env.example             # Environment template
└── README.md               # This file
```

## Configuration

### Alert Settings

- `ALERT_THRESHOLD_PERCENT`: Minimum percentage change to trigger alert (default: 10%)
- `ALERT_COOLDOWN_MINUTES`: Time between alerts (default: 30 minutes)

### ESP32 Settings

- `ESP32_IP`: IP address of your ESP32 device
- `ESP32_PORT`: Port for ESP32 web server (default: 80)

### Firebase Settings

All Firebase configuration is handled through environment variables. See the `.env.example` file for required fields.

## Troubleshooting

### Common Issues

1. **ESP32 not connecting**
   - Check WiFi credentials
   - Verify ESP32 IP address
   - Check network connectivity

2. **Firebase connection failed**
   - Verify service account credentials
   - Check project ID
   - Ensure Firestore is enabled

3. **Docker build fails**
   - Check Docker and Docker Compose versions
   - Verify all files are present
   - Check network connectivity for package downloads

4. **PWA not installing**
   - Ensure HTTPS is enabled (required for PWA)
   - Check manifest.json configuration
   - Verify service worker registration

### Logs

```bash
# View backend logs
docker-compose logs backend

# View frontend logs
docker-compose logs frontend

# View all logs
docker-compose logs -f
```

## Security Considerations

- Use HTTPS in production
- Secure Firebase service account keys
- Implement proper authentication if needed
- Regular security updates
- Network isolation for ESP32

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review Firebase documentation
- Consult ESP32 documentation

## Roadmap

- [ ] User authentication
- [ ] Multiple tank support
- [ ] Advanced analytics
- [ ] Mobile app versions
- [ ] Integration with smart home systems
- [ ] Weather data integration
- [ ] Predictive maintenance alerts 