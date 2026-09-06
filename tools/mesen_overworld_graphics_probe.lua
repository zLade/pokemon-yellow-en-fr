-- Explore early overworld rooms using only controller input and export
-- graphics checkpoints.  This is a discovery probe for the modular CHR pack,
-- not a gameplay regression assertion.

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
    [3050] = "01-bedroom-start",
    [3300] = "02-bedroom-right",
    [3450] = "03-bedroom-door",
    [3700] = "04-next-room",
    [4100] = "05-next-room-move",
    [4500] = "06-late-move",
}

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

local function writeBinary(filename, data)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    file:write(data)
    file:close()
end

local function exportCheckpoint(prefix)
    writeBinary(prefix .. "_screen.png", emu.takeScreenshot())
    writeBinary(
        prefix .. "_chr_ram_8k.bin",
        memoryBytes(emu.memType.nesChrRam, 0x0000, 0x1FFF)
    )
    writeBinary(
        prefix .. "_nametable_4k.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
    )
    writeBinary(
        prefix .. "_palette_32.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x3F00, 0x3F1F)
    )
    print(
        "POKEMON_OVERWORLD_GRAPHICS_CAPTURE frame=" ..
        tostring(frames) .. " state=" .. prefix
    )
end

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1

    pulseAt(180, "start", 4)
    for pulseFrame = 360, 3000, 30 do
        pulseAt(pulseFrame, "a", 3)
    end

    -- Bedroom: cross the room toward the opening visible on the right.
    holdBetween(3100, 3320, "right")
    holdBetween(3340, 3430, "up")
    -- Try the two likely exit directions in the next room.
    holdBetween(3500, 3720, "down")
    holdBetween(3750, 3970, "right")
    holdBetween(4000, 4220, "down")
    holdBetween(4250, 4470, "up")

    local checkpoint = checkpoints[frames]
    if checkpoint ~= nil then
        exportCheckpoint(checkpoint)
    end

    if frames == 4600 then
        local region = tostring(emu.getState()["region"])
        print(
            "POKEMON_OVERWORLD_GRAPHICS_PASS mapper=163 region=" ..
            region .. " checkpoints=6"
        )
        emu.stop(0)
    end
end, emu.eventType.endFrame)
