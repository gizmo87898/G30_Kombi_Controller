import time
import can
import random
import socket
import struct
import select 
import threading
import tkinter as tk
import win_precise_time as wpt
from datetime import datetime

bus = can.interface.Bus(channel='com5', bustype='seeedstudio', bitrate=500000)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('127.0.0.1', 4444))
    
# Track time for each function separately
start_time_100ms = time.time()
start_time_10ms = time.time()
start_time_5s = time.time()


id_counter = 0

counter_8bit = 0
counter_4bit_100ms = 0
counter_4bit_eps = 0
counter_4bit_mpg = 0
counter_4bit_10ms = 0
abs_counter = 0

rpm = 2000
speed = 0
coolant_temp = 120
fuel = 50

left_directional = False
right_directional = False
tc = False
abs = False
battery = False
handbrake = False
highbeam = False
auto_highbeam = False
park_light = False


tpms = False #tbd
cruise_control = False # tbd
cruise_control_speed = 80 # tbd
foglight = False
rear_foglight = False
parking_lights = False 
check_engine = False
hood = False
trunk = False
front_left = 30
front_right = 30
rear_left = 30
rear_right = 30
airbag = False
seatbelt = False

def crc8_sae_j1850(data, xor, polynomial, init_val):
    crc = init_val

    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ polynomial
            else:
                crc <<= 1
            crc &= 0xFF

    return crc ^ xor

def update_message_data(state):
    messages_100ms[24].data[0] = 0x40 if state == "press" else 0x00

def on_button_event(event):
    update_message_data("press" if event.type == tk.EventType.ButtonPress else "release")

def gui_thread():
    root = tk.Tk()
    root.title("6WA")

    update_button = tk.Button(root, text="BC", command=lambda: None)
    update_button.pack(pady=10)

    update_button.bind("<Button>", on_button_event)

    root.mainloop()

# Start the GUI thread
gui_thread = threading.Thread(target=gui_thread)
gui_thread.start()

while True:
    current_time = time.time()
    
    #read from the socket if there is data to be read
    ready_to_read, _, _ = select.select([sock], [], [], 0)
    if sock in ready_to_read:
        data, _ = sock.recvfrom(256)
        packet = struct.unpack('I4sH2c7f2I3f16s16si', data)
        
        rpm = int(max(min(packet[6], 8000), 0))
        speed = max(min(int(packet[5]*2.5), 160), 0) #convert speed to km/h
        
        left_directional = False
        right_directional = False
        highbeam = False
        abs = False
        battery = False
        tc = False
        handbrake = False
        
        if (packet[13]>>1)&1:
            highbeam = True
        if (packet[13]>>2)&1:
            handbrake = True
        if (packet[13]>>4)&1:
            tc = True
        if (packet[13]>>10)&1:
            abs = True
        if (packet[13]>>9)&1:
            battery = True
        if (packet[13]>>5)&1:
            left_directional = True
        if (packet[13]>>6)&1:
            right_directional = True
            
    # Send each message every 100ms
    elapsed_time_100ms = current_time - start_time_100ms
    if elapsed_time_100ms >= 0.05:
        date = datetime.now()
        
        messages_100ms = [
            

            
            can.Message(arbitration_id=0x3c, data=[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1a, 0x00], is_extended_id=False), #Ignition Status
               
            
            can.Message(arbitration_id=0x1f6, data=[ # Directionals "turn indicators"
                0x01+(left_directional*16)+(right_directional*32),0xf1], is_extended_id=False),
            
            can.Message(arbitration_id=0x21a, data=[ # lights "lamp status"
                (parking_lights*4)+(highbeam*2)+(foglight*32)+(rear_foglight*64), 0, 0xf7], is_extended_id=False),
            
           
            can.Message(arbitration_id=0x291, data=[ # MIL, set langage and units
                0x02, 0x04, 0x18, 0,0,0,0,0x04], is_extended_id=False),
            
            can.Message(arbitration_id=0x2a7, data=[ # Power STeering "display, Check Control, driving dynamics" 
                0xa7,counter_4bit_eps+0xf0,0xfe,0xff,0x14], is_extended_id=False),
            
            can.Message(arbitration_id=0x2bb, data=[ # mpg
                0xbb,counter_4bit_mpg+240,counter_8bit,counter_8bit,0xf2], is_extended_id=False),
            
            can.Message(arbitration_id=0x2c4, data=[ # mpg? "status, engine fuel consumption"
                0xD2,0x0B,0xFF,0xFF,0xFF,0x64,0xC1,0xFF], is_extended_id=False),
            
            can.Message(arbitration_id=0x30b, data=[ # Auto Start/Stop "status, automatic engine start-stop function"
                0,0,0,4,0,0,0,0], is_extended_id=False),
            
            
            
            can.Message(arbitration_id=0x349, data=[ # Fuel level "raw data, fuel tank level"
                0xfe, 0x3a, 0xce, 0x3a,0], is_extended_id=False),
            
           
            can.Message(arbitration_id=0x36a, data=[ # Auto Highbeam "status, high-beam assist"
                0xff,0xff,0xff,0xff,0,0,0,0], is_extended_id=False),
            
           
            
            
            can.Message(arbitration_id=0x39e, data=[ # Date and time
                date.hour,date.minute,date.second,date.day,date.year>>8,date.year&0xff,0,0xf2], is_extended_id=False),
            
            can.Message(arbitration_id=0x3d8, data=[ # Drive Mode "configuration, driving dynamics switch"
                counter_8bit, 0x2, counter_8bit, counter_8bit, counter_8bit,counter_8bit,counter_8bit,counter_8bit], is_extended_id=False),
            
            can.Message(arbitration_id=0x3f9, data=[ # Oil and coolant temp "status, gear selection" "drivetrain data"
                0x02, 148, counter_8bit, 148, 148, 148, 148, counter_8bit], is_extended_id=False),
            
            can.Message(arbitration_id=0x581, data=[ # Seatbelt
                0x40,0x4d,0,0x29,0xff,0xff,0xff,0xff], is_extended_id=False),
            
            can.Message(arbitration_id=0x1ee, data=[ # BC button
                0x00,0xff], is_extended_id=False),

            can.Message(arbitration_id=0x510, data=[
                random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255)], is_extended_id=False),

            can.Message(arbitration_id=id_counter, data=[
                random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255)], is_extended_id=False),
        ]
        
        #Update checksums and counters here
        counter_8bit = (counter_8bit + 1) % 256

        counter_4bit_100ms = (counter_4bit_100ms + 1) % 15
        counter_4bit_eps = (counter_4bit_eps + 4) % 15
        counter_4bit_mpg = (counter_4bit_mpg + 2) % 15
        
        messages_100ms[9].data[0] = crc8_sae_j1850(messages_100ms[9].data[1:], 0xde, 0x1d,0xff) # MPG 2bb checksum
       

        
        if ((((messages_100ms[2].data[2] >> 4) + 3) << 4) & 0xF0) | 0x03:
            messages_100ms[2].data[2] = 0x00
            
            
        # Send Messages
        for message in messages_100ms:
            bus.send(message)
            #print(message)
            #if message.arbitration_id == 0x1ee:
            #    print(message)
            wpt.sleep(0.001)
        start_time_100ms = time.time()


    # Execute code every 10ms
    elapsed_time_10ms = current_time - start_time_10ms
    if elapsed_time_10ms >= 0.01:  # 10ms
        counter_4bit_10ms = (counter_4bit_10ms + 1) % 15
        #print(counter_4bit_10ms)
        
        rpmval = int(rpm/10.3)
        
        messages_10ms = [
            can.Message(arbitration_id=0xf3, data=[ # RPM
                0xf3, (rpmval&0xf)*16 + counter_4bit_10ms, (rpmval >> 4) & 0xFF, 0xc0, 0xF0, 0x44, 0xFF, 0xFF], is_extended_id=False),    
            can.Message(arbitration_id=0x1a1, data=[ # Speed
                random.randint(0,255),counter_4bit_10ms+240, (speed*90)&0xff, (speed*90)>>8, 0x81], is_extended_id=False),
        ]
        #do checksums here
        messages_10ms[1].data[0] = crc8_sae_j1850(messages_10ms[1].data, 0x2c, 0x1d,0) # Speed Checksum (dont work)

        messages_10ms[0].data[0] = crc8_sae_j1850(messages_10ms[0].data, 0x2c, 0x1d,0) # RPM Checksum
        
        for message in messages_10ms:
            #if message.arbitration_id == 0xf3:
                #print(message)
            bus.send(message)
            wpt.sleep(0.001)
        start_time_10ms = time.time()

    # Execute code every 5s
    elapsed_time_5s = current_time - start_time_5s
    if elapsed_time_5s >= 3:
        id_counter += 1
        print(hex(id_counter))
        
       
        start_time_5s = time.time()
    
sock.close()

