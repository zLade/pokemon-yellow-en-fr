-- Replay a headerless stream of FCEUX NES controller-1 bytes in Mesen.
--
-- Generate the stream with extract_fm3_inputs.py and pass it through the
-- runner's -InputPath option.  This replayer never writes game memory.  A
-- PASS only proves that the complete stream was consumed; synchronization
-- and campaign completion require explicit expected checkpoints/artifacts.

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
local activeFrames = 0
local inputChecksum = 0
for index = 1, #inputBytes do
    local value = string.byte(inputBytes, index)
    if value ~= 0 then
        activeFrames = activeFrames + 1
    end
    inputChecksum = (inputChecksum * 257 + value) % 0x100000000
end

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

emu.addEventCallback(function()
    local value = 0
    if frame < #inputBytes then
        value = string.byte(inputBytes, frame + 1)
    end
    emu.setInput(decodeInput(value), 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    if frame ~= #inputBytes then
        return
    end

    writeBinary("fm3_replay_final_screen.png", emu.takeScreenshot())
    writeBinary(
        "fm3_replay_final_cpu_ram_2k.bin",
        memoryBytes(emu.memType.nesDebug, 0x0000, 0x07FF)
    )
    writeBinary(
        "fm3_replay_final_sram_8k.bin",
        memoryBytes(emu.memType.nesDebug, 0x6000, 0x7FFF)
    )
    print(string.format(
        "POKEMON_FM3_REPLAY_PASS mapper=163 region=%s frames=%d " ..
        "activeFrames=%d inputChecksum=%08X pc=%04X " ..
        "verification=stream_exhausted",
        tostring(emu.getState()["region"]),
        frame,
        activeFrames,
        inputChecksum,
        emu.getState()["cpu.pc"] or 0
    ))
    emu.stop(0)
end, emu.eventType.endFrame)
