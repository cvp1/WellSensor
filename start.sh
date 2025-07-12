#!/bin/bash

# Well Tank Monitor Startup Script
# This script helps you deploy the application

set -e

echo "🚰 Well Tank Monitor - Deployment Script"
echo "========================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    if [ -f "env.example" ]; then
        cp env.example .env
        echo "✅ Created .env file from template"
        echo "📝 Please edit .env file with your configuration before continuing"
        echo "   - Set your ESP32 IP address"
        echo "   - Configure Firebase credentials"
        echo "   - Adjust alert settings"
        read -p "Press Enter when you've configured .env file..."
    else
        echo "❌ env.example file not found. Please create .env file manually."
        exit 1
    fi
fi

# Generate PWA icons if they don't exist
if [ ! -d "frontend/icons" ]; then
    echo "🎨 Generating PWA icons..."
    python3 generate_icons.py
fi

# Build and start the application
echo "🐳 Building and starting Docker containers..."
docker-compose up -d --build

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "✅ Application started successfully!"
    echo ""
    echo "🌐 Access your application:"
    echo "   Frontend: http://localhost:8091"
    echo "   Backend API: http://localhost:8090"
    echo ""
    echo "📱 PWA Features:"
    echo "   - Install on mobile/desktop for app-like experience"
    echo "   - Works offline with cached data"
    echo "   - Push notifications for alerts"
    echo ""
    echo "📊 Monitoring:"
    echo "   - View logs: docker-compose logs -f"
    echo "   - Stop app: docker-compose down"
    echo "   - Restart: docker-compose restart"
    echo ""
    echo "🔧 Configuration:"
    echo "   - Edit .env file to change settings"
    echo "   - Restart with: docker-compose restart"
    echo ""
    echo "🎯 Next Steps:"
    echo "   1. Configure your ESP32 with the provided code"
    echo "   2. Set up Firebase project and update .env"
    echo "   3. Test the sensor connection"
    echo "   4. Customize alerts and thresholds"
else
    echo "❌ Failed to start application. Check logs:"
    docker-compose logs
    exit 1
fi 