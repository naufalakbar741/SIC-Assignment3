import machine
import time
import network
import urequests
import ujson
from umqtt.simple import MQTTClient
import _thread

WIFI_SSID = "Naufal"
WIFI_PASSWORD = "abcsampez"

STEPPER1_PUL_PIN = 14
STEPPER1_DIR_PIN = 27
STEPPER2_PUL_PIN = 26
STEPPER2_DIR_PIN = 25
SOIL_MOISTURE_PIN = 34

MQTT_SERVER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "esp32_controller"
MQTT_TOPIC = "sam/esp32/starter"

UBIDOTS_TOKEN = "BBUS-xZP4uuqxXFHy6n7PLGz30DcHN8EPyK"
UBIDOTS_API_URL = "https://industrial.api.ubidots.com/api/v1.6/devices/esp32-devkit-v1/"

stepper_running = False

stepper1_pul = machine.Pin(STEPPER1_PUL_PIN, machine.Pin.OUT)
stepper1_dir = machine.Pin(STEPPER1_DIR_PIN, machine.Pin.OUT)
stepper2_pul = machine.Pin(STEPPER2_PUL_PIN, machine.Pin.OUT)
stepper2_dir = machine.Pin(STEPPER2_DIR_PIN, machine.Pin.OUT)
moisture_sensor = machine.ADC(machine.Pin(SOIL_MOISTURE_PIN))
moisture_sensor.atten(machine.ADC.ATTN_11DB)

stepper_lock = _thread.allocate_lock()

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print('Menghubungkan ke WiFi...')
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        max_wait = 10
        while max_wait > 0:
            if wlan.isconnected():
                break
            max_wait -= 1
            print('Menunggu koneksi...')
            time.sleep(1)
    
    if wlan.isconnected():
        print('Terhubung ke WiFi!')
        print('Network config:', wlan.ifconfig())
        return True
    else:
        print('Gagal terhubung ke WiFi!')
        return False

def run_stepper_sequence():
    global stepper_running
    
    with stepper_lock:
        if stepper_running:
            return
        stepper_running = True
    
    try:
        print("Menjalankan sekuens stepper...")
        
        print("Stepper 1: 10 putaran CW")
        stepper1_dir.value(1)
        for _ in range(10 * 200):
            stepper1_pul.value(1)
            time.sleep_us(500)
            stepper1_pul.value(0)
            time.sleep_us(500)
        
        print("Stepper 2: 10 putaran CW")
        stepper2_dir.value(1)
        for _ in range(10 * 200):
            stepper2_pul.value(1)
            time.sleep_us(500)
            stepper2_pul.value(0)
            time.sleep_us(500)
        
        print("Stepper 2: 10 putaran CCW")
        stepper2_dir.value(0)
        for _ in range(10 * 200):
            stepper2_pul.value(1)
            time.sleep_us(500)
            stepper2_pul.value(0)
            time.sleep_us(500)
            
        print("Sekuens stepper selesai!")
    
    finally:
        with stepper_lock:
            stepper_running = False

def mqtt_callback(topic, msg):
    try:
        print(f"Pesan diterima: {msg}")
        msg_dict = ujson.loads(msg)
        
        if "msg" in msg_dict and msg_dict["msg"] == 1:
            print("Trigger dari MQTT diterima")
            _thread.start_new_thread(run_stepper_sequence, ())
    except Exception as e:
        print(f"Error memproses pesan MQTT: {e}")

def mqtt_task():
    while True:
        try:
            client = MQTTClient(MQTT_CLIENT_ID, MQTT_SERVER, MQTT_PORT)
            client.set_callback(mqtt_callback)
            client.connect()
            client.subscribe(MQTT_TOPIC)
            print(f"Terhubung ke MQTT broker dan subscribe ke {MQTT_TOPIC}")
            
            while True:
                client.check_msg()
                time.sleep(0.1)
        
        except Exception as e:
            print(f"MQTT Error: {e}")
            time.sleep(5)

def read_and_send_moisture():
    try:
        raw_value = moisture_sensor.read()
        
        moisture_percent = (raw_value / 4095) * 100
        
        headers = {
            "X-Auth-Token": UBIDOTS_TOKEN,
            "Content-Type": "application/json"
        }
        
        data = {"moisture": moisture_percent}
        
        response = urequests.post(
            UBIDOTS_API_URL,
            headers=headers,
            data=ujson.dumps(data)
        )
        
        print(f"Data kelembaban: {moisture_percent:.2f}% | Response: {response.status_code}")
        response.close()
        
    except Exception as e:
        print(f"Error membaca/mengirim data kelembaban: {e}")

def moisture_task():
    while True:
        read_and_send_moisture()
        time.sleep(5)

def main():
    if connect_wifi():
        _thread.start_new_thread(mqtt_task, ())
        
        _thread.start_new_thread(moisture_task, ())
        
        print("System ready!")
        
        while True:
            time.sleep(1)
    else:
        print("System initialization failed due to WiFi connection issue")

if __name__ == "__main__":
    main()