-- Replay an extracted FCEUX controller stream and trace natural Pokédex
-- SEEN/CAUGHT updates.  This is read-only with respect to game memory.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
local inputPath = os.getenv("POKEMON_YELLOW_MESEN_INPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end
if inputPath == nil or inputPath == "" then
    error("POKEMON_YELLOW_MESEN_INPUT is not set")
end

local file = assert(io.open(inputPath, "rb"))
local inputBytes = file:read("*a")
file:close()
if #inputBytes == 0 then
    error("controller input stream is empty")
end

local frame = 0
local events = {
    "frame,kind,address,old_value,new_value,species_id,pc,prg_offset",
}
local pendingCaptures = {}
local eventCount = 0
local caughtSpecies = {}
local seenSpecies = {}

local ranges = {
    { kind = "caught", first = 0x609F, last = 0x60B1 },
    { kind = "seen", first = 0x60B3, last = 0x60C5 },
}

local function decodeInput(value)
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

local function writeBinary(filename, data)
    local output = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    output:write(data)
    output:close()
end

local function prgOffsetForPc(pc)
    local converted = emu.convertAddress(pc, emu.memType.nesMemory)
    if converted ~= nil and converted.memType == emu.memType.nesPrgRom then
        return converted.address
    end
    return -1
end

local function traceWrite(kind, first, address, value)
    local oldValue = emu.read(address, emu.memType.nesDebug)
    if oldValue == value then
        return
    end
    local newBits = value & ((~oldValue) & 0xFF)
    local state = emu.getState()
    local pc = state["cpu.pc"] or 0
    for bit = 0, 7 do
        if (newBits & (1 << bit)) ~= 0 then
            local species = (address - first) * 8 + bit + 1
            if species <= 151 then
                local target = kind == "caught" and caughtSpecies or seenSpecies
                target[species] = true
                eventCount = eventCount + 1
                events[#events + 1] = string.format(
                    "%d,%s,%04X,%02X,%02X,%d,%04X,%06X",
                    frame,
                    kind,
                    address,
                    oldValue,
                    value,
                    species,
                    pc,
                    prgOffsetForPc(pc)
                )
                if kind == "caught" then
                    pendingCaptures[#pendingCaptures + 1] = species
                end
            end
        end
    end
end

for _, range in ipairs(ranges) do
    local traceRange = range
    emu.addMemoryCallback(function(address, value)
        traceWrite(
            traceRange.kind,
            traceRange.first,
            address,
            value
        )
    end, emu.callbackType.write, traceRange.first, traceRange.last)
end

emu.addEventCallback(function()
    local value = 0
    if frame < #inputBytes then
        value = string.byte(inputBytes, frame + 1)
    end
    emu.setInput(decodeInput(value), 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    for _, species in ipairs(pendingCaptures) do
        writeBinary(
            string.format(
                "natural_capture_%03d_frame_%06d.png",
                species,
                frame
            ),
            emu.takeScreenshot()
        )
    end
    pendingCaptures = {}

    if frame ~= #inputBytes then
        return
    end

    writeBinary("natural_pokedex_events.csv", table.concat(events, "\n") .. "\n")
    writeBinary("natural_pokedex_final_screen.png", emu.takeScreenshot())
    local caughtCount = 0
    local seenCount = 0
    for _ in pairs(caughtSpecies) do
        caughtCount = caughtCount + 1
    end
    for _ in pairs(seenSpecies) do
        seenCount = seenCount + 1
    end
    print(string.format(
        "POKEMON_FM3_POKEDEX_TRACE_PASS mapper=163 region=%s frames=%d " ..
        "events=%d newlySeen=%d newlyCaught=%d",
        tostring(emu.getState()["region"]),
        frame,
        eventCount,
        seenCount,
        caughtCount
    ))
    emu.stop(0)
end, emu.eventType.endFrame)
