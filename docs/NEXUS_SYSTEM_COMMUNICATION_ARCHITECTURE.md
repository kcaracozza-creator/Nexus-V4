# NEXUS Universal Collectibles System
## Complete System Communication Architecture
### Version 2.0 - January 22, 2026

---

## Network Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     NEXUS NETWORK TOPOLOGY                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Pi 5       │    │   Pi 2       │    │   ESP32      │      │
│  │   "Scarf"    │◄──►│  "Lionelle"  │◄──►│   Hub        │      │
│  │ 192.168.1.172│    │192.168.1.174 │    │192.168.1.xxx │      │
│  │              │    │              │    │              │      │
│  │ ┌──────────┐ │    │ ┌──────────┐ │    │ ┌──────────┐ │      │
│  │ │ Camera   │ │    │ │Processing│ │    │ │Hardware  │ │      │
│  │ │ Control  │ │    │ │ Server   │ │    │ │ Control  │ │      │
│  │ │ Capture  │ │    │ │ OCR/AI   │ │    │ │ Motors   │ │      │
│  │ └──────────┘ │    │ └──────────┘ │    │ └──────────┘ │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Communication Matrix

| Source | Destination | Protocol | Port/Pin | Purpose | Status |
|--------|-------------|----------|----------|---------|--------|
| **Pi 5 "Scarf"** | **Pi 2 "Lionelle"** | HTTP/TCP | 5001 | Processing requests | ✅ Active |
| **Pi 2 "Lionelle"** | **Pi 5 "Scarf"** | HTTP/TCP | 5000 | Command responses | ✅ Active |
| **ESP32 Hub** | **Pi 5 "Scarf"** | Serial/WiFi | UART/WiFi | Hardware status | ✅ Active |
| **Pi 5 "Scarf"** | **ESP32 Hub** | Serial/WiFi | UART/WiFi | Control commands | ✅ Active |
| **ESP32** | **ZK SMC02** | Digital GPIO | 18,19 | Stepper control | ✅ Active |
| **ESP32** | **PCA9685** | I2C | 21,22 | Servo control | ✅ Active |
| **ESP32** | **LED Matrix** | Digital PWM | Various | Lighting control | ✅ Active |
| **Windows Dev** | **Pi Network** | SSH/HTTP | 22,5000,5001 | Development access | ✅ Active |

---

## Hardware Communication Protocols

### ESP32 GPIO Pin Assignment

```
┌─────────────────────────────────────────────────────────────┐
│                    ESP32 PINOUT MAP                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  GPIO 14 ──► NeoPixel Ring 16 LED Display                 │
│  GPIO 18 ──► ZK SMC02 CW (Clockwise stepper pulses)       │
│  GPIO 19 ──► ZK SMC02 CCW (Counter-clockwise pulses)      │
│  GPIO 21 ──► PCA9685 SDA (I2C data for servo control)     │
│  GPIO 22 ──► PCA9685 SCL (I2C clock for servo control)    │
│  GPIO 25 ──► Camera Trigger (DSLR capture signal)         │
│  GPIO 26 ──► Status LED (System status indicator)         │
│  GPIO 27 ──► Display Box WS2812 17 LED (Lightbox)         │
│  GND     ──► Common ground (All systems)                  │
│  3V3     ──► Logic power (I2C, sensors)                   │
│  5V      ──► Component power (Relays, LEDs)               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Stepper Motor Control (ZK SMC02)

```python
# ESP32 → ZK SMC02 Communication Protocol
class StepperController:
    def __init__(self):
        self.cw_pin = 18      # Clockwise pulse pin
        self.ccw_pin = 19     # Counter-clockwise pulse pin
        self.pulse_width = 50  # Microseconds
        
    def step_clockwise(self, steps):
        """Send CW pulses to ZK SMC02"""
        for _ in range(steps):
            gpio.write(self.cw_pin, HIGH)
            delay_microseconds(self.pulse_width)
            gpio.write(self.cw_pin, LOW)
            delay_microseconds(self.pulse_width)
            
    def step_counter_clockwise(self, steps):
        """Send CCW pulses to ZK SMC02"""
        for _ in range(steps):
            gpio.write(self.ccw_pin, HIGH)
            delay_microseconds(self.pulse_width)
            gpio.write(self.ccw_pin, LOW)
            delay_microseconds(self.pulse_width)
```

### Servo Control (PCA9685)

```python
# ESP32 → PCA9685 I2C Communication
class ServoController:
    def __init__(self):
        self.i2c_address = 0x40  # PCA9685 default address
        self.frequency = 50      # 50Hz for servo control
        
    def set_servo_angle(self, channel, angle):
        """Set servo position via I2C"""
        pulse_length = self.angle_to_pulse(angle)
        self.write_pwm(channel, 0, pulse_length)
        
    def write_pwm(self, channel, on_time, off_time):
        """Write PWM values to PCA9685 register"""
        i2c.write_register(self.i2c_address, 
                          0x06 + 4 * channel, 
                          [on_time & 0xFF, on_time >> 8, 
                           off_time & 0xFF, off_time >> 8])
```

### LED Matrix Control

```python
# ESP32 → LED Matrix Communication
class LEDController:
    def __init__(self):
        self.data_pin = 23
        self.num_leds = 60
        self.led_strip = NeoPixel(self.data_pin, self.num_leds)
        
    def set_lighting_mode(self, mode):
        """Control scanning lighting"""
        modes = {
            'WHITE': (255, 255, 255),
            'WARM': (255, 200, 150),
            'COOL': (200, 220, 255),
            'OFF': (0, 0, 0)
        }
        color = modes.get(mode, (255, 255, 255))
        self.led_strip.fill(color)
        self.led_strip.write()
```

---

## Network Communication Protocols

### Pi 5 "Scarf" → Pi 2 "Lionelle" (Processing Requests)

```python
# HTTP API Communication
BASE_URL = "http://192.168.1.174:5001"

class ProcessingClient:
    def submit_scan_job(self, image_path, scan_type):
        """Submit image for OCR/AI processing"""
        data = {
            'image_path': image_path,
            'scan_type': scan_type,  # 'card', 'coin', 'stamp', etc.
            'timestamp': datetime.utcnow().isoformat(),
            'scanner_id': 'nexus_scarf_001'
        }
        response = requests.post(f"{BASE_URL}/api/process", json=data)
        return response.json()
        
    def get_processing_status(self, job_id):
        """Check processing status"""
        response = requests.get(f"{BASE_URL}/api/status/{job_id}")
        return response.json()
        
    def get_recognition_results(self, job_id):
        """Retrieve processing results"""
        response = requests.get(f"{BASE_URL}/api/results/{job_id}")
        return response.json()
```

### Pi 2 "Lionelle" Processing Server API

```python
# Flask API Endpoints
@app.route('/api/process', methods=['POST'])
def process_image():
    """Process submitted image"""
    data = request.json
    job_id = generate_job_id()
    
    # Queue processing job
    processing_queue.put({
        'job_id': job_id,
        'image_path': data['image_path'],
        'scan_type': data['scan_type'],
        'timestamp': data['timestamp']
    })
    
    return {'job_id': job_id, 'status': 'queued'}

@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get job processing status"""
    status = job_tracker.get(job_id, 'unknown')
    return {'job_id': job_id, 'status': status}

@app.route('/api/results/<job_id>')
def get_results(job_id):
    """Return processing results"""
    results = result_store.get(job_id)
    return {'job_id': job_id, 'results': results}
```

### ESP32 ↔ Pi 5 Communication

```python
# Serial/WiFi Communication Protocol
class HardwareController:
    def __init__(self):
        self.serial_port = "/dev/ttyUSB0"
        self.baud_rate = 9600
        self.wifi_ip = "192.168.1.xxx"  # ESP32 IP when assigned
        
    def send_command(self, command):
        """Send command to ESP32"""
        if self.serial_port:
            self.serial_send(command)
        else:
            self.wifi_send(command)
            
    def serial_send(self, command):
        """Serial communication"""
        with serial.Serial(self.serial_port, self.baud_rate) as ser:
            ser.write(f"{command}\n".encode())
            response = ser.readline().decode().strip()
            return response
            
    def wifi_send(self, command):
        """WiFi communication"""
        response = requests.post(f"http://{self.wifi_ip}/command", 
                               json={'cmd': command})
        return response.json()
```

---

## Command Protocol Specifications

### ESP32 Command Set

```
# Stepper Motor Commands
STEP_CW [steps]        - Step clockwise N steps
STEP_CCW [steps]       - Step counter-clockwise N steps  
GOTO [position]        - Move to absolute position
HOME                   - Return to home position
GET_POS                - Report current position

# Servo Commands  
SERVO [channel] [angle] - Set servo angle (0-180 degrees)
SERVO_HOME [channel]   - Return servo to home position
SERVO_OFF [channel]    - Disable servo power

# LED Commands
LED_WHITE              - Set white lighting
LED_WARM               - Set warm white lighting  
LED_COOL               - Set cool white lighting
LED_RGB [r] [g] [b]    - Set custom RGB color
LED_OFF                - Turn off all LEDs

# System Commands
STATUS                 - Report all system status
EMERGENCY_STOP         - Stop all motion immediately
RESET                  - Reset all systems to default
PING                   - Connectivity test
```

### Response Codes

```
# Success Responses
OK [data]              - Command successful with optional data
DONE                   - Motion completed
HOME_COMPLETE          - Homing sequence finished
STATUS_OK              - System operating normally

# Error Responses  
ERROR_INVALID_CMD      - Unknown command
ERROR_INVALID_PARAM    - Invalid parameter value
ERROR_HARDWARE         - Hardware fault detected
ERROR_SAFETY           - Safety system triggered
ERROR_BUSY             - System busy, retry later

# Status Responses
POS [x] [y] [z]        - Current position coordinates  
TEMP [celsius]         - System temperature
VOLTAGE [volts]        - Power supply voltage
```

---

## Database Communication

### SQLite Database Connections

```python
# Multi-database architecture
DATABASES = {
    'library': 'data/library/nexus_library.db',
    'scryfall': 'data/SCRYFALL_CACHE/scryfall_cache.db', 
    'sales': 'data/marketplace/sales_history.db',
    'analytics': 'data/business/shop_analytics.db',
    'ai_training': 'data/ai/training_data.db'
}

class DatabaseManager:
    def __init__(self):
        self.connections = {}
        for name, path in DATABASES.items():
            self.connections[name] = sqlite3.connect(path)
            
    def execute_query(self, db_name, query, params=None):
        """Execute query on specified database"""
        conn = self.connections[db_name]
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchall()
```

### API Integration Communications

```python
# External API Communication
class APIIntegrations:
    def __init__(self):
        self.scryfall_base = "https://api.scryfall.com"
        self.tcgplayer_base = "https://api.tcgplayer.com"
        self.pokemon_base = "https://api.pokemontcg.io"
        
    def scryfall_card_lookup(self, card_name):
        """Scryfall API card lookup"""
        url = f"{self.scryfall_base}/cards/named"
        params = {'fuzzy': card_name}
        response = requests.get(url, params=params)
        return response.json()
        
    def tcgplayer_price_lookup(self, product_id):
        """TCGPlayer pricing API"""
        url = f"{self.tcgplayer_base}/pricing/product/{product_id}"
        headers = {'Authorization': f'Bearer {self.tcg_token}'}
        response = requests.get(url, headers=headers)
        return response.json()
```

---

## Real-time Communication Flows

### Scanning Workflow Communication

```
1. User initiates scan via NEXUS V2 UI
   ↓
2. UI → Pi 5 "Scarf": Start scan sequence
   ↓  
3. Pi 5 → ESP32: Position stepper motor
   ↓
4. ESP32 → ZK SMC02: STEP_CW [steps] 
   ↓
5. ESP32 → PCA9685: SERVO [0] [45] (position arm)
   ↓
6. ESP32 → LED Matrix: LED_WHITE (optimal lighting)
   ↓
7. Pi 5 → Camera: Capture high-res image
   ↓
8. Pi 5 → Pi 2 "Lionelle": Submit for processing
   ↓
9. Pi 2 → OCR Engine: Extract text regions
   ↓
10. Pi 2 → AI Recognition: Identify card/item
    ↓
11. Pi 2 → Database: Store results
    ↓
12. Pi 2 → Pi 5: Return recognition data
    ↓
13. Pi 5 → UI: Display results to user
    ↓
14. ESP32: Return to home position
```

### Batch Scanning Communication

```
For each item in batch:
  ├─ ESP32 → Stepper: Move to next position
  ├─ ESP32 → Servo: Position scanning arm  
  ├─ Pi 5 → Camera: Capture image
  ├─ Pi 5 → Pi 2: Process image
  └─ Pi 2 → Database: Store results

Progress updates: Pi 5 → UI every 5 items
Error handling: Any component → UI immediate notification
```

---

## Network Configuration

### IP Address Assignments

```
# Static IP Configuration
Pi 5 "Scarf"     : 192.168.1.172 (Scanner control)
Pi 2 "Lionelle"  : 192.168.1.174 (Processing server)  
ESP32 Hub        : 192.168.1.175 (Hardware control)
Windows Dev      : 192.168.1.xxx (Development machine)
Router Gateway   : 192.168.1.1   (Network gateway)
```

### Port Assignments

```
# Service Ports
Pi 5 Control API    : 5000 (Scanner control interface)
Pi 2 Processing API : 5001 (OCR/AI processing service)
SSH Access         : 22   (Remote terminal access)
Database Sync      : 3306 (MySQL/MariaDB if upgraded)
Monitoring         : 8080 (System monitoring dashboard)
ESP32 Web Interface: 80   (Hardware status/control)
```

### Firewall Rules

```bash
# UFW Configuration (both Pi systems)
ufw allow 22/tcp    # SSH
ufw allow 5000/tcp  # Scanner API  
ufw allow 5001/tcp  # Processing API
ufw allow from 192.168.1.0/24  # Local network only
ufw enable
```

---

## Error Handling & Recovery

### Communication Timeouts

```python
# Timeout Configuration
TIMEOUTS = {
    'esp32_response': 5,      # ESP32 command response
    'processing_job': 300,    # Image processing timeout
    'database_query': 30,     # Database operation timeout
    'api_request': 10,        # External API timeout
    'network_ping': 2         # Network connectivity test
}

class CommunicationManager:
    def send_with_timeout(self, target, command, timeout):
        """Send command with timeout and retry logic"""
        for attempt in range(3):  # 3 retry attempts
            try:
                response = self.send_command(target, command, timeout)
                return response
            except TimeoutError:
                if attempt == 2:  # Last attempt
                    raise CommunicationError(f"Failed to reach {target}")
                time.sleep(1)  # Wait before retry
```

### Backup Communication Paths

```python
# Fallback Communication Routes
class BackupCommunication:
    def __init__(self):
        self.primary_routes = {
            'esp32': ['serial', 'wifi'],
            'processing': ['http', 'direct_db'],
            'database': ['local', 'network_backup']
        }
        
    def try_communication(self, target, data):
        """Try primary route, fall back to alternatives"""
        routes = self.primary_routes[target]
        for route in routes:
            try:
                return self.send_via_route(route, target, data)
            except Exception:
                continue
        raise CommunicationError(f"All routes to {target} failed")
```

---

## Performance Monitoring

### Communication Metrics

```python
# Real-time Communication Monitoring
class CommMetrics:
    def __init__(self):
        self.metrics = {
            'esp32_response_time': [],
            'processing_throughput': [],
            'database_query_time': [],
            'network_latency': [],
            'error_rates': {}
        }
        
    def log_communication(self, target, response_time, success):
        """Log communication performance"""
        self.metrics[f'{target}_response_time'].append(response_time)
        if not success:
            self.metrics['error_rates'][target] = self.metrics['error_rates'].get(target, 0) + 1
            
    def get_performance_summary(self):
        """Generate performance report"""
        return {
            'avg_esp32_response': np.mean(self.metrics['esp32_response_time']),
            'processing_rate': len(self.metrics['processing_throughput']),
            'error_rate': sum(self.metrics['error_rates'].values()),
            'system_health': self.calculate_health_score()
        }
```

---

## Security & Authentication

### Communication Security

```python
# Encrypted Communication (for production)
class SecureCommunication:
    def __init__(self):
        self.api_keys = {
            'scryfall': os.getenv('SCRYFALL_API_KEY'),
            'tcgplayer': os.getenv('TCGPLAYER_API_KEY'),
            'internal': os.getenv('NEXUS_INTERNAL_KEY')
        }
        
    def authenticate_request(self, request):
        """Verify API request authenticity"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not self.verify_token(auth_header):
            raise AuthenticationError("Invalid or missing authentication")
            
    def encrypt_sensitive_data(self, data):
        """Encrypt sensitive communication data"""
        # Implementation for production deployment
        pass
```

---

## System Status Communication

### Health Check Protocol

```python
# System Health Monitoring
class SystemHealth:
    def __init__(self):
        self.components = [
            'esp32_hub', 'stepper_motor', 'servo_control',
            'led_matrix', 'pi5_scanner', 'pi2_processor',
            'database', 'network', 'external_apis'
        ]
        
    def health_check_all(self):
        """Check all system components"""
        status = {}
        for component in self.components:
            status[component] = self.check_component_health(component)
        return status
        
    def check_component_health(self, component):
        """Individual component health check"""
        checkers = {
            'esp32_hub': lambda: self.ping_esp32(),
            'stepper_motor': lambda: self.test_stepper(),
            'pi2_processor': lambda: self.ping_processing_server(),
            'database': lambda: self.test_database_connection(),
            'network': lambda: self.test_network_connectivity()
        }
        
        checker = checkers.get(component)
        if checker:
            try:
                return checker()
            except Exception as e:
                return {'status': 'error', 'error': str(e)}
        return {'status': 'unknown'}
```

---

## Communication Documentation Summary

### Active Communication Channels

1. **Hardware Control**: ESP32 ↔ Motors/Servos/LEDs (GPIO/I2C)
2. **Image Processing**: Pi 5 ↔ Pi 2 (HTTP API)  
3. **Database Access**: All components ↔ SQLite databases
4. **External APIs**: Pi 2 ↔ Scryfall/TCGPlayer (HTTPS)
5. **User Interface**: Windows ↔ Pi network (HTTP/SSH)

### Performance Targets

- **ESP32 Response Time**: < 100ms for simple commands
- **Image Processing**: < 30 seconds per card
- **Database Queries**: < 1 second for standard lookups
- **Network Latency**: < 10ms internal, < 500ms external
- **System Uptime**: 99.9% operational availability

### Next Steps for Shop 2 Demo

1. **Test all communication paths** - Verify every protocol works
2. **Optimize response times** - Ensure demo runs smoothly  
3. **Prepare fallback options** - Have backup communication ready
4. **Document error recovery** - Show professional error handling
5. **Performance benchmarks** - Demonstrate speed/reliability

---

*NEXUS Universal Collectibles System*  
*Communication Architecture v2.0*  
*Kevin Caracozza - Patent Pending*  
*January 22, 2026*

**🛥️ From the trenches to the water 🛥️**