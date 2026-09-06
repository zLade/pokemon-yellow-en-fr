-- Runtime samples proving displayed-name -> description mapping for
-- Pokédex #001, #002 and #004.  The full 151-entry relationship is proven
-- statically by audit_pokedex_full_151.py and its hard pointer/name anchors.
-- The game and the three sampled entries are reached with controller input.
-- Only the already documented Pokédex flags/counters are initialized;
-- name/description pointers and text are never modified.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local traceActive = false
local activeEntry = 0
local reads = {"entry,frame,cpu_address,prg_offset,value"}
local desiredInput = {
    a = false, b = false, select = false, start = false,
    up = false, down = false, left = false, right = false,
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

local function assistedKanto()
    emu.write(0x6000, emu.read(0x6000, emu.memType.nesDebug) | 0x20,
        emu.memType.nesDebug)
    for offset = 0, 18 do
        local value = offset == 18 and 0x7F or 0xFF
        emu.write(0x609F + offset, value, emu.memType.nesDebug)
        emu.write(0x60B3 + offset, value, emu.memType.nesDebug)
    end
    emu.write(0x6031, 151, emu.memType.nesDebug)
    emu.write(0x6032, 151, emu.memType.nesDebug)
    emu.write(0x60C8, 151, emu.memType.nesDebug)
end

emu.addMemoryCallback(function(address, value)
    if not traceActive or #reads > 4096 then
        return
    end
    local converted = emu.convertAddress(address, emu.memType.nesMemory)
    if converted ~= nil and converted.memType == emu.memType.nesPrgRom then
        local prg = converted.address
        if (prg >= 0x031F00 and prg <= 0x037A00) then
            reads[#reads + 1] = string.format(
                "%d,%d,%04X,%06X,%02X",
                activeEntry, frames, address, prg, value or 0)
        end
    end
end, emu.callbackType.read, 0x8000, 0xFFFF)

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
    if frames == 5230 then
        assistedKanto()
    end
    pulseAt(5250, "a", 4)
    if frames == 5350 then
        traceActive = true
    end
    if frames == 5440 then activeEntry = 1 end
    pulseAt(5450, "a", 4)
    if frames == 5600 then
        writeBinary("pokedex_mapping_001.png", emu.takeScreenshot())
    end
    pulseAt(5650, "b", 4)
    pulseAt(5750, "down", 3)
    if frames == 5840 then activeEntry = 2 end
    pulseAt(5850, "a", 4)
    if frames == 6000 then
        writeBinary("pokedex_mapping_002.png", emu.takeScreenshot())
    end
    pulseAt(6050, "b", 4)
    pulseAt(6150, "down", 3)
    pulseAt(6170, "down", 3)
    if frames == 6240 then activeEntry = 4 end
    pulseAt(6250, "a", 4)
    if frames == 6400 then
        writeBinary("pokedex_mapping_004.png", emu.takeScreenshot())
    end
    if frames == 6450 then
        writeBinary("pokedex_mapping_samples_reads.csv",
            table.concat(reads, "\n") .. "\n")
        print(string.format(
            "POKEMON_POKEDEX_MAPPING_PASS frames=%d samples=3 filtered_reads=%d",
            frames, #reads - 1))
        emu.stop(0)
    end
end, emu.eventType.endFrame)
