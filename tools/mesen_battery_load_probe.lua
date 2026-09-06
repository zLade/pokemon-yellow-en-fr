-- Second-process battery/load probe for Pokemon Yellow NES (mapper 163).
--
-- The save-data directory is reused from mesen_battery_create_probe.lua.
-- This probe exports SRAM before any controller input, selects CONT and
-- captures the resumed room.  The PowerShell suite compares the exported
-- bytes with the closed first-process .sav, then compares both room images.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local screenshotCount = 0
local initialSram = nil
local menuHash = nil
local resumedHash = nil
local resumedConfirmationHash = nil
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

local function writeBinary(filename, data)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    file:write(data)
    file:close()
end

local function checksum(data)
    local hash = 0
    for index = 1, #data do
        hash = (hash * 257 + string.byte(data, index)) % 0x100000000
    end
    return hash
end

local function pulseAt(frame, button, duration)
    if frames == frame then
        desiredInput[button] = true
    elseif frames == frame + duration then
        desiredInput[button] = false
    end
end

initialSram = saveRamBytes()
writeBinary("battery_load_initial_sram.bin", initialSram)

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1
    pulseAt(180, "start", 4)
    pulseAt(420, "down", 4)
    pulseAt(540, "a", 4)

    if frames == 480 then
        menuHash = saveScreenshot("battery_load_cont_selected.png")
    elseif frames == 720 then
        resumedHash = saveScreenshot("battery_load_after_cont.png")
    elseif frames == 1000 then
        resumedConfirmationHash = saveScreenshot(
            "battery_load_resumed_room.png"
        )
    end

    if frames ~= 1000 then
        return
    end

    writeBinary("battery_load_final_sram.bin", saveRamBytes())
    local failures = {}
    if screenshotCount ~= 3 then
        table.insert(
            failures,
            "missing screenshots: " .. tostring(screenshotCount) .. "/3"
        )
    end
    if resumedHash == nil or resumedHash ~= resumedConfirmationHash then
        table.insert(failures, "CONT did not resume into a stable screen")
    end
    if menuHash == resumedHash then
        table.insert(failures, "CONT did not leave the title menu")
    end

    if #failures == 0 then
        print(string.format(
            "POKEMON_BATTERY_LOAD_PASS mapper=163 region=%s frames=%d " ..
            "initialSram=%08X stableResume=%08X screenshots=%d",
            tostring(emu.getState()["region"]), frames,
            checksum(initialSram), resumedHash, screenshotCount
        ))
        emu.stop(0)
    else
        print("POKEMON_BATTERY_LOAD_FAIL " .. table.concat(failures, "; "))
        emu.stop(1)
    end
end, emu.eventType.endFrame)
