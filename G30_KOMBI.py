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

bus = can.interface.Bus(channel='com3', bustype='seeedstudio', bitrate=500000)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('127.0.0.1', 4444))
    
# Track time for each function separately
start_time_100ms = time.time()
start_time_10ms = time.time()
start_time_5s = time.time()

id_counter = 0x500

counter_8bit = 0
counter_4bit_100ms = 0
counter_4bit_eps = 0
counter_4bit_mpg = 0
counter_4bit_10ms = 0
abs_counter = 0

ignition = True
rpm = 780
speed = 0
gear = b'0'
gearSelector = b"P"
coolant_temp = 90
oil_temp = 90
fuel = 100
drive_mode = 3

shiftlight = False
shiftlight_start = 5000
shiftlight_end = 6800

left_directional = False
lowpressure = False
right_directional = False
tc = False
abs = False
battery = False
handbrake = False
highbeam = False
bc = False

foglight = False
rear_foglight = False
lowbeam = False 
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

def calculate_section(start, end, input_num):
    if input_num < start:
        return 0
    if input_num >= end:
        return 8
    num_sections = 8
    interval_size = (end - start) / num_sections
    section = int((input_num - start) // interval_size)
    return section

def on_button_press(event):
    global bc
    bc = True

def on_button_release(event):
    global bc
    bc = False

def gui_thread():
    root = tk.Tk()
    root.title("G30")
    update_button = tk.Button(root, text="BC", command=lambda: None)
    update_button.pack(pady=10)
    update_button.bind("<ButtonPress>", on_button_press)
    update_button.bind("<ButtonRelease>", on_button_release)
    root.mainloop()

# Start the GUI thread
gui_thread = threading.Thread(target=gui_thread)
gui_thread.start()

def receive():
    while True:
        message = bus.recv()

        #if message.arbitration_id == 0x2ca:
        #    print("Outside Temp: " + str((message.data[0]/2)-40))
        #else:
        #    print(message)

receive = threading.Thread(target=receive)    
receive.start()


while True:
    current_time = time.time()
    
    #read from the socket if there is data to be read
    ready_to_read, _, _ = select.select([sock], [], [], 0)
    if sock in ready_to_read:
        data, _ = sock.recvfrom(256)
        packet = struct.unpack('I4sHc2c7f2I3f16s16si', data)
        rpm = int(max(min(packet[7], 8000), 0))
        speed = int(packet[6]*2.5) #convert speed to km/h
        coolant_temp = int(packet[9])
        oil_temp = int(packet[12])
        fuel = int(packet[10]*100)
        gearSelector = packet[3]
        gear = packet[4]
        left_directional = False
        right_directional = False
        highbeam = False
        abs = False
        battery = False
        tc = False
        handbrake = False
        shiftlight = False
        ignition = False
        lowpressure = False
        check_engine = False
        foglight = False
        lowbeam = False
        
        if (packet[14]>>0)&1:
            shiftlight = True
        if (packet[14]>>1)&1:
            highbeam = True
        if (packet[14]>>2)&1:
            handbrake = True
        if (packet[14]>>4)&1:
            tc = True
        if (packet[14]>>10)&1:
            abs = True
        if (packet[14]>>9)&1:
            battery = True
        if (packet[14]>>5)&1:
            left_directional = True
        if (packet[14]>>6)&1:
            right_directional = True
        if (packet[14]>>11)&1:
            ignition = True
        if (packet[14]>>12)&1:
            lowpressure = True
        if (packet[14]>>13)&1:
            check_engine = True
        if (packet[14]>>14)&1:
            foglight = True
        if (packet[14]>>15)&1:
            lowbeam = True
        #print(bc)
    # Send each message every 100ms
    elapsed_time_100ms = current_time - start_time_100ms
    if elapsed_time_100ms >= 0.05:
        date = datetime.now()
        fuel_level = round(0x2500 - (fuel / 100) * (0x2500 - 0x0200))
        match gearSelector:
            case b"P":
                gearByte = 0x20
            case b"R":
                gearByte = 0x40
            case b"N":
                gearByte = 0x60
            case b"D":
                gearByte = 0x80
            case b"S":
                gearByte = 0x81
            case b"M":
                gearByte = 0x02
            case _:
                gearByte = 0x00
        messages_100ms = [
            
            can.Message(arbitration_id=0x3c, data=[ # Ignition Status
                0,0b01101110,0,0, 0x00, 0x00, (ignition*9)+1, 0x00], is_extended_id=False), 
            
            can.Message(arbitration_id=0x1f6, data=[ # Directionals "turn indicators"
                0x01+(left_directional*16)+(right_directional*32),0xf0], is_extended_id=False),
            
            can.Message(arbitration_id=0x21a, data=[ # lights "lamp status"
                (lowbeam*4)+(highbeam*2)+(foglight*32)+(rear_foglight*64), 0, 0xf7], is_extended_id=False),

            can.Message(arbitration_id=0x289, data=[ # Cruise Control
                0x13,0xf+counter_4bit_mpg,random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255),random.randint(0,255)], is_extended_id=False),
            
            can.Message(arbitration_id=0x5c0, data=[ # MIL
                0x40, 34, 0x00, 0x30+check_engine, 0xFF, 0xFF, 0xFF, 0xFF], is_extended_id=False),
            
            can.Message(arbitration_id=0x291, data=[ # gear wakeup
                3,0,0,0,0,0,0,0], is_extended_id=False),
                
            can.Message(arbitration_id=0x2c4, data=[ # engine temp
                0x8B, 0xFF, oil_temp+8, 0xCD, 0x5D, 0x37, 0xCD, random.randint(0,255)], is_extended_id=False),
            
            can.Message(arbitration_id=0x30b, data=[ # Auto Start/Stop "status, automatic engine start-stop function"
                0,0,0,4,0,0,0,0], is_extended_id=False),
            
            can.Message(arbitration_id=0x349, data=[ # Fuel level "raw data, fuel tank level"
                fuel_level&0xff,fuel_level>>8,fuel_level&0xff,fuel_level>>8,4,4,4,4], is_extended_id=False),
           
            can.Message(arbitration_id=0x36a, data=[ # Auto Highbeam "status, high-beam assist"
                0xff,0xff,0xff,0xff,0,0,0,0], is_extended_id=False),
            
            can.Message(arbitration_id=0x39e, data=[ # Date and time
                date.hour,date.minute,date.second,date.day,date.year>>8,date.year&0xff,0,0b00000010], is_extended_id=False),
            
            can.Message(arbitration_id=0x3d8, data=[ # Drive Mode "configuration, driving dynamics switch"
                0, drive_mode, 0,0,0,0,0,0], is_extended_id=False),
            

            can.Message(arbitration_id=0x3fd, data=[ # 0x80 is drive, 0x20 is park, 0x40 is reverse, 0x81 is ds, 
                0xff, counter_4bit_100ms + (int.from_bytes(gear, byteorder='big')&0xf)*16, gearByte, 0,0xFF], is_extended_id=False),

            can.Message(arbitration_id=0x581, data=[ # Seatbelt
                0x40,0x4d,0,0x29,0xff,0xff,0xff,0xff], is_extended_id=False),
            
            can.Message(arbitration_id=0x1ee, data=[ # BC button
                0x00+(bc*64),0xff], is_extended_id=False),

            can.Message(arbitration_id=0x291, data=[ # units
                0b00001011,0,0,0,0,0,0,0], is_extended_id=False),

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
        
        messages_100ms[12].data[0] = crc8_sae_j1850(messages_100ms[12].data[1:], 0xD6, 0x1d,0xff) # Gear 3fd Checksum 
        messages_100ms[3].data[0] = crc8_sae_j1850(messages_100ms[3].data[1:], 0x82, 0x1d,0xff) # Cruise Control 289 checksum
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
        rpmval = int(rpm/10)
        messages_10ms = [
            can.Message(arbitration_id=0xf3, data=[ # RPM
                0xf3, (rpmval&0xf)*16 + counter_4bit_10ms, (rpmval >> 4) & 0xFF, 0xc0, 0xF0, 0x44, 0xFF, 0xFF], is_extended_id=False),    
            can.Message(arbitration_id=0x1a1, data=[ # Speed
                random.randint(0,255),counter_4bit_10ms+240, (speed*92)&0xff, (speed*92)>>8, 0x81], is_extended_id=False),
            can.Message(arbitration_id=0xdf, data=[ # Shift Lights
                (shiftlight*0x10) + calculate_section(shiftlight_start, shiftlight_end, rpm),0,0,0, 0, 0, 0, 0], is_extended_id=False),
        ]
        #do checksums here
        messages_10ms[1].data[0] = crc8_sae_j1850(messages_10ms[1].data, 0x2c, 0x1d,0) # Speed Checksum
        messages_10ms[0].data[0] = crc8_sae_j1850(messages_10ms[0].data, 0x2c, 0x1d,0) # RPM Checksum
        
        for message in messages_10ms:
            bus.send(message)
            wpt.sleep(0.001)
        start_time_10ms = time.time()

    # Execute code every 5s
    elapsed_time_5s = current_time - start_time_5s
    if elapsed_time_5s >= 6:
        id_counter += 1
        print(hex(id_counter))
        if id_counter == 0x7ff:
            id_counter = 0

        start_time_5s = time.time()

send_thread_20ms.join()

sock.close()

