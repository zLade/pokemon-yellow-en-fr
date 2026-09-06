-- Observe recovery from a deliberately mismatched battery-save pair.
--
-- The PowerShell suite prepares the .sav before Mesen starts.  This probe is
-- intentionally read-only with respect to emulator memory: it only drives
-- the real title-menu CONT path, exports SRAM and captures the settled result.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local saveRamWrites = 0
local screenshotCount = 0
local menuHash = nil
local finalHash = nil
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

local function saveScreenshot(filename)
    local png = emu.takeScreenshot()
    writeBinary(filename, png)
    screenshotCount = screenshotCount + 1
    return checksum(png)
end

local function pulseAt(frame, button, duration)
    if frames == frame then
        desiredInput[button] = true
    elseif frames == frame + duration then
        desiredInput[button] = false
    end
end

local initialSram = saveRamBytes()
writeBinary("battery_corruption_initial_sram.bin", initialSram)

emu.addMemoryCallback(function()
    saveRamWrites = saveRamWrites + 1
end, emu.callbackType.write, 0x6000, 0x7FFF)

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1
    pulseAt(180, "start", 4)
    pulseAt(420, "down", 4)
    pulseAt(540, "a", 4)

    if frames == 480 then
        menuHash = saveScreenshot("battery_corruption_cont_selected.png")
    elseif frames == 1000 then
        finalHash = saveScreenshot("battery_corruption_final.png")
    end

    if frames ~= 1000 then
        return
    end

    local finalSram = saveRamBytes()
    writeBinary("battery_corruption_final_sram.bin", finalSram)
    local failures = {}
    if screenshotCount ~= 2 then
        table.insert(
            failures,
            "missing screenshots: " .. tostring(screenshotCount) .. "/2"
        )
    end
    if finalHash == nil or menuHash == finalHash then
        table.insert(failures, "CONT did not leave the title menu")
    end

    if #failures == 0 then
        print(string.format(
            "POKEMON_BATTERY_CORRUPTION_OBSERVED mapper=163 region=%s " ..
            "frames=%d initialSram=%08X finalSram=%08X stable=%08X " ..
            "saveRamWrites=%d screenshots=%d memoryInjection=false",
            tostring(emu.getState()["region"]), frames,
            checksum(initialSram), checksum(finalSram), finalHash,
            saveRamWrites, screenshotCount
        ))
        emu.stop(0)
    else
        print(
            "POKEMON_BATTERY_CORRUPTION_FAIL " ..
            table.concat(failures, "; ")
        )
        emu.stop(1)
    end
end, emu.eventType.endFrame)
