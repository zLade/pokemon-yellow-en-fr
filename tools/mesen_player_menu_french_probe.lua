-- Validate and export the in-game player menu for the selected locale.
--
-- The labels are pre-rendered NES 2bpp graphics, not ASCII strings. This
-- probe reaches the bedroom without RAM injection, opens the player menu,
-- verifies exact live CHR-RAM checksums and checks that the original tilemap
-- geometry is still intact.  The default remains the historical French
-- contract; the English wrapper selects the untouched ITEMS/Ash/HMs/SAVE
-- assets from the pinned English base.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local menuProfile =
    rawget(_G, "POKEMON_PLAYER_MENU_PROFILE") or "fr-FR"
if menuProfile ~= "fr-FR" and menuProfile ~= "en-US" then
    error("unsupported player-menu profile: " .. tostring(menuProfile))
end
local outputPrefix = menuProfile == "en-US"
    and "player_menu_en"
    or "player_menu_fr"
local PASS_MARKER = menuProfile == "en-US"
    and "POKEMON_PLAYER_MENU_EN_PASS"
    or "POKEMON_PLAYER_MENU_FR_PASS"
local FAIL_MARKER = menuProfile == "en-US"
    and "POKEMON_PLAYER_MENU_EN_FAIL"
    or "POKEMON_PLAYER_MENU_FR_FAIL"
local expectedFullChrChecksum = menuProfile == "en-US"
    and 0xF90379C3
    or 0xA9254C19

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

local labels = {
    {
        name = "OBJETS",
        topAddress = 0x214C,
        bottomAddress = 0x216C,
        topPayload = { 0x00, 0x00, 0x25, 0x29, 0x2B, 0x2F, 0x00, 0x00 },
        bottomPayload = { 0x00, 0x00, 0x26, 0x2A, 0x2C, 0x30, 0x00, 0x00 },
        tileIds = { 0x25, 0x29, 0x2B, 0x2F, 0x26, 0x2A, 0x2C, 0x30 },
        expectedChecksum = 0x3B1833B2,
    },
    {
        name = "SACHA",
        topAddress = 0x21CC,
        bottomAddress = 0x21EC,
        topPayload = { 0x00, 0x00, 0x00, 0x31, 0x33, 0x35, 0x00, 0x00 },
        bottomPayload = { 0x00, 0x00, 0x00, 0x32, 0x34, 0x36, 0x00, 0x00 },
        tileIds = { 0x31, 0x33, 0x35, 0x32, 0x34, 0x36 },
        expectedChecksum = 0xC8B0B2B5,
    },
    {
        name = "CS",
        topAddress = 0x224C,
        bottomAddress = 0x226C,
        topPayload = { 0x00, 0x00, 0x00, 0x4C, 0x4E, 0x5B, 0x00, 0x00 },
        bottomPayload = { 0x00, 0x00, 0x00, 0x4D, 0x4F, 0x5C, 0x00, 0x00 },
        tileIds = { 0x4C, 0x4E, 0x5B, 0x4D, 0x4F, 0x5C },
        expectedChecksum = 0x9557B046,
    },
    {
        name = "SAUVER",
        topAddress = 0x22CC,
        bottomAddress = 0x22EC,
        topPayload = { 0x00, 0x00, 0x5D, 0x7B, 0x7D, 0x84, 0x00, 0x00 },
        bottomPayload = { 0x00, 0x00, 0x5E, 0x7C, 0x7E, 0x85, 0x00, 0x00 },
        tileIds = { 0x5D, 0x7B, 0x7D, 0x84, 0x5E, 0x7C, 0x7E, 0x85 },
        expectedChecksum = 0x4AC79629,
    },
}

if menuProfile == "en-US" then
    labels = {
        {
            name = "ITEMS",
            topAddress = 0x214C,
            bottomAddress = 0x216C,
            topPayload = { 0x00, 0x00, 0x25, 0x29, 0x2B, 0x2F, 0x00, 0x00 },
            bottomPayload = { 0x00, 0x00, 0x26, 0x2A, 0x2C, 0x30, 0x00, 0x00 },
            tileIds = { 0x25, 0x29, 0x2B, 0x2F, 0x26, 0x2A, 0x2C, 0x30 },
            expectedChecksum = 0xF02F0CD5,
        },
        {
            name = "Ash",
            topAddress = 0x21CC,
            bottomAddress = 0x21EC,
            topPayload = { 0x00, 0x00, 0x00, 0x31, 0x33, 0x35, 0x00, 0x00 },
            bottomPayload = { 0x00, 0x00, 0x00, 0x32, 0x34, 0x36, 0x00, 0x00 },
            tileIds = { 0x31, 0x33, 0x35, 0x32, 0x34, 0x36 },
            expectedChecksum = 0xC4E58A41,
        },
        {
            name = "HMs",
            topAddress = 0x224C,
            bottomAddress = 0x226C,
            topPayload = { 0x00, 0x00, 0x00, 0x4C, 0x4E, 0x5B, 0x00, 0x00 },
            bottomPayload = { 0x00, 0x00, 0x00, 0x4D, 0x4F, 0x5C, 0x00, 0x00 },
            tileIds = { 0x4C, 0x4E, 0x5B, 0x4D, 0x4F, 0x5C },
            expectedChecksum = 0xBB364290,
        },
        {
            name = "SAVE",
            topAddress = 0x22CC,
            bottomAddress = 0x22EC,
            topPayload = { 0x00, 0x00, 0x5D, 0x7B, 0x7D, 0x84, 0x00, 0x00 },
            bottomPayload = { 0x00, 0x00, 0x5E, 0x7C, 0x7E, 0x85, 0x00, 0x00 },
            tileIds = { 0x5D, 0x7B, 0x7D, 0x84, 0x5E, 0x7C, 0x7E, 0x85 },
            expectedChecksum = 0x92B540DA,
        },
    }
end

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

local function writeText(filename, data)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "w"))
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

local function payloadMatches(address, expected)
    for index, value in ipairs(expected) do
        if emu.read(
            address + index - 1,
            emu.memType.nesPpuDebug
        ) ~= value then
            return false
        end
    end
    return true
end

local function tileChecksum(tileIds)
    local hash = 0
    for _, tileId in ipairs(tileIds) do
        local first = tileId * 16
        for address = first, first + 15 do
            hash = (
                hash * 257 +
                emu.read(address, emu.memType.nesChrRam)
            ) % 0x100000000
        end
    end
    return hash
end

local function fullChrChecksum()
    local hash = 0
    for address = 0x0000, 0x1FFF do
        hash = (
            hash * 257 +
            emu.read(address, emu.memType.nesChrRam)
        ) % 0x100000000
    end
    return hash
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
    pulseAt(4900, "start", 4)

    if frames ~= 5200 then
        return
    end

    local failures = {}
    local report = {}
    for _, label in ipairs(labels) do
        local checksum = tileChecksum(label.tileIds)
        local topMatches = payloadMatches(
            label.topAddress,
            label.topPayload
        )
        local bottomMatches = payloadMatches(
            label.bottomAddress,
            label.bottomPayload
        )
        report[#report + 1] = string.format(
            "%s checksum=%08X expected=%08X top=%s bottom=%s",
            label.name,
            checksum,
            label.expectedChecksum,
            tostring(topMatches),
            tostring(bottomMatches)
        )
        if checksum ~= label.expectedChecksum then
            failures[#failures + 1] = string.format(
                "%s CHR %08X != %08X",
                label.name,
                checksum,
                label.expectedChecksum
            )
        end
        if not topMatches or not bottomMatches then
            failures[#failures + 1] = label.name .. " tilemap mismatch"
        end
    end

    local chrChecksum = fullChrChecksum()
    if chrChecksum ~= expectedFullChrChecksum then
        failures[#failures + 1] = string.format(
            "full CHR %08X != %08X",
            chrChecksum,
            expectedFullChrChecksum
        )
    end

    local screenshot = emu.takeScreenshot()
    if #screenshot < 1000 then
        failures[#failures + 1] = "screenshot PNG unexpectedly small"
    end

    writeBinary(outputPrefix .. "_screen.png", screenshot)
    writeBinary(
        outputPrefix .. "_chr_ram_8k.bin",
        memoryBytes(emu.memType.nesChrRam, 0x0000, 0x1FFF)
    )
    writeBinary(
        outputPrefix .. "_nametable_4k.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
    )
    writeBinary(
        outputPrefix .. "_palette_32.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x3F00, 0x3F1F)
    )
    writeText(
        outputPrefix .. "_validation.txt",
        table.concat(report, "\n") .. "\n" ..
        string.format("fullChrChecksum=%08X\n", chrChecksum) ..
        "sameFrameAssets=true\n"
    )

    local state = emu.getState()
    if #failures == 0 then
        print(string.format(
            PASS_MARKER .. " mapper=163 region=%s " ..
            "frames=%d labels=4 chr=%08X sameFrameAssets=true",
            tostring(state["region"]),
            frames,
            chrChecksum
        ))
        emu.stop(0)
    else
        print(
            FAIL_MARKER .. " mapper=163 region=" ..
            tostring(state["region"]) .. " " ..
            table.concat(failures, "; ")
        )
        emu.stop(1)
    end
end, emu.eventType.endFrame)
