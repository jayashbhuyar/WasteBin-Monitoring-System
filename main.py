import time
import network
import urequests
import machine
from machine import Pin

# Configuration
CONFIG = {
    'WIFI_SSID': 'Wokwi-GUEST',
    'WIFI_PASSWORD': '',
    'API_V3_KEY': 'Your API Key Here',
    'SENDER_EMAIL': "Your Email Here",
    'RECIPIENT_EMAIL': "Recipient Email Here",
    'ADDRESS': "Dustbin Location",
    'PINS': {
        'TRIGGER': 5,
        'ECHO': 18,
        'GREEN_LED': 4,
        'YELLOW_LED': 16,
        'RED_LED': 17
    },
    'DISTANCE_THRESHOLDS': {
        'EMPTY': 30,
        'HALF_FULL': 10
    },
    'EMAIL_DELAY': 300  
}

class WasteBinMonitor:
    """A system to monitor waste bin levels and send alerts when full."""
    def __init__(self):
        
        self.trigger = Pin(CONFIG['PINS']['TRIGGER'], Pin.OUT)
        self.echo = Pin(CONFIG['PINS']['ECHO'], Pin.IN)
        self.green_led = Pin(CONFIG['PINS']['GREEN_LED'], Pin.OUT)
        self.yellow_led = Pin(CONFIG['PINS']['YELLOW_LED'], Pin.OUT)
        self.red_led = Pin(CONFIG['PINS']['RED_LED'], Pin.OUT)

        
        self.last_email_time = 0
        self.is_currently_full = False
        self.first_full_detection = True

    def connect_wifi(self):
        """Connect to WiFi."""
        sta_if = network.WLAN(network.STA_IF)
        sta_if.active(True)
        sta_if.connect(CONFIG['WIFI_SSID'], CONFIG['WIFI_PASSWORD'])

        start_time = time.time()
        while not sta_if.isconnected():
            if time.time() - start_time > 10:
                print("WiFi connection failed.")
                return False
            time.sleep(0.5)
        
        print(f"WiFi Connected. IP: {sta_if.ifconfig()[0]}")
        return True

    def measure_distance(self):
        """Measure distance using ultrasonic sensor."""
        self.trigger.off()
        time.sleep_us(2)
        self.trigger.on()
        time.sleep_us(10)
        self.trigger.off()

        pulse_start = pulse_end = time.ticks_us()
        timeout = time.ticks_add(pulse_start, 30000)  

        while self.echo.value() == 0:
            pulse_start = time.ticks_us()
            if time.ticks_diff(time.ticks_us(), timeout) > 0:
                return 100  

        while self.echo.value() == 1:
            pulse_end = time.ticks_us()
            if time.ticks_diff(time.ticks_us(), timeout) > 0:
                return 100  

        pulse_duration = time.ticks_diff(pulse_end, pulse_start)
        distance = (pulse_duration / 2) / 29.1
        return distance

    def send_email_alert(self, subject, message, address):
        """Send email using Brevo API with an attractive design."""
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            'accept': 'application/json',
            'api-key': CONFIG['API_V3_KEY'],
            'content-type': 'application/json'
        }

        html_content = f"""
        <html>
            <body>
                <h1>Waste Bin Full Alert</h1>
                <p><strong>Location:</strong> {address}</p>
                <p>{message}</p>
            </body>
        </html>
        """

        payload = {
            "sender": {
                "email": CONFIG['SENDER_EMAIL'],
                "name": "Waste Bin Monitor"
            },
            "to": [
                {
                    "email": CONFIG['RECIPIENT_EMAIL'],
                    "name": "Recipient"
                }
            ],
            "subject": subject,
            "htmlContent": html_content
        }

        print("Payload:", payload)  
        try:
            response = urequests.post(url, json=payload, headers=headers)
            print(f"Email Response: {response.status_code}, {response.text}")
            return response.status_code == 201
        except Exception as e:
            print(f"Error sending email: {e}")
            return False

    def should_send_email(self):
        """Determine if an email alert should be sent."""
        current_time = time.time()
        if self.first_full_detection:
            return True
        if current_time - self.last_email_time >= CONFIG['EMAIL_DELAY']:
            return True
        return False

    def update_bin_status(self, distance):
        """Update LED status and send alert if bin is full."""
        # is_full = distance <= CONFIG['DISTANCE_THRESHOLDS']['HALF_FULL']
        
        if distance > CONFIG['DISTANCE_THRESHOLDS']['EMPTY']:
            self.green_led.on()
            self.yellow_led.off()
            self.red_led.off()
            print("Bin is empty.")
            if self.is_currently_full:
                self.is_currently_full = False
                self.first_full_detection = True
        elif distance > CONFIG['DISTANCE_THRESHOLDS']['HALF_FULL']:
            self.green_led.off()
            self.yellow_led.on()
            self.red_led.off()
            print("Bin is partially full.")
            if self.is_currently_full:
                self.is_currently_full = False
                self.first_full_detection = True
        else:
            self.green_led.off()
            self.yellow_led.off()
            self.red_led.on()
            print("Bin is full.")
            if not self.is_currently_full:
                self.is_currently_full = True
            if self.should_send_email():
                if self.send_email_alert(
                    subject="Waste Bin Full Alert",
                    message="The bin is full and needs to be emptied.",
                    address=CONFIG['ADDRESS']
                ):
                    self.last_email_time = time.time()
                    self.first_full_detection = False

    def run(self):
        """Main monitoring loop."""
        if not self.connect_wifi():
            return

        print("Monitoring started...")
        while True:
            try:
                distance = self.measure_distance()
                print(f"Measured Distance: {distance:.2f} cm")
                self.update_bin_status(distance)
                time.sleep(10)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)


monitor = WasteBinMonitor()
monitor.run()
