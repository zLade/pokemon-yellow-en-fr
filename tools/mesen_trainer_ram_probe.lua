-- Trace persistent SRAM while the player/trainer status screen is opened.
-- This isolates badges and story-state reads from the fresh-game save.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local traceActive = false
local accesses = {}
local desiredInput = {
    a = false,
    b = false,
    select = false,
    start = false,
    up = false,
    down = false,
    left = false,
    right = false,
}

local function pulseAt(frame, button, duration)
    if frames == frame then
        desiredInput[button] = true
    elseif frames == frame + duration then
        desiredInput[button] = false
    end
end

local function writeBinary(filename, data)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    file:write(data)
    file:close()
end

local function snapshot(filename)
    local bytes = {}
    for address = 0x6000, 0x67FF do
        bytes[#bytes + 1] = string.char(
            emu.read(address, emu.memType.nesMemory)
        )
    end
    writeBinary(filename .. "_primary_sram_2k.bin", table.concat(bytes))
    writeBinary(filename .. "_screen.png", emu.takeScreenshot())
end

local function record(kind, address, value)
    if not traceActive then
        return
    end
    local state = emu.getState()
    local pc = state["cpu.pc"] or 0
    local converted = emu.convertAddress(pc, emu.memType.nesMemory)
    local prgOffset = -1
    if converted ~= nil and converted.memType == emu.memType.nesPrgRom then
        prgOffset = converted.address
    end
    if #accesses < 4096 then
        accesses[#accesses + 1] = string.format(
            "%s frame=%04d addr=%04X value=%02X pc=%04X prg=%06X",
            kind,
            frames,
            address,
            value or 0,
            pc,
            prgOffset
        )
    end
end

emu.addMemoryCallback(function(address, value)
    record("R", address, value)
end, emu.callbackType.read, 0x6000, 0x67FF)

emu.addMemoryCallback(function(address, value)
    record("W", address, value)
end, emu.callbackType.write, 0x6000, 0x67FF)

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1
    pulseAt(180, "start", 4)
    for pulseFrame = 360, 4500, 30 do
        pulseAt(pulseFrame, "a", 3)
    end

    pulseAt(4900, "start", 4)
    pulseAt(5220, "down", 4)
    pulseAt(5280, "down", 4)
    pulseAt(5340, "down", 4)
    if frames == 5380 then
        snapshot("01_trainer_selected")
        -- Eight badges are rendered from the eight bits of one byte.
        emu.write(0x60C7, 0xFF, emu.memType.nesMemory)
        traceActive = true
    end
    pulseAt(5400, "a", 4)

    if frames == 5750 then
        traceActive = false
        snapshot("02_trainer_screen")
        writeBinary("trainer_primary_sram_access_log.txt", table.concat(
            accesses,
            "\n"
        ))
        print(string.format(
            "POKEMON_TRAINER_RAM_PASS mapper=163 region=%s frames=%d",
            tostring(emu.getState()["region"]),
            frames
        ))
        emu.stop(0)
    end
end, emu.eventType.endFrame)
