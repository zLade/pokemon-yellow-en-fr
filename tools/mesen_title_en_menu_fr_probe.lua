-- Validate the English YELLOW title label and the French NOUV/CONT menu.
--
-- Mapper 163 loads the title graphics into CHR-RAM and swaps the physical
-- 4 KiB halves at scanline 127.  This probe therefore checks the exact live
-- CHR bytes, not only the ROM source or a generic screenshot contract.
-- It uses controller input only and captures each screen together with its
-- CHR-RAM, nametable and palette from the same end-of-frame callback.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local function bytesFromHex(value)
    if #value % 2 ~= 0 then
        error("hex payload must contain an even number of characters")
    end
    local bytes = {}
    for index = 1, #value, 2 do
        bytes[#bytes + 1] = tonumber(value:sub(index, index + 1), 16)
    end
    return bytes
end

-- English YELLOW tiles from Pokemon Yellow English 9-23-2015.nes.
-- They are loaded in live CHR-RAM pattern table $0000 as IDs $51-$55.
local TITLE_TILES = {
    {
        id = 0x51,
        address = 0x0510,
        bytes = bytesFromHex("0053525257222300FFACADADA8DD5477"),
    },
    {
        id = 0x52,
        address = 0x0520,
        bytes = bytesFromHex("0063545663515600F79CABA99CAEA9FF"),
    },
    {
        id = 0x53,
        address = 0x0530,
        bytes = bytesFromHex("0049555555554900FFB6AAAAAAAAB6FF"),
    },
    {
        id = 0x54,
        address = 0x0540,
        bytes = bytesFromHex("0020A0A060602000F8D858589898D8F8"),
    },
    {
        id = 0x55,
        address = 0x0550,
        bytes = bytesFromHex("0F030000000000001C07010000000000"),
    },
}

-- French condensed NOUV/CONT tiles.  The source lives in the second
-- physical 4 KiB half and is visible live at $1300-$132F/$1400-$143F.
local MENU_TILES = {
    {
        id = 0x30,
        address = 0x1300,
        bytes = bytesFromHex("0089CAAA9A8A89000089CAAA9A8A8900"),
    },
    {
        id = 0x31,
        address = 0x1310,
        bytes = bytesFromHex("00C828282828C70000C828282828C700"),
    },
    {
        id = 0x32,
        address = 0x1320,
        bytes = bytesFromHex("00A2A2A2A294080000A2A2A2A2940800"),
    },
    {
        id = 0x40,
        address = 0x1400,
        bytes = bytesFromHex("003C666060663C00003C666060663C00"),
    },
    {
        id = 0x41,
        address = 0x1410,
        bytes = bytesFromHex("003C666666663C00003C666666663C00"),
    },
    {
        id = 0x42,
        address = 0x1420,
        bytes = bytesFromHex("006676767E6E6600006676767E6E6600"),
    },
    {
        id = 0x43,
        address = 0x1430,
        bytes = bytesFromHex("007E181818181800007E181818181800"),
    },
}

-- Poké Ball cursor used by NEW/LOAD.  It is a sprite, so it never appears in
-- the background nametables used to select the credit tile IDs.
local MENU_CURSOR_TILES = {
    {
        id = 0xA3,
        address = 0x1A30,
        bytes = bytesFromHex("001C2241415F2E1C00001C363E1E0C00"),
    },
}

local FRENCH_BOTTOM_TITLE_TILES = {
    { id = 0x81, address = 0x1810, bytes = bytesFromHex("FF83EFEFEFAFCFFFFF8300000000CFFF") },
    { id = 0x82, address = 0x1820, bytes = bytesFromHex("FFC7BBBB83BBBBFFFFC700000000BBFF") },
    { id = 0x83, address = 0x1830, bytes = bytesFromHex("FFBBBBBBBBBBC7FFFFBB00000000C7FF") },
    { id = 0x7F, address = 0x17F0, bytes = bytesFromHex("FFBB9BABB3BBBBFFFFBB00000000BBFF") },
    { id = 0x84, address = 0x1840, bytes = bytesFromHex("FF83BF87BFBF83FFFF830000000083FF") },
}

local FRENCH_BOTTOM_TITLE_TILEMAP = {
    0x8E, 0x8E, 0x8E, 0x8E, 0x8E,
    0x81, 0x8E, 0x82, 0x8E, 0x83, 0x8E, 0x7F, 0x8E, 0x84,
    0x8E, 0x8E, 0x8E, 0x8E, 0x8E, 0x8E,
}

local TITLE_TILEMAP = {
    { address = 0x21A9, value = 0x51 },
    { address = 0x21AA, value = 0x52 },
    { address = 0x21AB, value = 0x53 },
    { address = 0x21AC, value = 0x54 },
    { address = 0x21AD, value = 0x55 },
}

local MENU_TILEMAP = {
    { address = 0x2267, value = 0x30 },
    { address = 0x2268, value = 0x31 },
    { address = 0x2269, value = 0x32 },
    { address = 0x22A7, value = 0x40 },
    { address = 0x22A8, value = 0x41 },
    { address = 0x22A9, value = 0x42 },
    { address = 0x22AA, value = 0x43 },
}

local frames = 0
local titleCaptured = false
local titleStableFrames = 0
local titleSignature = nil
local titleCaptureFrame = nil
local startPressFrame = nil
local menuStableFrames = 0
local menuSignature = nil
local finished = false
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

local function checksum(memoryType, first, last)
    local hash = 0
    for address = first, last do
        hash = (
            hash * 257 + emu.read(address, memoryType)
        ) % 0x100000000
    end
    return hash
end

local function graphicsSignature()
    return string.format(
        "%08X:%08X:%08X",
        checksum(emu.memType.nesChrRam, 0x0000, 0x1FFF),
        checksum(emu.memType.nesPpuDebug, 0x2000, 0x2FFF),
        checksum(emu.memType.nesPpuDebug, 0x3F00, 0x3F1F)
    )
end

local function renderedTitleContract()
    local background = emu.getPixel(16, 16)
    local interior = emu.getPixel(50, 50)
    local framePoints = {
        { 40, 40 },
        { 215, 40 },
        { 40, 198 },
        { 215, 198 },
    }
    for _, point in ipairs(framePoints) do
        if emu.getPixel(point[1], point[2]) == background then
            return false
        end
    end

    local logoPixel = emu.getPixel(128, 64)
    local pikachuPixel = emu.getPixel(128, 145)
    return interior ~= background and
           logoPixel ~= background and logoPixel ~= interior and
           pikachuPixel ~= background and pikachuPixel ~= interior
end

local function baseTitleTilemapIsPresent()
    return emu.read(0x204E, emu.memType.nesPpuDebug) == 0x40 and
           emu.read(0x206F, emu.memType.nesPpuDebug) == 0x30 and
           emu.read(0x2169, emu.memType.nesPpuDebug) == 0x31 and
           emu.read(0x216A, emu.memType.nesPpuDebug) == 0x32 and
           emu.read(0x2189, emu.memType.nesPpuDebug) == 0x41 and
           emu.read(0x218A, emu.memType.nesPpuDebug) == 0x42 and
           emu.read(0x218B, emu.memType.nesPpuDebug) == 0x43
end

local function menuSceneIsPresent()
    if not baseTitleTilemapIsPresent() then
        return false
    end
    -- The untouched title uses blank tile $5F at both menu anchors.  Detect
    -- the menu without requiring its exact payload so validation can report
    -- a precise tilemap mismatch instead of eventually timing out.
    return emu.read(0x2267, emu.memType.nesPpuDebug) ~= 0x5F and
           emu.read(0x22A7, emu.memType.nesPpuDebug) ~= 0x5F
end

local function appendExactTileResults(tiles, label, failures, report)
    for _, tile in ipairs(tiles) do
        local exact = true
        local mismatch = nil
        for index, expected in ipairs(tile.bytes) do
            local address = tile.address + index - 1
            local actual = emu.read(address, emu.memType.nesChrRam)
            if actual ~= expected then
                exact = false
                mismatch = string.format(
                    "%s tile=$%02X address=$%04X actual=$%02X expected=$%02X",
                    label,
                    tile.id,
                    address,
                    actual,
                    expected
                )
                break
            end
        end
        report[#report + 1] = string.format(
            "%s tile=$%02X live=$%04X exact=%s",
            label,
            tile.id,
            tile.address,
            tostring(exact)
        )
        if mismatch ~= nil then
            failures[#failures + 1] = mismatch
        end
    end
end

local function appendExactTilemapResults(entries, label, failures, report)
    for _, entry in ipairs(entries) do
        local actual = emu.read(entry.address, emu.memType.nesPpuDebug)
        local exact = actual == entry.value
        report[#report + 1] = string.format(
            "%s address=$%04X actual=$%02X expected=$%02X exact=%s",
            label,
            entry.address,
            actual,
            entry.value,
            tostring(exact)
        )
        if not exact then
            failures[#failures + 1] = string.format(
                "%s address=$%04X actual=$%02X expected=$%02X",
                label,
                entry.address,
                actual,
                entry.value
            )
        end
    end
end

local function validateGraphics(includeMenu)
    local failures = {}
    local report = {}
    appendExactTileResults(
        TITLE_TILES,
        "title_en",
        failures,
        report
    )
    appendExactTilemapResults(
        TITLE_TILEMAP,
        "title_en_tilemap",
        failures,
        report
    )
    if includeMenu then
        appendExactTileResults(
            MENU_TILES,
            "menu_fr",
            failures,
            report
        )
        appendExactTilemapResults(
            MENU_TILEMAP,
            "menu_fr_tilemap",
            failures,
            report
        )
        appendExactTileResults(
            MENU_CURSOR_TILES,
            "menu_cursor",
            failures,
            report
        )
        appendExactTileResults(
            FRENCH_BOTTOM_TITLE_TILES,
            "bottom_title_jaune",
            failures,
            report
        )
        local bottomTitleTilemap = {}
        for index, value in ipairs(FRENCH_BOTTOM_TITLE_TILEMAP) do
            bottomTitleTilemap[index] = {
                address = 0x2306 + index - 1,
                value = value,
            }
        end
        appendExactTilemapResults(
            bottomTitleTilemap,
            "bottom_title_jaune_tilemap",
            failures,
            report
        )
        local cursorSprite = false
        for address = 0, 252, 4 do
            local y = emu.read(address, emu.memType.nesSpriteRam)
            local tile = emu.read(address + 1, emu.memType.nesSpriteRam)
            if tile == 0xA3 and y < 239 then
                cursorSprite = true
                break
            end
        end
        report[#report + 1] = "menu_cursor_oam=" .. tostring(cursorSprite)
        if not cursorSprite then
            failures[#failures + 1] = "menu cursor tile $A3 absent from visible OAM"
        end
    end
    report[#report + 1] = "sameFrameAssets=true"
    return failures, report
end

local function exportState(prefix, screenshot, report)
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
    writeBinary(prefix .. "_screen.png", screenshot)
    writeText(
        prefix .. "_validation.txt",
        table.concat(report, "\n") .. "\n" ..
        "frame=" .. tostring(frames) .. "\n"
    )
    print(
        "TITLE_EN_MENU_FR_CAPTURE state=" .. prefix ..
        " frame=" .. tostring(frames) ..
        " sameFrameAssets=true"
    )
end

local function fail(stage, failures, report, screenshot)
    if finished then
        return
    end
    finished = true
    desiredInput.start = false
    writeBinary(
        "title_en_menu_fr_failure_screen.png",
        screenshot or emu.takeScreenshot()
    )
    writeText(
        "title_en_menu_fr_failure.txt",
        table.concat(report or {}, "\n") .. "\n" ..
        table.concat(failures or {}, "\n") .. "\n"
    )
    local state = emu.getState()
    print(
        "TITLE_EN_MENU_FR_FAIL mapper=163 region=" ..
        tostring(state["region"]) ..
        " frame=" .. tostring(frames) ..
        " stage=" .. tostring(stage) ..
        " reason=" .. table.concat(failures or {}, " | ")
    )
    emu.stop(1)
end

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if finished then
        return
    end

    frames = frames + 1
    if startPressFrame ~= nil and frames == startPressFrame then
        desiredInput.start = true
    elseif startPressFrame ~= nil and frames == startPressFrame + 4 then
        desiredInput.start = false
    end

    local state = emu.getState()
    local rendering = state["ppu.mask.backgroundEnabled"] and
        state["ppu.mask.spritesEnabled"]

    if not titleCaptured and
       frames >= 60 and
       rendering and
       baseTitleTilemapIsPresent() and
       not menuSceneIsPresent() and
       renderedTitleContract() then
        local screenshot = emu.takeScreenshot()
        local signature = graphicsSignature()
        if signature == titleSignature then
            titleStableFrames = titleStableFrames + 1
        else
            titleSignature = signature
            titleStableFrames = 1
        end
        if titleStableFrames >= 3 then
            local failures, report = validateGraphics(false)
            if #failures ~= 0 then
                fail("title_en", failures, report, screenshot)
                return
            end
            titleCaptureFrame = frames
            exportState("title_en", screenshot, report)
            titleCaptured = true
            startPressFrame = frames + 30
        end
    end

    if titleCaptured and
       menuSceneIsPresent() and
       rendering and
       renderedTitleContract() then
        local screenshot = emu.takeScreenshot()
        local signature = graphicsSignature()
        if signature == menuSignature then
            menuStableFrames = menuStableFrames + 1
        else
            menuSignature = signature
            menuStableFrames = 1
        end
        if menuStableFrames >= 3 then
            local failures, report = validateGraphics(true)
            if #failures ~= 0 then
                fail("menu_fr", failures, report, screenshot)
                return
            end
            exportState("title_menu_fr", screenshot, report)
            finished = true
            desiredInput.start = false
            print(string.format(
                "TITLE_EN_MENU_FR_PASS mapper=163 region=%s " ..
                "frames=%d titleFrame=%d menuFrame=%d " ..
                "titleTiles=5 menuTiles=7 sameFrameAssets=true",
                tostring(state["region"]),
                frames,
                titleCaptureFrame,
                frames
            ))
            emu.stop(0)
            return
        end
    end

    if frames == 1200 then
        fail(
            "timeout",
            {
                "titleCaptured=" .. tostring(titleCaptured),
                "titleStableFrames=" .. tostring(titleStableFrames),
                "menuStableFrames=" .. tostring(menuStableFrames),
            },
            {},
            emu.takeScreenshot()
        )
    end
end, emu.eventType.endFrame)
