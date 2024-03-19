-- This Source Code Form is subject to the terms of the bCDDL, v. 1.1.
-- If a copy of the bCDDL was not distributed with this
-- file, You can obtain one at http://beamng.com/bCDDL-1.1.txt

-- this file serves two purposes:
-- A) generic outgauge implementation: used to use for example custom made dashboard hardware and alike
-- B) update the user interface for the remote control app directly via the sendPackage function
-- please note that use case A and B exclude each other for now.

local M = {}

local ip = "127.0.0.1"
local port = 4444

local udpSocket = nil

local ffi = require("ffi")

local function declareOutgaugeStruct()
  -- the original protocol documentation can be found at LFS/docs/InSim.txt
  ffi.cdef [[
  typedef struct outgauge_t  {
          ////////////////
          //////////////// IMPORTANT
          //////////////// do not modify this format without also updating the documentation at git:documentation/modding/protocols
          ////////////////
      unsigned       time;            // [0] time in milliseconds (to check order) // N/A, hardcoded to 0
      char           car[4];          // [1]  Car name // N/A, hardcoded to "beam"
      unsigned short flags;           // [2] Info (see OG_x below)
      char           gear;            // [3]  Gear selector position, P/R/N/D/S/M/L
      char           gearIndex;       // [4]  Gear 1/2/3/4/5/6/7, null if not a manual car, or in sport/manual mode
      char           plid;            // [5]  Unique ID of viewed player (0 = none) // N/A, hardcoded to 0
      float          speed;           // [6]  M/S
      float          rpm;             // [7]  RPM
      float          turbo;           // [8]  BAR
      float          engTemp;         // [9]  C
      float          fuel;            // [10]  0 to 1
      float          oilPressure;     // [11]  BAR // N/A, hardcoded to 0
      float          oilTemp;         // [12]  C
      unsigned       dashLights;      // [13]  Dash lights available (see DL_x below)
      unsigned       showLights;      // [14]  Dash lights currently switched on
      float          throttle;        // [15]  0 to 1
      float          brake;           // [16]  0 to 1
      float          clutch;          // [17]  0 to 1
      char           display1[16];    // [18]  Usually Fuel // N/A, hardcoded to ""
      char           display2[16];    // [19]  Usually Settings // N/A, hardcoded to ""
      int            id;              // [20]  optional - only if OutGauge ID is specified
  } outgauge_t;
  ]]
end

pcall(declareOutgaugeStruct)

--[[
CONSTANTS
// OG_x - bits for OutGaugePack Flags
#define OG_SHIFT      1        // key // N/A
#define OG_CTRL       2        // key // N/A
#define OG_TURBO      8192     // show turbo gauge
#define OG_KM         16384    // if not set - user prefers MILES
#define OG_BAR        32768    // if not set - user prefers PSI

// DL_x - bits for OutGaugePack DashLights and ShowLights
DL_SHIFT,           // bit 0    - shift light
DL_FULLBEAM,        // bit 1    - full beam
DL_HANDBRAKE,       // bit 2    - handbrake
DL_PITSPEED,        // bit 3    - pit speed limiter // N/A
DL_TC,              // bit 4    - TC active or switched off
DL_SIGNAL_L,        // bit 5    - left turn signal
DL_SIGNAL_R,        // bit 6    - right turn signal
DL_SIGNAL_ANY,      // bit 7    - shared turn signal // N/A
DL_OILWARN,         // bit 8    - oil pressure warning
DL_BATTERY,         // bit 9    - battery warning
DL_ABS,             // bit 10   - ABS active or switched off
DL_IGNITION,        // bit 11   - ignition switch state
DL_LOWPRESSURE,     // bit 12   - tpms light
DL_CHECKENGINE,     // bit 13   - cel
DL_FOG,             // bit 14   - fog lights
DL_LOWBEAM,         // bit 15   - lowbeam/parking lights


]]
    --////////////////
    --//////////////// IMPORTANT
    --//////////////// do not modify this format without also updating the documentation at git:documentation/modding/protocols
    --////////////////

local OG_KM = 16384
local OG_BAR = 32768
local OG_TURBO = 8192

local DL_SHIFT = 2 ^ 0
local DL_FULLBEAM = 2 ^ 1
local DL_HANDBRAKE = 2 ^ 2
local DL_TC = 2 ^ 4
local DL_SIGNAL_L = 2 ^ 5
local DL_SIGNAL_R = 2 ^ 6
local DL_OILWARN = 2 ^ 8
local DL_BATTERY = 2 ^ 9
local DL_ABS = 2 ^ 10
local DL_IGNITION = 2 ^ 11
local DL_LOWPRESSURE = 2 ^ 12
local DL_CHECKENGINE = 2 ^ 13
local DL_FOG = 2 ^ 14
local DL_LOWBEAM = 2 ^ 15

local hasESC = false
local hasShiftLights = false

local function sendPackage(ip, port, id)
  --log('D', 'outgauge', 'sendPackage: '..tostring(ip) .. ':' .. tostring(port))

  if not electrics.values.watertemp then
    -- vehicle not completly initialized, skip sending package
    return
  end

  local o = ffi.new("outgauge_t")
  -- set the values
  o.time = 0 -- not used atm
  o.car = "beam"
  o.flags = OG_KM + OG_BAR + (electrics.values.turboBoost and OG_TURBO or 0)


  o.gear = string.byte(electrics.values.gear)
  o.gearIndex = electrics.values.gearIndex

  o.plid = 0
  o.speed = electrics.values.wheelspeed or electrics.values.airspeed
  o.rpm = electrics.values.rpm or 0
  o.turbo = (electrics.values.turboBoost or 0) / 14.504

  o.engTemp = electrics.values.watertemp or 0
  o.fuel = electrics.values.fuel or 0
  o.oilPressure = 0 -- TODO
  o.oilTemp = electrics.values.oiltemp or 0

  -- the lights

  if hasShiftLights then
    o.dashLights = bit.bor(o.dashLights, DL_SHIFT)
    if electrics.values.shouldShift then
      o.showLights = bit.bor(o.showLights, DL_SHIFT)
    end
  end

  o.dashLights = bit.bor(o.dashLights, DL_FULLBEAM)
  if electrics.values.highbeam ~= 0 then
    o.showLights = bit.bor(o.showLights, DL_FULLBEAM)
  end

  o.dashLights = bit.bor(o.dashLights, DL_HANDBRAKE)
  if electrics.values.parkingbrake ~= 0 then
    o.showLights = bit.bor(o.showLights, DL_HANDBRAKE)
  end

  hasESC = electrics.values.hasESC
  if hasESC then
    o.dashLights = bit.bor(o.dashLights, DL_TC)
    if electrics.values.esc ~= 0 or electrics.values.tcs ~= 0 then
      o.showLights = bit.bor(o.showLights, DL_TC)
    end
  end


  o.dashLights = bit.bor(o.dashLights, DL_SIGNAL_L)
  if electrics.values.signal_L ~= 0 then
    o.showLights = bit.bor(o.showLights, DL_SIGNAL_L)
  end

  o.dashLights = bit.bor(o.dashLights, DL_SIGNAL_R)
  if electrics.values.signal_R ~= 0 then
    o.showLights = bit.bor(o.showLights, DL_SIGNAL_R)
  end

  o.dashLights = bit.bor(o.dashLights, DL_OILWARN)
  if electrics.values.oil ~= 0 then
    o.showLights = bit.bor(o.showLights, DL_OILWARN)
  end

  
  
  o.dashLights = bit.bor(o.dashLights, DL_BATTERY)
  if electrics.values.engineRunning == 0 then
    o.showLights = bit.bor(o.showLights, DL_BATTERY)
  end

  local hasABS = electrics.values.hasABS or false
  if hasABS then
    o.dashLights = bit.bor(o.dashLights, DL_ABS)
    if electrics.values.abs ~= 0 then
      o.showLights = bit.bor(o.showLights, DL_ABS)
    end
  end

  
  o.dashLights = bit.bor(o.dashLights, DL_IGNITION)
  if electrics.values.ignition ~= 0 then
    o.showLights = bit.bor(o.showLights, DL_IGNITION)
  end

  o.dashLights = bit.bor(o.dashLights, DL_LOWPRESSURE)
  if electrics.values.lowpressure ~= 0 then
    o.showLights = bit.bor(o.showLights, DL_LOWPRESSURE)
  end

  o.dashLights = bit.bor(o.dashLights, DL_CHECKENGINE)
  if electrics.values.checkengine ~= 0 then
    o.showLights = bit.bor(o.showLights, DL_CHECKENGINE)
  end

  o.dashLights = bit.bor(o.dashLights, DL_FOG)
  if electrics.values.fog ~= 0 then
    o.showLights = bit.bor(o.showLights, DL_FOG)
  end

  o.dashLights = bit.bor(o.dashLights, DL_LOWBEAM)
  if electrics.values.lowbeam ~= 0 then
    o.showLights = bit.bor(o.showLights, DL_LOWBEAM)
  end
  
  o.throttle = electrics.values.throttle
  o.brake = electrics.values.brake
  o.clutch = electrics.values.clutch
  o.display1 = "" -- TODO
  o.display2 = "" -- TODO
  o.id = id

  local packet = ffi.string(o, ffi.sizeof(o)) --convert the struct into a string
  udpSocket:sendto(packet, ip, port)
  --log("I", "", "SendPackage for ID '"..dumps(id).."': "..dumps(electrics.values.rpm))
end

local function updateGFX(dt)
  if not playerInfo.firstPlayerSeated then
    return
  end
  sendPackage(ip, port, 0)
end

local function onExtensionLoaded()
  if not ffi then
    log("E", "outgauge", "Unable to load outgauge module: Lua FFI required")
    return false
  end

  if not udpSocket then
    udpSocket = socket.udp()
  end

  ip = settings.getValue("outgaugeIP")
  port = tonumber(settings.getValue("outgaugePort"))

  log("I", "", "Outgauge initialized for: " .. tostring(ip) .. ":" .. tostring(port))

  local shiftLightControllers = controller.getControllersByType("shiftLights")
  hasShiftLights = shiftLightControllers and #shiftLightControllers > 0
  return true
end

local function onExtensionUnloaded()
  if udpSocket then
    udpSocket:close()
  end
  udpSocket = nil
end

-- public interface
M.onExtensionLoaded = onExtensionLoaded
M.onExtensionUnloaded = onExtensionUnloaded
M.updateGFX = updateGFX

M.sendPackage = sendPackage

return M
