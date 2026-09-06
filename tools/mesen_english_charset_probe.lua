-- Controller-only runtime proof for the native English font and Pokémon é.
--
-- Unicode é is encoded as byte $40.  The original English font already draws
-- é in that slot.  This probe finds every encoded "Pok@mon" in the candidate,
-- observes a real $40 text read during the intro, observes all 16 bytes of the
-- font tile being read, and requires ensuing CHR-RAM writes before capturing
-- a completed dialogue page.  The probe never writes game state or PRG-ROM.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
local romPath = os.getenv("POKEMON_YELLOW_MESEN_ROM")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end
if romPath == nil or romPath == "" then
    error("POKEMON_YELLOW_MESEN_ROM is not set")
end

local INES_HEADER_SIZE = 16
local PRG_PAIR_SIZE = 0x8000
local ASCII_FONT_OFFSET = 0x078210
local E_ACUTE_CODE = 0x40
local E_ACUTE_FONT_OFFSET =
    ASCII_FONT_OFFSET + (E_ACUTE_CODE - 0x20) * 16
local E_ACUTE_EXPECTED_HEX = "0030c03c427e403e0000000000000000"
local ENCODED_POKEMON = "Pok@mon"

local function readFile(path)
    local file = assert(io.open(path, "rb"))
    local data = file:read("*a")
    file:close()
    return data
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

local function toHex(data)
    return (string.gsub(data, ".", function(value)
        return string.format("%02x", string.byte(value))
    end))
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

local rom = readFile(romPath)
if string.sub(rom, 1, 4) ~= "NES\026" then
    error("not an iNES ROM")
end
if string.byte(rom, 5) * 0x4000 ~= 0x200000 or
   string.byte(rom, 6) ~= 0 then
    error("unexpected PRG/CHR layout")
end
local mapper =
    ((string.byte(rom, 7) >> 4) | (string.byte(rom, 8) & 0xF0))
if mapper ~= 163 then
    error("unexpected mapper: " .. tostring(mapper))
end

local fontTile = string.sub(
    rom,
    E_ACUTE_FONT_OFFSET + 1,
    E_ACUTE_FONT_OFFSET + 16
)
if toHex(fontTile) ~= E_ACUTE_EXPECTED_HEX then
    error(
        "English é font tile changed: " .. toHex(fontTile) ..
        " != " .. E_ACUTE_EXPECTED_HEX
    )
end

local function pairAndCpu(fileOffset)
    local pair = (fileOffset - INES_HEADER_SIZE) // PRG_PAIR_SIZE
    local pairStart = INES_HEADER_SIZE + pair * PRG_PAIR_SIZE
    return pair, 0x8000 + fileOffset - pairStart
end

local targetByPairAndCpu = {}
local targetCpuAddresses = {}
local searchAt = 1
local occurrenceCount = 0
while true do
    local found = string.find(rom, ENCODED_POKEMON, searchAt, true)
    if found == nil then
        break
    end
    occurrenceCount = occurrenceCount + 1
    -- Lua strings are one-based; @ is the fourth byte of Pok@mon.
    local atFileOffset = found - 1 + 3
    local pair, cpu = pairAndCpu(atFileOffset)
    targetByPairAndCpu[pair] = targetByPairAndCpu[pair] or {}
    targetByPairAndCpu[pair][cpu] = atFileOffset
    targetCpuAddresses[cpu] = true
    searchAt = found + 1
end
if occurrenceCount < 2 then
    error("candidate has too few encoded Pokémon occurrences")
end

local fontPair, fontCpuFirst = pairAndCpu(E_ACUTE_FONT_OFFSET)
local fontCpuLast = fontCpuFirst + 15
local frames = 0
local nmiCount = 0
local lowBank = 0
local highBank = 0
local mapperBankKnown = false
local textReadEvents = 0
local textReadOffsets = {}
local textReadMismatches = 0
local fontReadEvents = 0
local fontReadBytes = {}
local fontReadMismatches = 0
local lastFontReadFrame = nil
local ppuWritesNearFont = 0
local finished = false
local nextPromptAdvance = nil
local lastPromptAdvance = 0
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

local function currentBank()
    return lowBank | (highBank << 4)
end

local function mapperRegisterKey(address)
    if address == 0x5101 then
        return 0x5101
    end
    return address & 0x7300
end

local function promptArrowVisible()
    local sprite = 63 * 4
    local y = emu.read(sprite, emu.memType.nesSpriteRam)
    return y >= 190 and y <= 193 and
           emu.read(sprite + 1, emu.memType.nesSpriteRam) == 0xFF and
           emu.read(sprite + 3, emu.memType.nesSpriteRam) == 208
end

local function uniqueCount(values)
    local count = 0
    for _ in pairs(values) do
        count = count + 1
    end
    return count
end

local function firstPlaneUniqueCount(values)
    local count = 0
    for index in pairs(values) do
        if index < 8 then
            count = count + 1
        end
    end
    return count
end

local function captureAndFinish()
    if finished then
        return
    end
    finished = true
    local failures = {}
    local fontUnique = uniqueCount(fontReadBytes)
    local fontPlane0Unique = firstPlaneUniqueCount(fontReadBytes)
    local textUnique = uniqueCount(textReadOffsets)
    if textReadEvents < 1 or textUnique < 1 then
        failures[#failures + 1] = "no encoded Pokémon é byte read"
    end
    if textReadMismatches ~= 0 then
        failures[#failures + 1] =
            "text read mismatches=" .. tostring(textReadMismatches)
    end
    -- The engine reads the eight nonblank first-plane rows twice; this is the
    -- same proven contract used by the exhaustive French glyph diagnostic.
    if fontReadEvents < 16 or fontPlane0Unique ~= 8 then
        failures[#failures + 1] = string.format(
            "incomplete é font read events=%d plane0=%d/8 unique=%d",
            fontReadEvents,
            fontPlane0Unique,
            fontUnique
        )
    end
    if fontReadMismatches ~= 0 then
        failures[#failures + 1] =
            "font read mismatches=" .. tostring(fontReadMismatches)
    end
    if ppuWritesNearFont < 16 then
        failures[#failures + 1] =
            "too few CHR writes after é font reads: " ..
            tostring(ppuWritesNearFont)
    end
    if nmiCount < 300 then
        failures[#failures + 1] = "too few NMIs=" .. tostring(nmiCount)
    end

    local screenshot = emu.takeScreenshot()
    if #screenshot < 1000 then
        failures[#failures + 1] = "screenshot PNG unexpectedly small"
    end
    writeBinary("english_charset_pokemon_screen.png", screenshot)
    writeBinary(
        "english_charset_pokemon_chr_ram_8k.bin",
        memoryBytes(emu.memType.nesChrRam, 0x0000, 0x1FFF)
    )
    writeBinary(
        "english_charset_pokemon_nametable_4k.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
    )
    local failureText = #failures == 0 and "" or table.concat(failures, "; ")
    writeText(
        "english_charset_pokemon_validation.txt",
        table.concat({
            "schema=nj046-en2-english-charset-runtime/v1",
            "controllerOnly=true",
            "diskRomWritesByProbe=0",
            "cpuRamWritesByProbe=0",
            "ppuWritesByProbe=0",
            "mapperWritesByProbe=0",
            "encodedPokemonOccurrences=" .. tostring(occurrenceCount),
            "encodedEAcuteReadEvents=" .. tostring(textReadEvents),
            "encodedEAcuteUniqueOffsets=" .. tostring(textUnique),
            "fontTileOffset=" .. string.format("$%06X", E_ACUTE_FONT_OFFSET),
            "fontTileHex=" .. E_ACUTE_EXPECTED_HEX,
            "fontReadEvents=" .. tostring(fontReadEvents),
            "fontUniqueBytes=" .. tostring(fontUnique),
            "fontPlane0UniqueBytes=" .. tostring(fontPlane0Unique),
            "ppuWritesNearFont=" .. tostring(ppuWritesNearFont),
            "result=" .. (#failures == 0 and "PASS" or "FAIL"),
            "failures=" .. failureText,
        }, "\n") .. "\n"
    )

    local region = tostring(emu.getState()["region"])
    if #failures == 0 then
        print(string.format(
            "POKEMON_ENGLISH_CHARSET_PASS mapper=163 region=%s " ..
            "frames=%d occurrences=%d textReads=%d fontReads=%d " ..
            "fontUnique=%d fontPlane0=%d ppuWrites=%d controllerOnly=true",
            region,
            frames,
            occurrenceCount,
            textReadEvents,
            fontReadEvents,
            fontUnique,
            fontPlane0Unique,
            ppuWritesNearFont
        ))
        emu.stop(0)
    else
        print(
            "POKEMON_ENGLISH_CHARSET_FAIL mapper=163 region=" .. region ..
            " " .. failureText
        )
        emu.stop(1)
    end
end

emu.addMemoryCallback(function(address, value)
    local key = mapperRegisterKey(address)
    if key == 0x5000 then
        lowBank = value & 0x0F
        mapperBankKnown = true
    elseif key == 0x5200 then
        highBank = value & 0x0F
        mapperBankKnown = true
    end
end, emu.callbackType.write, 0x5000, 0x5FFF)

local function observeTextRead(address, value)
    if not mapperBankKnown then
        return
    end
    local pairTargets = targetByPairAndCpu[currentBank()]
    if pairTargets == nil then
        return
    end
    local fileOffset = pairTargets[address]
    if fileOffset == nil then
        return
    end
    textReadEvents = textReadEvents + 1
    textReadOffsets[fileOffset] = true
    if value ~= E_ACUTE_CODE then
        textReadMismatches = textReadMismatches + 1
    end
end

for cpu in pairs(targetCpuAddresses) do
    emu.addMemoryCallback(
        observeTextRead,
        emu.callbackType.read,
        cpu,
        cpu
    )
end

emu.addMemoryCallback(function(address, value)
    if not mapperBankKnown or currentBank() ~= fontPair then
        return
    end
    local index = address - fontCpuFirst
    fontReadEvents = fontReadEvents + 1
    fontReadBytes[index] = true
    if value ~= string.byte(fontTile, index + 1) then
        fontReadMismatches = fontReadMismatches + 1
    end
    lastFontReadFrame = frames
end, emu.callbackType.read, fontCpuFirst, fontCpuLast)

emu.addMemoryCallback(function(address)
    if (address & 0x07) == 0x07 and
       lastFontReadFrame ~= nil and
       frames - lastFontReadFrame <= 1 then
        ppuWritesNearFont = ppuWritesNearFont + 1
    end
end, emu.callbackType.write, 0x2000, 0x3FFF)

emu.addEventCallback(function()
    nmiCount = nmiCount + 1
end, emu.eventType.nmi)

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1
    if frames == 180 then
        desiredInput.start = true
    elseif frames == 184 then
        desiredInput.start = false
    elseif frames == 360 then
        desiredInput.a = true
    elseif frames == 364 then
        desiredInput.a = false
    end

    local promptVisible = frames > 400 and promptArrowVisible()
    if textReadEvents == 0 and
       promptVisible and
       nextPromptAdvance == nil and
       frames - lastPromptAdvance >= 60 then
        nextPromptAdvance = frames + 30
    end
    if nextPromptAdvance ~= nil and frames == nextPromptAdvance then
        desiredInput.a = true
    elseif nextPromptAdvance ~= nil and frames == nextPromptAdvance + 3 then
        desiredInput.a = false
        lastPromptAdvance = frames
        nextPromptAdvance = nil
    end

    if frames > 400 and
       textReadEvents > 0 and
       firstPlaneUniqueCount(fontReadBytes) == 8 and
       ppuWritesNearFont >= 16 and
       promptVisible then
        captureAndFinish()
    elseif frames == 3000 then
        captureAndFinish()
    end
end, emu.eventType.endFrame)
