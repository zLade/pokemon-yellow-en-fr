-- Controller-only campaign explorer.
-- Replays the verified opening stream, then walks a bounded frontier while
-- recording unique screen/coordinate signatures. No RAM writes, savestates,
-- cheats or rewind are used.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
local inputPath = os.getenv("POKEMON_YELLOW_MESEN_INPUT")
if not outputDirectory or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end
if not inputPath or inputPath == "" then
    error("POKEMON_YELLOW_MESEN_INPUT is not set")
end

local inputFile = assert(io.open(inputPath, "rb"))
local opening = inputFile:read("*a")
inputFile:close()
if #opening < 5300 then
    error("opening controller stream is shorter than 5300 frames")
end

local frame = 0
local phase = "opening"
local actionIndex = 1
local actionFrame = 0
local signatureLast = ""
local stableFrames = 0
local seen = {}
local captures = 0
local directions = {
    {name = "up", value = 0x10, opposite = 0x20},
    {name = "right", value = 0x80, opposite = 0x40},
    {name = "down", value = 0x20, opposite = 0x10},
    {name = "left", value = 0x40, opposite = 0x80},
}

local function writeText(filename, text)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "w"))
    file:write(text)
    file:close()
end

local function writeBinary(filename, bytes)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    file:write(bytes)
    file:close()
end

local function checksumNametable()
    local hash = 0
    for address = 0x2000, 0x2FFF do
        hash = (hash * 257 + emu.read(address, emu.memType.nesPpuDebug))
            % 0x100000000
    end
    return hash
end

local function signature()
    local hash = checksumNametable()
    local x = emu.read(0x0304, emu.memType.nesDebug)
    local y = emu.read(0x0306, emu.memType.nesDebug)
    return string.format("%08X:%02X:%02X", hash, x, y), hash, x, y
end

local function decode(value)
    return {
        a = (value & 0x01) ~= 0,
        b = (value & 0x02) ~= 0,
        select = (value & 0x04) ~= 0,
        start = (value & 0x08) ~= 0,
        up = (value & 0x10) ~= 0,
        down = (value & 0x20) ~= 0,
        left = (value & 0x40) ~= 0,
        right = (value & 0x80) ~= 0,
    }
end

local function captureIfNew()
    local key, hash, x, y = signature()
    if key == signatureLast then
        stableFrames = stableFrames + 1
    else
        signatureLast = key
        stableFrames = 0
    end
    if stableFrames < 12 then
        return key, hash, x, y
    end
    if seen[key] then
        return key, hash, x, y
    end
    seen[key] = true
    captures = captures + 1
    writeBinary(
        string.format("explore_%03d_screen.png", captures),
        emu.takeScreenshot()
    )
    local log = string.format(
        "capture=%03d frame=%d phase=%s action=%s hash=%08X x=%02X y=%02X\n",
        captures, frame, phase, directions[actionIndex].name, hash, x, y
    )
    local existing = ""
    local handle = io.open(outputDirectory .. "\\exploration.tsv", "r")
    if handle then
        existing = handle:read("*a")
        handle:close()
    end
    writeText("exploration.tsv", existing .. log)
    return key, hash, x, y
end

emu.addEventCallback(function()
    local value = 0
    if phase == "opening" then
        value = string.byte(opening, frame + 1) or 0
    else
        -- Periodic A/B pulses dismiss residual dialogue and battle prompts.
        if frame % 180 < 4 then
            value = 0x01
        elseif frame % 180 >= 90 and frame % 180 < 94 then
            value = 0x02
        else
            value = directions[actionIndex].value
        end
    end
    emu.setInput(decode(value), 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    if frame == 5300 then
        phase = "exploration"
        actionFrame = 0
        writeText("exploration.tsv", "capture frame phase action hash x y\n")
    end
    if phase ~= "exploration" then
        return
    end
    actionFrame = actionFrame + 1
    captureIfNew()
    if actionFrame >= 180 then
        actionFrame = 0
        actionIndex = (actionIndex % #directions) + 1
    end
    if frame >= 5300 + 18000 then
        print(string.format(
            "POKEMON_CAMPAIGN_EXPLORER_PASS mapper=163 region=%s " ..
            "frames=%d uniqueSignatures=%d captures=%d",
            tostring(emu.getState()["region"]), frame, captures, captures
        ))
        emu.stop(0)
    end
end, emu.eventType.endFrame)
