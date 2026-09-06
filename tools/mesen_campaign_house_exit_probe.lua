-- Controller-only discovery probe: new game -> bedroom -> downstairs ->
-- attempted front-door exit.  Reads coordinates and PPU signatures but never
-- injects RAM, loads states, rewinds, or uses cheats.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
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

local checkpoints = {
    [4700] = "00_bedroom",
    [4990] = "01_downstairs_spawn",
    [5080] = "02_downstairs_top_center",
    [5260] = "03_downstairs_below_table",
    [5330] = "04_downstairs_door_aligned",
    [5410] = "05_front_door_transition",
    [5480] = "06_outside_candidate",
}

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

local function pulseAt(frame, button, duration)
    if frames == frame then
        desiredInput[button] = true
    elseif frames == frame + duration then
        desiredInput[button] = false
    end
end

local function holdBetween(first, last, button)
    if frames == first then
        desiredInput[button] = true
    elseif frames == last then
        desiredInput[button] = false
    end
end

local function capture(name)
    writeBinary(name .. "_screen.png", emu.takeScreenshot())
    writeBinary(
        name .. "_ram_2k.bin",
        memoryBytes(emu.memType.nesDebug, 0x0000, 0x07FF)
    )
    writeBinary(
        name .. "_nametable_4k.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
    )
    print(string.format(
        "POKEMON_CAMPAIGN_HOUSE_CAPTURE frame=%d checkpoint=%s x=%02X y=%02X pc=%04X",
        frames,
        name,
        emu.read(0x0304, emu.memType.nesDebug),
        emu.read(0x0306, emu.memType.nesDebug),
        emu.getState()["cpu.pc"] or 0
    ))
end

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1
    pulseAt(180, "start", 4)
    for pulseFrame = 360, 4500, 30 do
        pulseAt(pulseFrame, "a", 3)
    end

    -- Bedroom doorway.
    holdBetween(4740, 4868, "right")
    holdBetween(4900, 4940, "up")

    -- Downstairs spawn is near (C0,20).  Go around the right edge of the
    -- table, align with the bottom-center door, then walk out.
    holdBetween(5000, 5064, "left")
    holdBetween(5100, 5244, "down")
    holdBetween(5270, 5318, "left")
    holdBetween(5340, 5400, "down")

    local checkpoint = checkpoints[frames]
    if checkpoint ~= nil then
        capture(checkpoint)
    end

    if frames == 5520 then
        print(string.format(
            "POKEMON_CAMPAIGN_HOUSE_PATH_PROBE_PASS mapper=163 region=%s",
            tostring(emu.getState()["region"])
        ))
        emu.stop(0)
    end
end, emu.eventType.endFrame)
