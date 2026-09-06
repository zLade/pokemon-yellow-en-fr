-- Read-only discovery probe for a future full-campaign controller bot.
--
-- The script reaches the bedroom through normal controller input, records
-- internal RAM/SRAM/OAM snapshots while walking, and attempts the first warp.
-- It does not inject RAM or modify the ROM.

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
    [4700] = "00_bedroom_idle",
    [4740] = "01_before_right",
    [4772] = "02_right_32",
    [4804] = "03_right_64",
    [4836] = "04_right_96",
    [4868] = "06_right_128_stop",
    [4900] = "07_before_up",
    [4920] = "08_up_20",
    [4940] = "09_up_40",
    [4990] = "10_after_first_warp_attempt",
    [5050] = "11_downstairs_or_room",
    [5150] = "12_after_down",
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
    writeBinary(
        name .. "_ram_2k.bin",
        memoryBytes(emu.memType.nesDebug, 0x0000, 0x07FF)
    )
    writeBinary(
        name .. "_sram_8k.bin",
        memoryBytes(emu.memType.nesDebug, 0x6000, 0x7FFF)
    )
    writeBinary(
        name .. "_oam_256.bin",
        memoryBytes(emu.memType.nesSpriteRam, 0x00, 0xFF)
    )
    writeBinary(name .. "_screen.png", emu.takeScreenshot())
    local state = emu.getState()
    local pc = state["cpu.pc"] or 0
    print(string.format(
        "POKEMON_CAMPAIGN_RAM_CAPTURE frame=%d checkpoint=%s pc=%04X",
        frames,
        name,
        pc
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

    -- The player begins near x=72.  Move to the doorway around x=200,
    -- avoiding the prior exploratory probe's overshoot to x=232.
    holdBetween(4740, 4868, "right")
    holdBetween(4900, 4940, "up")

    -- If the first warp succeeds, try walking down in the next room.
    holdBetween(5070, 5150, "down")

    local checkpoint = checkpoints[frames]
    if checkpoint ~= nil then
        capture(checkpoint)
    end

    if frames == 5190 then
        print(string.format(
            "POKEMON_CAMPAIGN_RAM_DISCOVERY_PASS mapper=163 region=%s checkpoints=%d",
            tostring(emu.getState()["region"]),
            13
        ))
        emu.stop(0)
    end
end, emu.eventType.endFrame)
