-- Read-only trace of the first campaign segment from an extracted FM3 stream.
--
-- This probe exists to recover stable screen/RAM observations from the
-- original controller-only reference movie.  It replays buttons only: no
-- game-memory writes, savestate loads, rewind or cheats.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
local inputPath = os.getenv("POKEMON_YELLOW_MESEN_INPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end
if inputPath == nil or inputPath == "" then
    error("POKEMON_YELLOW_MESEN_INPUT is not set")
end

local inputFile = assert(io.open(inputPath, "rb"))
local inputBytes = inputFile:read("*a")
inputFile:close()
if #inputBytes == 0 then
    error("controller input stream is empty")
end

local frame = 0
local samples = {
    "frame\tlabel\tnametable_checksum\tx\ty\tparty_count\tparty0\tlevel0\tpc",
}

local checkpoints = {
    [913] = "00_bedroom_ready",
    [1098] = "01_bedroom_stairs",
    [1160] = "02_downstairs",
    [1470] = "03_front_door",
    [1527] = "04_outside_start",
    [1708] = "05_oak_trigger",
    [1850] = "06_oak_walks_in",
    [2056] = "07_oak_dialogue",
    [2300] = "08_capture_cutscene",
    [2600] = "09_capture_cutscene_end",
    [2706] = "10_lab_dialogue_start",
    [2980] = "11_lab_control",
    [3032] = "12_starter_ball",
    [3260] = "13_rival_interrupts",
    [3545] = "14_pikachu_offer",
    [3612] = "15_pikachu_obtained",
    [3644] = "16_walk_to_exit",
    [3799] = "17_rival_challenge",
    [4056] = "18_battle_open",
    [4390] = "19_battle_mid",
    [4917] = "20_battle_resolved",
    [5067] = "21_lab_exit_walk",
    [5193] = "22_outside_after_lab",
}

local function decodeInput(value)
    return {
        a = (value & 0x01) ~= 0,
        b = (value & 0x02) ~= 0,
        select = (value & 0x04) ~= 0,
        start = (value & 0x08) ~= 0,
        up = (value & 0x10) ~= 0,
        down = (value & 0x20) ~= 0,
        left = (value & 0x40) ~= 0,
        right = (value & 0x80) ~= 0,
    }
end

local function writeBinary(filename, data)
    local output = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    output:write(data)
    output:close()
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

local function nametableChecksum()
    local hash = 0
    for address = 0x2000, 0x2FFF do
        hash = (
            hash * 257 + emu.read(address, emu.memType.nesPpuDebug)
        ) % 0x100000000
    end
    return hash
end

local function capture(label)
    local checksum = nametableChecksum()
    local x = emu.read(0x0304, emu.memType.nesDebug)
    local y = emu.read(0x0306, emu.memType.nesDebug)
    local partyCount = emu.read(0x6030, emu.memType.nesMemory)
    local party0 = emu.read(0x6033, emu.memType.nesMemory)
    local level0 = emu.read(0x6039, emu.memType.nesMemory)
    local pc = emu.getState()["cpu.pc"] or 0
    samples[#samples + 1] = string.format(
        "%d\t%s\t%08X\t%02X\t%02X\t%02X\t%02X\t%02X\t%04X",
        frame,
        label,
        checksum,
        x,
        y,
        partyCount,
        party0,
        level0,
        pc
    )
    writeBinary(label .. "_screen.png", emu.takeScreenshot())
    writeBinary(
        label .. "_ram_2k.bin",
        memoryBytes(emu.memType.nesDebug, 0x0000, 0x07FF)
    )
    writeBinary(
        label .. "_sram_8k.bin",
        memoryBytes(emu.memType.nesMemory, 0x6000, 0x7FFF)
    )
end

emu.addEventCallback(function()
    local value = 0
    if frame < #inputBytes then
        value = string.byte(inputBytes, frame + 1)
    end
    emu.setInput(decodeInput(value), 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    local label = checkpoints[frame]
    if label ~= nil then
        capture(label)
    end
    if frame ~= 5300 then
        return
    end
    writeBinary(
        "fm3_early_campaign_trace.tsv",
        table.concat(samples, "\n") .. "\n"
    )
    print(string.format(
        "POKEMON_FM3_EARLY_CAMPAIGN_TRACE_PASS mapper=163 region=%s " ..
        "frames=%d checkpoints=%d writes_to_game=0",
        tostring(emu.getState()["region"]),
        frame,
        #samples - 1
    ))
    emu.stop(0)
end, emu.eventType.endFrame)
