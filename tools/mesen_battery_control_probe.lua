-- Fresh-save control for Pokemon Yellow NES (mapper 163) under Mesen 2.2.1.
--
-- The PowerShell battery suite launches this probe with a brand-new isolated
-- save-data directory.  It exports the initial 8 KiB SRAM image, opens the
-- title menu and exercises the CONT path once for visual evidence.  With no
-- valid save, CONT must fall back to the Professor/new-game introduction.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local screenshotCount = 0
local screenshotHashes = {}
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
    screenshotHashes[hash] = true
end

local function pulseAt(frame, button, duration)
    if frames == frame then
        desiredInput[button] = true
    elseif frames == frame + duration then
        desiredInput[button] = false
    end
end

writeBinary("battery_control_initial_sram.bin", saveRamBytes())

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1
    pulseAt(180, "start", 4)
    pulseAt(300, "down", 4)
    pulseAt(360, "a", 4)

    if frames == 330 then
        saveScreenshot("battery_control_cont_selected.png")
    elseif frames == 480 then
        saveScreenshot("battery_control_after_cont.png")
    elseif frames == 720 then
        saveScreenshot("battery_control_final.png")
    end

    if frames ~= 720 then
        return
    end

    if screenshotCount ~= 3 then
        print(
            "POKEMON_BATTERY_CONTROL_FAIL screenshots=" ..
            tostring(screenshotCount)
        )
        emu.stop(1)
        return
    end
    local distinctScreens = 0
    for _ in pairs(screenshotHashes) do
        distinctScreens = distinctScreens + 1
    end
    if distinctScreens ~= 3 then
        print(
            "POKEMON_BATTERY_CONTROL_FAIL fresh CONT did not " ..
            "progress into new-game introduction"
        )
        emu.stop(1)
        return
    end

    print(string.format(
        "POKEMON_BATTERY_CONTROL_PASS mapper=163 region=%s frames=%d " ..
        "freshSaveData=true fallback=new-game screenshots=%d distinct=%d",
        tostring(emu.getState()["region"]), frames, screenshotCount,
        distinctScreens
    ))
    emu.stop(0)
end, emu.eventType.endFrame)
