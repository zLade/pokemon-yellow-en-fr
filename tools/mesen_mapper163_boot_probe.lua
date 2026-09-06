-- Pokemon Yellow NES (NJ046) cold-boot/smoke probe for Mesen 2.2.1.
--
-- This cartridge is iNES mapper 163 with 2 MiB PRG-ROM and CHR-RAM.  The
-- probe deliberately avoids mapper 30 registers and project-specific RAM
-- addresses.  It checks only observable execution/PPU invariants that are
-- valid for the original English ROM and the translated build alike.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local nmiCount = 0
local renderingFrames = 0
local pcSamples = {}
local pcSampleCount = 0
local screenshotCount = 0
local screenshotFrames = {
    [120] = "boot_0120.png",
    [300] = "boot_0300.png",
    [600] = "boot_0600.png",
}

local function saveScreenshot(filename)
    local png = emu.takeScreenshot()
    local path = outputDirectory .. "\\" .. filename
    local file = assert(io.open(path, "wb"))
    file:write(png)
    file:close()
    screenshotCount = screenshotCount + 1
end

local function checksum(memoryType, first, last)
    local hash = 0
    for address = first, last do
        hash = (hash * 257 + emu.read(address, memoryType)) % 0x100000000
    end
    return hash
end

emu.addEventCallback(function()
    nmiCount = nmiCount + 1
end, emu.eventType.nmi)

emu.addEventCallback(function()
    frames = frames + 1
    local state = emu.getState()
    local pc = state["cpu.pc"]
    if type(pc) == "number" and not pcSamples[pc] then
        pcSamples[pc] = true
        pcSampleCount = pcSampleCount + 1
    end
    if state["ppu.mask.backgroundEnabled"] or
       state["ppu.mask.spritesEnabled"] then
        renderingFrames = renderingFrames + 1
    end

    local screenshotName = screenshotFrames[frames]
    if screenshotName ~= nil then
        saveScreenshot(screenshotName)
    end

    if frames ~= 600 then
        return
    end

    local failures = {}
    if nmiCount < 300 then
        table.insert(failures, "too few NMIs: " .. tostring(nmiCount))
    end
    if renderingFrames < 300 then
        table.insert(
            failures,
            "too few rendered frames: " .. tostring(renderingFrames)
        )
    end
    if pcSampleCount < 8 then
        table.insert(
            failures,
            "CPU execution appears stuck: unique PCs=" .. tostring(pcSampleCount)
        )
    end
    if screenshotCount ~= 3 then
        table.insert(
            failures,
            "missing screenshots: " .. tostring(screenshotCount) .. "/3"
        )
    end

    local ramHash = checksum(emu.memType.nesMemory, 0x0000, 0x07FF)
    local chrHash = checksum(emu.memType.nesChrRam, 0x0000, 0x1FFF)
    local region = tostring(state["region"])
    if #failures == 0 then
        print(string.format(
            "POKEMON_MESEN_PASS mapper=163 region=%s frames=%d nmi=%d rendered=%d uniquePc=%d ram=%08X chrRam=%08X screenshots=%d",
            region, frames, nmiCount, renderingFrames, pcSampleCount,
            ramHash, chrHash, screenshotCount
        ))
        emu.stop(0)
    else
        print(
            "POKEMON_MESEN_FAIL mapper=163 " .. table.concat(failures, "; ")
        )
        emu.stop(1)
    end
end, emu.eventType.endFrame)
