-- Locate PRG-ROM data read while the in-game player menu is built.
--
-- The probe reaches the bedroom without RAM injection, resets Mesen's access
-- counters immediately before pressing Start, then exports PRG read/execute
-- counters and the live graphics after the menu is stable.  This is a
-- diagnostic for non-ASCII labels such as ITEMS/HMs/SAVE.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local traceActive = false
local prgDataReads = {}
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

local function memoryBytes(memoryType, first, last)
    local chunks = {}
    local chunk = {}
    for address = first, last do
        chunk[#chunk + 1] = string.char(emu.read(address, memoryType))
        if #chunk == 512 then
            chunks[#chunks + 1] = table.concat(chunk)
            chunk = {}
        end
    end
    if #chunk > 0 then
        chunks[#chunks + 1] = table.concat(chunk)
    end
    return table.concat(chunks)
end

local function exportReadRanges()
    local lines = {
        "PRG offsets exclude the 16-byte iNES header.",
        "Ranges contain bytes read as data while the player menu opened.",
    }
    local offsets = {}
    for offset in pairs(prgDataReads) do
        offsets[#offsets + 1] = offset
    end
    table.sort(offsets)
    local rangeStart = nil
    local rangeEnd = nil
    for _, offset in ipairs(offsets) do
        if rangeStart == nil then
            rangeStart = offset
            rangeEnd = offset
        elseif offset == rangeEnd + 1 then
            rangeEnd = offset
        else
            lines[#lines + 1] = string.format(
                "%06X-%06X",
                rangeStart,
                rangeEnd
            )
            rangeStart = offset
            rangeEnd = offset
        end
    end
    if rangeStart ~= nil then
        lines[#lines + 1] = string.format(
            "%06X-%06X",
            rangeStart,
            rangeEnd
        )
    end
    lines[#lines + 1] = "uniqueDataBytes=" .. tostring(#offsets)
    writeBinary("player_menu_prg_data_ranges.txt", table.concat(lines, "\n"))
end

emu.addMemoryCallback(function(address)
    if not traceActive then
        return
    end
    local converted = emu.convertAddress(address, emu.memType.nesMemory)
    if converted ~= nil and converted.memType == emu.memType.nesPrgRom then
        prgDataReads[converted.address] = true
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

    if frames == 4880 then
        traceActive = true
    end
    pulseAt(4900, "start", 4)
    if frames == 5100 then
        traceActive = false
    end

    if frames ~= 5200 then
        return
    end

    exportReadRanges()
    writeBinary("player_menu_screen.png", emu.takeScreenshot())
    writeBinary(
        "player_menu_chr_ram_8k.bin",
        memoryBytes(emu.memType.nesChrRam, 0x0000, 0x1FFF)
    )
    writeBinary(
        "player_menu_nametable_4k.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
    )
    print(string.format(
        "POKEMON_PLAYER_MENU_ACCESS_PASS mapper=163 region=%s frames=%d",
        tostring(emu.getState()["region"]),
        frames
    ))
    emu.stop(0)
end, emu.eventType.endFrame)
