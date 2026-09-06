-- Validate the translated player-card and saving-screen assets in CHR-RAM.
--
-- POKEMON_SECONDARY_SCREEN must be either "status" or "saving".  The probe
-- reaches the requested option with controller input only, then checks the
-- exact live tile payload and nametable geometry while the game transitions.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end
local mode = os.getenv("POKEMON_SECONDARY_SCREEN") or ""
if mode ~= "status" and mode ~= "saving" then
    error("POKEMON_SECONDARY_SCREEN must be status or saving")
end

local frames = 0
local desiredInput = {
    a = false, b = false, select = false, start = false,
    up = false, down = false, left = false, right = false,
}

local contracts = {
    status = {
        steps = 3,
        tileIds = {
            0x7C, 0x7D, 0x7E, 0x7F, 0x87, 0x88, 0x89, 0x8A,
            0x95, 0x96, 0x97, 0x98, 0x9E, 0x9F, 0xA0, 0xA1,
            0xAC, 0xAD, 0xAE, 0xAF, 0x83, 0x8D,
            0xB5, 0xB6, 0xB7, 0xB8, 0x84, 0x8E,
            0x81, 0x82, 0xB1,
        },
        checksum = 0x74798129,
        portraitTileIds = {0x8F, 0x90, 0x91, 0x92, 0x93, 0x94},
        portraitChecksum = 0x985FC3B3,
        rows = {
            {0x2146, {0x7C, 0x7D, 0x7E, 0x7F}},
            {0x2166, {0x87, 0x88, 0x89, 0x8A}},
            {0x21A6, {0x95, 0x96, 0x97, 0x98}},
            {0x21C6, {0x9E, 0x9F, 0xA0, 0xA1}},
            {0x2206, {0xAC, 0xAD, 0xAE, 0xAF, 0x83, 0x8D}},
            {0x2226, {0xB5, 0xB6, 0xB7, 0xB8, 0x84, 0x8E}},
            {0x214C, {0x81, 0x82, 0xB1}},
            {0x216C, {0x78, 0x78, 0x78}},
            {0x2176, {0x8F, 0x90, 0x91}},
            {0x2196, {0x92, 0x93, 0x94}},
        },
    },
    saving = {
        steps = 5,
        tileIds = {
            0x04, 0x05, 0x06, 0x07, 0x08, 0x09,
            0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
        },
        checksum = 0x10108BCD,
        rows = {
            {0x20A4, {0x04, 0x05, 0x06, 0x07, 0x08, 0x09}},
            {0x20C4, {0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F}},
            {0x20AA, {0x00, 0x00, 0x00}},
            {0x20CA, {0x10, 0x10, 0x10}},
        },
    },
}
local contract = contracts[mode]

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

local function memoryBytes(memoryType, first, last)
    local chunks = {}
    for address = first, last do
        chunks[#chunks + 1] = string.char(emu.read(address, memoryType))
    end
    return table.concat(chunks)
end

local function payloadMatches(address, expected)
    for index, value in ipairs(expected) do
        if emu.read(
            address + index - 1, emu.memType.nesPpuDebug
        ) ~= value then
            return false
        end
    end
    return true
end

local function tileChecksum(tileIds)
    local hash = 0
    for _, tileId in ipairs(tileIds) do
        for address = tileId * 16, tileId * 16 + 15 do
            hash = (
                hash * 257 + emu.read(address, emu.memType.nesChrRam)
            ) % 0x100000000
        end
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
    for step = 1, contract.steps do
        pulseAt(5220 + step * 60, "down", 4)
    end
    pulseAt(5700, "a", 8)

    if frames ~= 5800 then
        return
    end

    local failures = {}
    local checksum = tileChecksum(contract.tileIds)
    if checksum ~= contract.checksum then
        failures[#failures + 1] = string.format(
            "CHR checksum %08X != %08X", checksum, contract.checksum
        )
    end
    if contract.portraitTileIds ~= nil then
        local portraitChecksum = tileChecksum(contract.portraitTileIds)
        if portraitChecksum ~= contract.portraitChecksum then
            failures[#failures + 1] = string.format(
                "portrait checksum %08X != %08X",
                portraitChecksum,
                contract.portraitChecksum
            )
        end
    end
    for _, row in ipairs(contract.rows) do
        if not payloadMatches(row[1], row[2]) then
            failures[#failures + 1] = string.format(
                "nametable mismatch at $%04X", row[1]
            )
        end
    end

    writeBinary(
        mode .. "_fr_chr_ram_8k.bin",
        memoryBytes(emu.memType.nesChrRam, 0x0000, 0x1FFF)
    )
    writeBinary(
        mode .. "_fr_nametable_4k.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
    )
    writeBinary(
        mode .. "_fr_sram_8k.bin",
        memoryBytes(emu.memType.nesMemory, 0x6000, 0x7FFF)
    )
    writeBinary(
        mode .. "_fr_palette_32.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x3F00, 0x3F1F)
    )
    writeBinary(
        mode .. "_fr_cpu_ram_2k.bin",
        memoryBytes(emu.memType.nesMemory, 0x0000, 0x07FF)
    )
    writeBinary(
        mode .. "_fr_oam_256.bin",
        memoryBytes(emu.memType.nesSpriteRam, 0x0000, 0x00FF)
    )
    writeBinary(mode .. "_fr_screen.png", emu.takeScreenshot())

    if #failures == 0 then
        print(string.format(
            "POKEMON_SECONDARY_MENU_FR_PASS mapper=163 region=%s " ..
            "screen=%s frames=%d checksum=%08X sameFrameAssets=true",
            tostring(emu.getState()["region"]), mode, frames, checksum
        ))
        emu.stop(0)
    else
        print(
            "POKEMON_SECONDARY_MENU_FR_FAIL screen=" .. mode .. " " ..
            table.concat(failures, "; ")
        )
        emu.stop(1)
    end
end, emu.eventType.endFrame)
