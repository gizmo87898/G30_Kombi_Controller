# BMW G30 Instrument Cluster Beam.NG  

Before running, do:
pip install python-can

pip install pyserial

Place the outgauge.lua file in C:\Program Files (x86)\Steam\steamapps\common\BeamNG.drive\lua\vehicle\extensions (or wherever your game is)

Tested with a Seeedstudio USB-to-CAN adapter but should work with anything that python-can supports

speed, rpm, fuel, temp, gear, directionals, foglight, parking lights, highbeam work

temp gauge is buggy, so are directionals

Big thanks to jiggo/e91_330d for his inital sketch and helping me find more ids along with the gear message
