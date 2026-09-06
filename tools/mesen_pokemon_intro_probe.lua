-- Functional new-game/intro probe for Pokemon Yellow NES (mapper 163).
--
-- The run starts with isolated battery RAM (configured by the PowerShell
-- runner), captures the title, presses Start, then advances the early dialog
-- with short A-button pulses.  It intentionally uses only controller input:
-- no game RAM addresses or mapper registers are forced.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local nmiCount = 0
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

local captures = {
    [150] = "intro_0150_title.png",
    [300] = "intro_0300_after_start.png",
    [480] = "intro_0480.png",
    [660] = "intro_0660.png",
    [840] = "intro_0840.png",
    [1020] = "intro_1020.png",
    [1200] = "intro_1200.png",
    [1440] = "intro_1440.png",
    [1680] = "intro_1680.png",
    [1920] = "intro_1920.png",
}

local function byteStringHash(data)
    local hash = 0
    for index = 1, #data do
        hash = (hash * 257 + string.byte(data, index)) % 0x100000000
    end
    return hash
end

local function saveScreenshot(filename)
    local png = emu.takeScreenshot()
    local path = outputDirectory .. "\\" .. filename
    local file = assert(io.open(path, "wb"))
    file:write(png)
    file:close()
    local hash = byteStringHash(png)
    screenshotHashes[hash] = true
    screenshotCount = screenshotCount + 1
    local nametable = {}
    for address = 0x2000, 0x2FFF do
        nametable[#nametable + 1] = string.char(
            emu.read(address, emu.memType.nesPpuDebug)
        )
    end
    local nametablePath = outputDirectory .. "\\" ..
        string.gsub(filename, "%.png$", "_nametable_4k.bin")
    local nametableFile = assert(io.open(nametablePath, "wb"))
    nametableFile:write(table.concat(nametable))
    nametableFile:close()
    local oam = {}
    for address = 0x00, 0xFF do
        oam[#oam + 1] = string.char(
            emu.read(address, emu.memType.nesSpriteRam)
        )
    end
    local oamPath = outputDirectory .. "\\" ..
        string.gsub(filename, "%.png$", "_oam_256.bin")
    local oamFile = assert(io.open(oamPath, "wb"))
    oamFile:write(table.concat(oam))
    oamFile:close()
    print(string.format(
        "POKEMON_INTRO_CAPTURE frame=%d file=%s bytes=%d hash=%08X",
        frames, filename, #png, hash
    ))
end

local function setButton(name, pressed)
    desiredInput[name] = pressed
end

local function pulseAt(frame, button, duration)
    if frames == frame then
        setButton(button, true)
    elseif frames == frame + duration then
        setButton(button, false)
    end
end

emu.addEventCallback(function()
    nmiCount = nmiCount + 1
end, emu.eventType.nmi)

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1

    pulseAt(180, "start", 4)
    -- Advance early dialog/menus at a human-safe cadence.
    for pulseFrame = 360, 1860, 90 do
        pulseAt(pulseFrame, "a", 3)
    end

    local captureName = captures[frames]
    if captureName ~= nil then
        saveScreenshot(captureName)
    end

    if frames ~= 1920 then
        return
    end

    local distinctScreens = 0
    for _ in pairs(screenshotHashes) do
        distinctScreens = distinctScreens + 1
    end
    local failures = {}
    if nmiCount < 1500 then
        table.insert(failures, "too few NMIs: " .. tostring(nmiCount))
    end
    if screenshotCount ~= 10 then
        table.insert(
            failures,
            "missing screenshots: " .. tostring(screenshotCount) .. "/10"
        )
    end
    if distinctScreens < 5 then
        table.insert(
            failures,
            "intro did not progress: distinct screens=" ..
            tostring(distinctScreens)
        )
    end

    if #failures == 0 then
        local region = tostring(emu.getState()["region"])
        print(string.format(
            "POKEMON_INTRO_PASS mapper=163 region=%s frames=%d nmi=%d screenshots=%d distinct=%d",
            region, frames, nmiCount, screenshotCount, distinctScreens
        ))
        emu.stop(0)
    else
        print("POKEMON_INTRO_FAIL " .. table.concat(failures, "; "))
        emu.stop(1)
    end
end, emu.eventType.endFrame)
