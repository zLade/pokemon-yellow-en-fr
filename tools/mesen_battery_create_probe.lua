-- Create a real in-game battery save for Pokemon Yellow NES (mapper 163).
--
-- This script drives the title/new-game flow with controller input, opens the
-- player menu after the introduction and asks the game to save.  No RAM is
-- injected: the suite validates the resulting 8 KiB .sav bit-for-bit in a
-- second Mesen process.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local saveRamWrites = 0
local screenshotCount = 0
local beforeSave = nil
local roomHash = nil
local roomConfirmationHash = nil
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

local captures = {
    [1000] = "battery_create_1000.png",
    [2000] = "battery_create_2000.png",
    [3000] = "battery_create_3000.png",
    [4000] = "battery_create_4000.png",
    [4800] = "battery_create_4800.png",
    [5200] = "battery_create_5200.png",
    [5750] = "battery_create_save_selected.png",
    [6000] = "battery_create_save_activated.png",
    [6300] = "battery_create_save_settled.png",
}

local function saveScreenshot(filename)
    local png = emu.takeScreenshot()
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    file:write(png)
    file:close()
    screenshotCount = screenshotCount + 1
    local hash = 0
    for index = 1, #png do
        hash = (hash * 257 + string.byte(png, index)) % 0x100000000
    end
    return hash
end

local function saveRamBytes()
    local bytes = {}
    for address = 0x6000, 0x7FFF do
        bytes[#bytes + 1] = string.char(
            emu.read(address, emu.memType.nesMemory)
        )
    end
    return table.concat(bytes)
end

local function checksum(data)
    local hash = 0
    for index = 1, #data do
        hash = (hash * 257 + string.byte(data, index)) % 0x100000000
    end
    return hash
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

local function pulseAt(frame, button, duration)
    if frames == frame then
        desiredInput[button] = true
    elseif frames == frame + duration then
        desiredInput[button] = false
    end
end

emu.addMemoryCallback(function()
    saveRamWrites = saveRamWrites + 1
end, emu.callbackType.write, 0x6000, 0x7FFF)

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1
    pulseAt(180, "start", 4)

    -- Select NOUV and advance all introduction/name prompts.
    for pulseFrame = 360, 4500, 30 do
        pulseAt(pulseFrame, "a", 3)
    end

    -- Open the player menu, move to SAVE, activate it and accept any
    -- confirmation at a human-safe cadence.
    pulseAt(4900, "start", 4)
    for pulseFrame = 5300, 5660, 90 do
        pulseAt(pulseFrame, "down", 4)
    end
    pulseAt(5800, "a", 4)
    pulseAt(6100, "a", 4)

    if frames == 5799 then
        beforeSave = saveRamBytes()
    end

    local captureName = captures[frames]
    if captureName ~= nil then
        local captureHash = saveScreenshot(captureName)
        if frames == 4000 then
            roomHash = captureHash
        elseif frames == 4800 then
            roomConfirmationHash = captureHash
        elseif frames == 5750 then
            -- Same-frame raw assets for manual review/editing of any menu
            -- labels that are stored as tile IDs rather than ASCII.
            writeBinary(
                "battery_create_player_menu_chr_ram_8k.bin",
                memoryBytes(emu.memType.nesChrRam, 0x0000, 0x1FFF)
            )
            writeBinary(
                "battery_create_player_menu_nametable_4k.bin",
                memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
            )
            writeBinary(
                "battery_create_player_menu_palette_32.bin",
                memoryBytes(emu.memType.nesPpuDebug, 0x3F00, 0x3F1F)
            )
            writeBinary(
                "battery_create_player_menu_oam_256.bin",
                memoryBytes(emu.memType.nesSpriteRam, 0x00, 0xFF)
            )
        end
    end

    if frames ~= 6400 then
        return
    end

    local afterSave = saveRamBytes()
    writeBinary("battery_create_sram_before_save.bin", beforeSave)
    writeBinary("battery_create_sram_after_save.bin", afterSave)

    if roomHash == nil or roomHash ~= roomConfirmationHash then
        print(
            "POKEMON_BATTERY_CREATE_FAIL new-game room was not stable " ..
            "before opening SAVE"
        )
        emu.stop(1)
        return
    end
    if saveRamWrites < 1 then
        print("POKEMON_BATTERY_CREATE_FAIL no battery RAM writes observed")
        emu.stop(1)
        return
    end

    print(string.format(
        "POKEMON_BATTERY_CREATE_PASS mapper=163 region=%s frames=%d " ..
        "saveRamWrites=%d beforeSave=%08X afterSave=%08X " ..
        "stableRoom=%08X screenshots=%d",
        tostring(emu.getState()["region"]), frames, saveRamWrites,
        checksum(beforeSave), checksum(afterSave), roomHash, screenshotCount
    ))
    emu.stop(0)
end, emu.eventType.endFrame)
