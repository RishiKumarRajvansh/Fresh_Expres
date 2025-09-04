#!/usr/bin/env python3
"""
Production Deployment Script
Automates the deployment process for the Fresh Express platform
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deployment.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_command(command, check=True):
    """Run a shell command and return the result"""
    logger.info(f"Running: {command}")
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True,
            check=check
        )
        if result.stdout:
            logger.info(f"Output: {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        logger.error(f"Error output: {e.stderr}")
        if check:
            raise
        return e

def check_requirements():
    """Check if all requirements are met"""
    logger.info("Checking deployment requirements...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        logger.error("Python 3.8 or higher is required")
        sys.exit(1)
    
    # Check if Django is installed
    try:
        import django
        logger.info(f"Django version: {django.__version__}")
    except ImportError:
        logger.error("Django is not installed")
        sys.exit(1)
    
    # Check if required directories exist
    required_dirs = ['static', 'media', 'templates']
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            logger.warning(f"Creating missing directory: {dir_name}")
            Path(dir_name).mkdir(parents=True, exist_ok=True)
    
    logger.info("Requirements check completed")

def install_dependencies():
    """Install Python dependencies"""
    logger.info("Installing Python dependencies...")
    
    # Check if requirements.txt exists
    if Path('requirements.txt').exists():
        run_command("pip install -r requirements.txt")
    else:
        logger.warning("requirements.txt not found, installing core dependencies...")
        dependencies = [
            "Django>=5.0,<6.0",
            "whitenoise>=6.0",
            "gunicorn>=20.0",
            "psycopg2-binary>=2.9",
            "Pillow>=9.0",
            "python-dotenv>=0.19"
        ]
        for dep in dependencies:
            run_command(f"pip install {dep}")
    
    logger.info("Dependencies installation completed")

def setup_database():
    """Setup and migrate database"""
    logger.info("Setting up database...")
    
    # Set production settings
    os.environ['DJANGO_SETTINGS_MODULE'] = 'meat_seafood.settings_production'
    
    # Create migrations
    logger.info("Creating migrations...")
    run_command("python manage.py makemigrations")
    
    # Apply migrations
    logger.info("Applying migrations...")
    run_command("python manage.py migrate")
    
    # Create superuser if it doesn't exist
    logger.info("Creating superuser...")
    create_superuser_command = """
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@yourdomain.com', 'admin123')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
"""
    
    run_command(f'python manage.py shell -c "{create_superuser_command}"')
    
    logger.info("Database setup completed")

def collect_static_files():
    """Collect static files for production"""
    logger.info("Collecting static files...")
    
    os.environ['DJANGO_SETTINGS_MODULE'] = 'meat_seafood.settings_production'
    
    # Create staticfiles directory
    Path('staticfiles').mkdir(exist_ok=True)
    
    # Collect static files
    run_command("python manage.py collectstatic --noinput")
    
    logger.info("Static files collection completed")

def setup_logging():
    """Setup logging directories"""
    logger.info("Setting up logging...")
    
    # Create logs directory
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    
    # Create log files
    (logs_dir / 'django.log').touch()
    (logs_dir / 'django_errors.log').touch()
    
    logger.info("Logging setup completed")

def create_environment_file():
    """Create .env file template"""
    logger.info("Creating environment file template...")
    
    env_content = """
# Production Environment Variables
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database Configuration
DB_NAME=meat_seafood_prod
DB_USER=postgres
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# Payment Gateway
RAZORPAY_KEY_ID=your-razorpay-key-id
RAZORPAY_KEY_SECRET=your-razorpay-key-secret

# Google Maps API
GOOGLE_MAPS_API_KEY=your-google-maps-api-key

# SMS Configuration (Twilio)
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_FROM_NUMBER=+1234567890

# Redis (optional)
REDIS_URL=redis://localhost:6379/1

# Use SQLite (for smaller deployments)
USE_SQLITE=False
"""
    
    env_file = Path('.env')
    if not env_file.exists():
        with open(env_file, 'w') as f:
            f.write(env_content.strip())
        logger.info("Created .env template file")
    else:
        logger.info(".env file already exists")

def create_nginx_config():
    """Create Nginx configuration template"""
    logger.info("Creating Nginx configuration template...")
    
    nginx_config = """
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL Configuration (add your SSL certificates)
    ssl_certificate /path/to/your/certificate.pem;
    ssl_certificate_key /path/to/your/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Static files
    location /static/ {
        alias /path/to/your/project/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Media files
    location /media/ {
        alias /path/to/your/project/media/;
        expires 30d;
        add_header Cache-Control "public";
    }
    
    # Django application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
}
"""
    
    nginx_file = Path('nginx.conf')
    with open(nginx_file, 'w') as f:
        f.write(nginx_config.strip())
    
    logger.info("Created nginx.conf template")

def create_systemd_service():
    """Create systemd service file for Gunicorn"""
    logger.info("Creating systemd service template...")
    
    service_content = """
[Unit]
Description=Fresh Express Platform
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
RuntimeDirectory=gunicorn
WorkingDirectory=/path/to/your/project
ExecStart=/path/to/your/venv/bin/gunicorn --worker-class=gevent --workers=3 --bind=127.0.0.1:8000 --timeout=300 --max-requests=1000 --max-requests-jitter=100 meat_seafood.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5s

Environment=DJANGO_SETTINGS_MODULE=meat_seafood.settings_production

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path('meat-seafood.service')
    with open(service_file, 'w') as f:
        f.write(service_content.strip())
    
    logger.info("Created systemd service template")

def create_deployment_checklist():
    """Create deployment checklist"""
    logger.info("Creating deployment checklist...")
    
    checklist = """
# Production Deployment Checklist

## Pre-deployment:
- [ ] Update .env file with production values
- [ ] Set up production database (PostgreSQL recommended)
- [ ] Configure SSL certificates
- [ ] Set up domain DNS records
- [ ] Configure email server (SMTP)
- [ ] Set up payment gateway accounts
- [ ] Configure Google Maps API
- [ ] Set up SMS service (Twilio)

## Deployment Steps:
- [ ] Run deployment script: python deploy.py
- [ ] Copy nginx.conf to /etc/nginx/sites-available/
- [ ] Enable Nginx site: sudo ln -s /etc/nginx/sites-available/meat-seafood /etc/nginx/sites-enabled/
- [ ] Copy systemd service: sudo cp meat-seafood.service /etc/systemd/system/
- [ ] Start services: sudo systemctl start meat-seafood && sudo systemctl enable meat-seafood
- [ ] Reload Nginx: sudo nginx -t && sudo systemctl reload nginx

## Post-deployment:
- [ ] Test website functionality
- [ ] Test order placement and delivery assignment
- [ ] Test contact form email delivery
- [ ] Test agent dashboard and order management
- [ ] Set up monitoring and logging
- [ ] Configure automated backups
- [ ] Set up SSL monitoring
- [ ] Create admin accounts for store owners
- [ ] Test payment processing

## Security:
- [ ] Update all default passwords
- [ ] Configure firewall rules
- [ ] Set up fail2ban
- [ ] Enable automatic security updates
- [ ] Configure log rotation
- [ ] Set up monitoring alerts

## Performance:
- [ ] Configure Redis for caching (optional)
- [ ] Set up CDN for static files (optional)
- [ ] Configure database connection pooling
- [ ] Set up database backups
- [ ] Monitor server resources

## Testing:
- [ ] Load test the application
- [ ] Test all user workflows
- [ ] Test admin functionality
- [ ] Test error handling
- [ ] Test backup and recovery procedures
"""
    
    checklist_file = Path('DEPLOYMENT_CHECKLIST.md')
    with open(checklist_file, 'w') as f:
        f.write(checklist.strip())
    
    logger.info("Created deployment checklist")

def main():
    """Main deployment function"""
    logger.info("Starting production deployment...")
    
    try:
        # Run deployment steps
        check_requirements()
        install_dependencies()
        setup_database()
        collect_static_files()
        setup_logging()
        create_environment_file()
        create_nginx_config()
        create_systemd_service()
        create_deployment_checklist()
        
        logger.info("Deployment completed successfully!")
        logger.info("Please review the DEPLOYMENT_CHECKLIST.md for next steps.")
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
