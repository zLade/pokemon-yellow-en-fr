-- Export the live CHR-RAM/nametable state for manual graphics work.
--
-- Two stable states are captured from an isolated new game: the title and
-- the NEW/LOAD menu.  Raw dumps are kept alongside screenshots; the Python
-- title_screen_tools.py render-dump command converts them to editable BMP
-- tile sheets and rendered nametables.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local lastOamDmaPage = nil
local titleCaptured = false
local titleStableFrames = 0
local titleSignature = nil
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

local function writeText(filename, data)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "w"))
    file:write(data)
    file:close()
end

local function checksum(memoryType, first, last)
    local hash = 0
    for address = first, last do
        hash = (hash * 257 + emu.read(address, memoryType)) % 0x100000000
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
    -- Screenshots include 8 pixels of vertical overscan.  (0, 0) is black,
    -- so sample the actual green backdrop inside the visible playfield.
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

    -- Both the logo and Pikachu must have reached the framebuffer, not only
    -- the static nametable/CHR state behind a partially drawn strict boot.
    local logoPixel = emu.getPixel(128, 64)
    local pikachuPixel = emu.getPixel(128, 145)
    return interior ~= background and
           logoPixel ~= background and logoPixel ~= interior and
           pikachuPixel ~= background and pikachuPixel ~= interior
end

local function scalarStateDump()
    local state = emu.getState()
    local keys = {}
    for key, value in pairs(state) do
        local valueType = type(value)
        if valueType == "number" or
           valueType == "string" or
           valueType == "boolean" then
            keys[#keys + 1] = key
        end
    end
    table.sort(keys)

    local lines = {}
    for _, key in ipairs(keys) do
        lines[#lines + 1] = key .. "=" .. tostring(state[key])
    end
    return table.concat(lines, "\n") .. "\n"
end

local function exportState(prefix, screenshot)
    writeBinary(
        prefix .. "_chr_ram_8k.bin",
        memoryBytes(emu.memType.nesChrRam, 0x0000, 0x1FFF)
    )
    writeBinary(
        prefix .. "_ppu_pattern_8k.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x0000, 0x1FFF)
    )
    writeBinary(
        prefix .. "_nametable_4k.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
    )
    writeBinary(
        prefix .. "_palette_32.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x3F00, 0x3F1F)
    )
    writeBinary(
        prefix .. "_oam_256.bin",
        memoryBytes(emu.memType.nesSpriteRam, 0x00, 0xFF)
    )
    if lastOamDmaPage ~= nil then
        local first = lastOamDmaPage * 0x100
        writeBinary(
            prefix .. "_oam_shadow_256.bin",
            memoryBytes(emu.memType.nesDebug, first, first + 0xFF)
        )
        writeText(
            prefix .. "_oam_dma_page.txt",
            string.format("$%02X\n", lastOamDmaPage)
        )
    end
    writeText(prefix .. "_mesen_state.txt", scalarStateDump())
    writeBinary(
        prefix .. "_screen.png",
        screenshot or emu.takeScreenshot()
    )
    writeText(
        prefix .. "_capture_frame.txt",
        "frame=" .. tostring(frames) .. "\n" ..
        "same_frame_assets=true\n"
    )
    print("POKEMON_CHR_EXPORT state=" .. prefix .. " frame=" .. tostring(frames))
end

local function titleTilemapIsPresent()
    return emu.read(0x204E, emu.memType.nesPpuDebug) == 0x40 and
           emu.read(0x206F, emu.memType.nesPpuDebug) == 0x30 and
           emu.read(0x2169, emu.memType.nesPpuDebug) == 0x31 and
           emu.read(0x216A, emu.memType.nesPpuDebug) == 0x32 and
           emu.read(0x2189, emu.memType.nesPpuDebug) == 0x41 and
           emu.read(0x218A, emu.memType.nesPpuDebug) == 0x42 and
           emu.read(0x218B, emu.memType.nesPpuDebug) == 0x43
end

local function menuTilemapIsPresent()
    return titleTilemapIsPresent() and
           emu.read(0x2267, emu.memType.nesPpuDebug) == 0x30 and
           emu.read(0x2268, emu.memType.nesPpuDebug) == 0x31 and
           emu.read(0x2269, emu.memType.nesPpuDebug) == 0x32 and
           emu.read(0x22A7, emu.memType.nesPpuDebug) == 0x40 and
           emu.read(0x22A8, emu.memType.nesPpuDebug) == 0x41 and
           emu.read(0x22A9, emu.memType.nesPpuDebug) == 0x42 and
           emu.read(0x22AA, emu.memType.nesPpuDebug) == 0x43
end

emu.addMemoryCallback(function(_, value)
    lastOamDmaPage = value
end, emu.callbackType.write, 0x4014, 0x4014)

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
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
       titleTilemapIsPresent() and
       not menuTilemapIsPresent() and
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
            exportState("title", screenshot)
            titleCaptured = true
            startPressFrame = frames + 30
        end
    end

    if titleCaptured and
       menuTilemapIsPresent() and
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
        if menuStableFrames >= 3 and not finished then
            finished = true
            exportState("new_load_menu_stable", screenshot)
            print(
                "POKEMON_CHR_EXPORT_PASS mapper=163 region=" ..
                tostring(state["region"]) ..
                " states=2 titleFrame=" ..
                tostring(startPressFrame - 30) ..
                " menuFrame=" .. tostring(frames) ..
                " sameFrameAssets=true visualContract=true"
            )
            emu.stop(0)
            return
        end
    end

    if frames == 1200 then
        print(
            "POKEMON_CHR_EXPORT_FAIL mapper=163 region=" ..
            tostring(state["region"]) ..
            " titleCaptured=" .. tostring(titleCaptured) ..
            " titleStableFrames=" .. tostring(titleStableFrames) ..
            " menuStableFrames=" .. tostring(menuStableFrames)
        )
        emu.stop(1)
    end
end, emu.eventType.endFrame)
