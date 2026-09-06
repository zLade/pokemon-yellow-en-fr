-- Catalog stable CHR-RAM states reached during a normal new-game sequence.
--
-- The mapper 163 cartridge has no CHR-ROM.  This probe records complete
-- 8 KiB CHR-RAM snapshots whenever a new graphics state remains unchanged
-- for a few frames.  The resulting snapshots are used by
-- chr_asset_pipeline.py to associate runtime graphics with their raw PRG
-- sources without guessing from entropy alone.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local stableFrames = 0
local currentSignature = nil
local capturedSignatures = {}
local captureCount = 0
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

local function pulseAt(frame, button, duration)
    if frames == frame then
        desiredInput[button] = true
    elseif frames == frame + duration then
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
        "%08X_%08X",
        checksum(emu.memType.nesChrRam, 0x0000, 0x0FFF),
        checksum(emu.memType.nesChrRam, 0x1000, 0x1FFF)
    )
end

local function captureStableState(signature)
    captureCount = captureCount + 1
    local prefix = string.format(
        "state_%02d_frame_%04d_%s",
        captureCount,
        frames,
        signature
    )
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
    writeBinary(prefix .. "_screen.png", emu.takeScreenshot())
    print(
        "POKEMON_CHR_CATALOG_CAPTURE frame=" ..
        tostring(frames) ..
        " signature=" .. signature
    )
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

    local state = emu.getState()
    local rendering = state["ppu.mask.backgroundEnabled"] and
        state["ppu.mask.spritesEnabled"]
    if rendering then
        local signature = graphicsSignature()
        if signature == currentSignature then
            stableFrames = stableFrames + 1
        else
            currentSignature = signature
            stableFrames = 1
        end
        if stableFrames == 12 and
           capturedSignatures[signature] == nil and
           captureCount < 100 then
            capturedSignatures[signature] = true
            captureStableState(signature)
        end
    end

    if frames ~= 5400 then
        return
    end

    if captureCount < 4 then
        print(
            "POKEMON_CHR_CATALOG_FAIL mapper=163 region=" ..
            tostring(state["region"]) ..
            " states=" .. tostring(captureCount)
        )
        emu.stop(1)
    else
        print(
            "POKEMON_CHR_CATALOG_PASS mapper=163 region=" ..
            tostring(state["region"]) ..
            " states=" .. tostring(captureCount)
        )
        emu.stop(0)
    end
end, emu.eventType.endFrame)
