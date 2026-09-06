-- Exhaustive assisted runtime proof for all native French dialogue glyphs.
--
-- The canonical source entry is p(0x035E82, ...).  Repacked builds can move
-- its payload. The probe temporarily replaces that one loaded PRG-ROM record
-- inside Mesen with an equal-length diagnostic record containing
-- À Â É Î Ç à â ç è é ê î ï ô ù û. The disk ROM is never modified, and the
-- loaded record is restored before the probe exits.
--
-- The game reaches and renders the record through normal controller input.
-- For every glyph the probe requires, in the same completed dialogue page:
--   * the diagnostic byte to be read by the CPU through mapper 163;
--   * all eight bitmap rows to be read from the real PRG font tile;
--   * the ensuing PPU $2007 writes that build the enlarged CHR-RAM tiles;
--   * both generated tile IDs in both mirrored dialogue nametables.
-- A screenshot plus CHR, PPU, nametable, palette and OAM dumps are archived.
-- This is explicitly an assisted diagnostic, not controller-only evidence.
-- It writes no CPU RAM, PPU memory, mapper register, save data or savestate.

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
local SOURCE_ENTRY_OFFSET = 0x035E82
local ASCII_FONT_OFFSET = 0x078210
local EXPECTED_MANIFEST =
    "tools/data/mesen_french_charset_probe_expected.json"
local ORIGINAL_RECORD_HEX =
    "534143484120212020202020202020202054612071757d746520506f6b406d6f" ..
    "6e202020766120636f6d6d656e63657220212020202020556e206d6f6e646520" ..
    "646520727d766573202065742064276176656e74757265732020202020742761" ..
    "7474656e6420210d"
local DIAGNOSTIC_RECORD_HEX =
    "474c5950484553204652414e434149532022232a3c3b7b7e5b7c407d5c5d5e5f" ..
    "602020204d4f54455552205445585445205245454c20204c4543545552452050" ..
    "4f4c49434520524f4d204543524954555245204348522052414d202050524555" ..
    "5645204f4b20200d"

local function fromHex(hex)
    if #hex % 2 ~= 0 or string.find(hex, "[^0-9a-fA-F]") ~= nil then
        error("invalid hexadecimal byte string")
    end
    return (string.gsub(hex, "..", function(pair)
        return string.char(tonumber(pair, 16))
    end))
end

local ORIGINAL_RECORD = fromHex(ORIGINAL_RECORD_HEX)
local TARGET_RECORD = fromHex(DIAGNOSTIC_RECORD_HEX)
if #ORIGINAL_RECORD ~= 104 or #TARGET_RECORD ~= #ORIGINAL_RECORD then
    error("French charset diagnostic record length contract mismatch")
end

local glyphs = {
    {
        label = "A_grave_upper",
        character = "À",
        code = 0x22,
        romOffset = 0x078230,
        expectedHex = "0c031028447c82820000000000000000",
    },
    {
        label = "A_circumflex_upper",
        character = "Â",
        code = 0x23,
        romOffset = 0x078240,
        expectedHex = "18241028447c82820000000000000000",
    },
    {
        label = "E_acute_upper",
        character = "É",
        code = 0x2A,
        romOffset = 0x0782B0,
        expectedHex = "30c0fe80fc8080fe0000000000000000",
    },
    {
        label = "C_cedilla_upper",
        character = "Ç",
        code = 0x3B,
        romOffset = 0x0783C0,
        expectedHex = "3c428080423c10200000000000000000",
    },
    {
        label = "I_circumflex_upper",
        character = "Î",
        code = 0x3C,
        romOffset = 0x0783D0,
        expectedHex = "18247c101010107c0000000000000000",
    },
    {
        label = "e_acute",
        character = "é",
        code = 0x40,
        romOffset = 0x078410,
        expectedHex = "0030c03c427e403e0000000000000000",
    },
    {
        label = "c_cedilla",
        character = "ç",
        code = 0x5B,
        romOffset = 0x0785C0,
        expectedHex = "00788480847810200000000000000000",
    },
    {
        label = "i_circumflex",
        character = "î",
        code = 0x5C,
        romOffset = 0x0785D0,
        expectedHex = "18240010101010100000000000000000",
    },
    {
        label = "i_diaeresis",
        character = "ï",
        code = 0x5D,
        romOffset = 0x0785E0,
        expectedHex = "24000010101010100000000000000000",
    },
    {
        label = "o_circumflex",
        character = "ô",
        code = 0x5E,
        romOffset = 0x0785F0,
        expectedHex = "1824003c4242423c0000000000000000",
    },
    {
        label = "u_grave",
        character = "ù",
        code = 0x5F,
        romOffset = 0x078600,
        expectedHex = "000c03444444443c0000000000000000",
    },
    {
        label = "u_circumflex",
        character = "û",
        code = 0x60,
        romOffset = 0x078610,
        expectedHex = "182400444444443c0000000000000000",
    },
    {
        label = "a_grave",
        character = "à",
        code = 0x7B,
        romOffset = 0x0787C0,
        expectedHex = "000c0338043c443e0000000000000000",
    },
    {
        label = "e_grave",
        character = "è",
        code = 0x7C,
        romOffset = 0x0787D0,
        expectedHex = "000c033c427e403e0000000000000000",
    },
    {
        label = "e_circumflex",
        character = "ê",
        code = 0x7D,
        romOffset = 0x0787E0,
        expectedHex = "1824003c427e403e0000000000000000",
    },
    {
        label = "a_circumflex",
        character = "â",
        code = 0x7E,
        romOffset = 0x0787F0,
        expectedHex = "18240038043c443e0000000000000000",
    },
}

local pageRequirements = {
    {
        0x22, 0x23, 0x2A, 0x3C, 0x3B, 0x7B, 0x7E, 0x5B,
        0x7C, 0x40, 0x7D, 0x5C, 0x5D, 0x5E, 0x5F, 0x60,
    },
    {},
    {},
}

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
    error("not an iNES ROM: " .. romPath)
end
if string.byte(rom, 5) * 0x4000 ~= 0x200000 or
   string.byte(rom, 6) ~= 0 then
    error("unexpected mapper 163 PRG/CHR layout")
end
local mapper =
    ((string.byte(rom, 7) >> 4) | (string.byte(rom, 8) & 0xF0))
if mapper ~= 163 then
    error("unexpected iNES mapper: " .. tostring(mapper))
end

local targetFirst = nil
local searchAt = 1
local targetOccurrences = 0
while true do
    local found = string.find(rom, ORIGINAL_RECORD, searchAt, true)
    if found == nil then
        break
    end
    targetOccurrences = targetOccurrences + 1
    targetFirst = found
    searchAt = found + 1
end
if targetOccurrences ~= 1 then
    error(
        "accent target record occurrence count=" ..
        tostring(targetOccurrences) .. ", expected 1"
    )
end

-- Lua strings are one-based; file offsets and CPU addresses are zero-based.
local targetFileOffset = targetFirst - 1
local targetPair = (targetFileOffset - INES_HEADER_SIZE) // PRG_PAIR_SIZE
local targetPairStart = INES_HEADER_SIZE + targetPair * PRG_PAIR_SIZE
local targetCpuFirst = 0x8000 + targetFileOffset - targetPairStart
local targetCpuLast = targetCpuFirst + #TARGET_RECORD - 1
if targetCpuFirst < 0x8000 or targetCpuLast > 0xFFFF then
    error("accent target record crosses a 32 KiB mapper window")
end

local glyphByCode = {}
for _, glyph in ipairs(glyphs) do
    if glyphByCode[glyph.code] ~= nil then
        error(string.format("duplicate French glyph code $%02X", glyph.code))
    end
    local expectedOffset =
        ASCII_FONT_OFFSET + (glyph.code - 0x20) * 16
    if glyph.romOffset ~= expectedOffset then
        error("internal French font offset mismatch for " .. glyph.label)
    end
    glyph.tile = string.sub(rom, glyph.romOffset + 1, glyph.romOffset + 16)
    if toHex(glyph.tile) ~= glyph.expectedHex then
        error(
            string.format(
                "ROM glyph mismatch %s at $%06X: %s != %s",
                glyph.label,
                glyph.romOffset,
                toHex(glyph.tile),
                glyph.expectedHex
            )
        )
    end
    glyph.pair =
        (glyph.romOffset - INES_HEADER_SIZE) // PRG_PAIR_SIZE
    local pairStart =
        INES_HEADER_SIZE + glyph.pair * PRG_PAIR_SIZE
    glyph.cpuFirst = 0x8000 + glyph.romOffset - pairStart
    glyph.cpuLast = glyph.cpuFirst + 15
    glyph.sourceReadEvents = 0
    glyph.sourceReadBytes = {}
    glyph.sourceReadLog = {}
    glyph.lastSourceReadFrame = nil
    glyph.ppuWritesNearSourceReads = 0
    glyph.ppuWriteLog = {}
    glyphByCode[glyph.code] = glyph
end
if #glyphs ~= 16 then
    error("expected 16 native French glyphs, got " .. tostring(#glyphs))
end
for _, glyph in ipairs(glyphs) do
    local occurrences = 0
    for index = 1, #TARGET_RECORD do
        if string.byte(TARGET_RECORD, index) == glyph.code then
            occurrences = occurrences + 1
        end
    end
    if occurrences ~= 1 then
        error(
            string.format(
                "diagnostic record occurrence count for %s is %d, expected 1",
                glyph.label,
                occurrences
            )
        )
    end
end

local targetPrgOffset = targetFileOffset - INES_HEADER_SIZE
local transientPrgPatchWrites = 0
local transientPrgRestoreWrites = 0
local transientPatchInstalled = false
local transientPatchRestored = false

local function loadedPrgRecord()
    return memoryBytes(
        emu.memType.nesPrgRom,
        targetPrgOffset,
        targetPrgOffset + #ORIGINAL_RECORD - 1
    )
end

local function installTransientRecord()
    if loadedPrgRecord() ~= ORIGINAL_RECORD then
        error("loaded PRG record differs from the disk ROM before patch")
    end
    for index = 1, #TARGET_RECORD do
        local original = string.byte(ORIGINAL_RECORD, index)
        local diagnostic = string.byte(TARGET_RECORD, index)
        if original ~= diagnostic then
            emu.write(
                targetPrgOffset + index - 1,
                diagnostic,
                emu.memType.nesPrgRom
            )
            transientPrgPatchWrites = transientPrgPatchWrites + 1
        end
    end
    if loadedPrgRecord() ~= TARGET_RECORD then
        error("transient diagnostic PRG record patch did not verify")
    end
    transientPatchInstalled = true
end

local function restoreTransientRecord()
    if transientPatchRestored then
        return true
    end
    for index = 1, #ORIGINAL_RECORD do
        local original = string.byte(ORIGINAL_RECORD, index)
        local diagnostic = string.byte(TARGET_RECORD, index)
        if original ~= diagnostic then
            emu.write(
                targetPrgOffset + index - 1,
                original,
                emu.memType.nesPrgRom
            )
            transientPrgRestoreWrites = transientPrgRestoreWrites + 1
        end
    end
    transientPatchRestored = loadedPrgRecord() == ORIGINAL_RECORD
    return transientPatchRestored
end

installTransientRecord()

local frames = 0
local nmiCount = 0
local lowBank = 0
local highBank = 0
local mapperBankKnown = false
local targetReadEvents = 0
local targetReadMismatches = 0
local targetReadBytes = {}
local targetFirstReadFrame = nil
local targetLastReadFrame = nil
local ppuDataWrites = 0
local targetActive = false
local targetPage = 0
local advanceAt = nil
local lastPromptSignature = nil
local finalPageSignature = nil
local finalPageStableFrames = 0
local pageEvidence = {}
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

local function mapperRegisterKey(address)
    if address == 0x5101 then
        return 0x5101
    end
    return address & 0x7300
end

local function currentBank()
    return lowBank | (highBank << 4)
end

local function promptArrowVisible()
    local sprite = 63 * 4
    local y = emu.read(sprite, emu.memType.nesSpriteRam)
    return y >= 190 and y <= 193 and
           emu.read(sprite + 1, emu.memType.nesSpriteRam) == 0xFF and
           emu.read(sprite + 3, emu.memType.nesSpriteRam) == 208
end

local function dialoguePixelSignature()
    local hash = 0
    for y = 165, 203, 2 do
        for x = 40, 199, 2 do
            hash = (hash * 257 + emu.getPixel(x, y)) % 0x100000000
        end
    end
    return hash
end

local PAGE_STARTS = { 0, 36, 74 }
local PAGE_ENDS = { 35, 73, 102 }

local function expectedDialogueReferences(page, code)
    local references = {}
    local firstLineLength = page == 1 and 17 or 19
    for recordIndex = PAGE_STARTS[page], PAGE_ENDS[page] do
        if string.byte(TARGET_RECORD, recordIndex + 1) == code then
            local pageIndex = recordIndex - PAGE_STARTS[page]
            local line = pageIndex < firstLineLength and 1 or 2
            local lineIndex =
                line == 1 and pageIndex or pageIndex - firstLineLength
            local lineLength = line == 1 and firstLineLength or 19
            local column = 6 + (19 - lineLength) + lineIndex
            local topRow = line == 1 and 21 or 23
            local topTileId = 0x40 + pageIndex * 2
            for _, tableIndex in ipairs({ 0, 2 }) do
                for rowOffset = 0, 1 do
                    local address =
                        0x2000 + tableIndex * 0x400 +
                        (topRow + rowOffset) * 32 + column
                    local expectedTileId = topTileId + rowOffset
                    references[#references + 1] = {
                        address = address,
                        tableIndex = tableIndex,
                        row = topRow + rowOffset,
                        column = column,
                        tileId = emu.read(
                            address,
                            emu.memType.nesPpuDebug
                        ),
                        expectedTileId = expectedTileId,
                        matches =
                            emu.read(
                                address,
                                emu.memType.nesPpuDebug
                            ) == expectedTileId,
                    }
                end
            end
        end
    end
    return references
end

local function formatReferences(references)
    local values = {}
    for _, reference in ipairs(references) do
        values[#values + 1] = string.format(
            "$%04X=$%02X/%02X:%s",
            reference.address,
            reference.tileId,
            reference.expectedTileId,
            reference.matches and "ok" or "bad"
        )
    end
    return table.concat(values, ",")
end

local function sourceReadCoverage(glyph, firstFrame, lastFrame)
    local firstPlane = {}
    local secondPlane = {}
    local events = 0
    for _, event in ipairs(glyph.sourceReadLog) do
        if event.frame >= firstFrame and event.frame <= lastFrame then
            events = events + 1
            if event.index < 8 then
                firstPlane[event.index] = true
            else
                secondPlane[event.index] = true
            end
        end
    end
    local firstPlaneCount = 0
    for _ in pairs(firstPlane) do
        firstPlaneCount = firstPlaneCount + 1
    end
    local secondPlaneCount = 0
    for _ in pairs(secondPlane) do
        secondPlaneCount = secondPlaneCount + 1
    end
    local ppuWrites = 0
    for _, writeFrame in ipairs(glyph.ppuWriteLog) do
        if writeFrame >= firstFrame and writeFrame <= lastFrame then
            ppuWrites = ppuWrites + 1
        end
    end
    return firstPlaneCount, secondPlaneCount, events, ppuWrites
end

local function requiredOnPage(page, code)
    for _, requiredCode in ipairs(pageRequirements[page]) do
        if code == requiredCode then
            return true
        end
    end
    return false
end

local function captureTargetPage(page, signature)
    local state = emu.getState()
    local patternBase =
        tonumber(state["ppu.control.backgroundPatternAddr"]) or 0
    local prefix = string.format(
        "french_charset_exhaustive_page_%d_frame_%04d",
        page,
        frames
    )
    local screenshot = emu.takeScreenshot()

    writeBinary(prefix .. ".png", screenshot)
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

    local evidence = {
        page = page,
        frame = frames,
        signature = signature,
        patternBase = patternBase,
        glyphs = {},
    }
    local intervalFirst = targetFirstReadFrame or 0
    if page > 1 and pageEvidence[page - 1] ~= nil then
        intervalFirst = pageEvidence[page - 1].frame + 1
    end
    for _, glyph in ipairs(glyphs) do
        local references = expectedDialogueReferences(page, glyph.code)
        local sourcePlane0, sourcePlane1, sourceEvents, ppuWrites =
            sourceReadCoverage(glyph, intervalFirst, frames)
        evidence.glyphs[glyph.code] = {
            references = references,
            sourcePlane0 = sourcePlane0,
            sourcePlane1 = sourcePlane1,
            sourceEvents = sourceEvents,
            ppuWritesNearSourceReads = ppuWrites,
        }
        print(string.format(
            "POKEMON_FRENCH_CHARSET_GLYPH page=%d frame=%d glyph=%s " ..
            "code=$%02X rom=$%06X bgBase=$%04X " ..
            "sourcePlane0=%d/8 sourcePlane1=%d/8 events=%d " ..
            "ppuWritesNear=%d refs=%s",
            page,
            frames,
            glyph.label,
            glyph.code,
            glyph.romOffset,
            patternBase,
            sourcePlane0,
            sourcePlane1,
            sourceEvents,
            ppuWrites,
            formatReferences(references)
        ))
    end
    pageEvidence[page] = evidence
    print(string.format(
        "POKEMON_FRENCH_CHARSET_CAPTURE page=%d frame=%d " ..
        "targetReads=%d targetUnique=%d pngBytes=%d",
        page,
        frames,
        targetReadEvents,
        (function()
            local count = 0
            for _ in pairs(targetReadBytes) do
                count = count + 1
            end
            return count
        end)(),
        #screenshot
    ))
end

local function finalize()
    local restoreOk = restoreTransientRecord()
    local failures = {}
    local report = {
        "Pokemon Yellow NES - exhaustive French charset runtime proof",
        "schemaVersion=1",
        "mode=assisted_transient_prg_record",
        "expectedManifest=" .. EXPECTED_MANIFEST,
        string.format(
            "canonicalSourceEntry=$%06X",
            SOURCE_ENTRY_OFFSET
        ),
        string.format("repackedRecordOffset=$%06X", targetFileOffset),
        string.format("repackedRecordBytes=%d", #TARGET_RECORD),
        string.format("nativeGlyphs=%d", #glyphs),
        string.format("mapperPair=%d", targetPair),
        string.format(
            "cpuSpan=$%04X-$%04X",
            targetCpuFirst,
            targetCpuLast
        ),
        string.format("targetReadEvents=%d", targetReadEvents),
        string.format(
            "targetReadFrames=%s-%s",
            tostring(targetFirstReadFrame),
            tostring(targetLastReadFrame)
        ),
        string.format("targetReadMismatches=%d", targetReadMismatches),
        string.format("observedPpuDataWrites=%d", ppuDataWrites),
        string.format("nmi=%d", nmiCount),
        "controllerOnly=false",
        "assistedPrgRecordOnly=true",
        string.format(
            "transientPrgPatchWrites=%d",
            transientPrgPatchWrites
        ),
        string.format(
            "transientPrgRestoreWrites=%d",
            transientPrgRestoreWrites
        ),
        "transientPrgRecordRestored=" .. tostring(restoreOk),
        "diskRomWritesByProbe=0",
        "cpuRamWritesByProbe=0",
        "ppuWritesByProbe=0",
        "mapperWritesByProbe=0",
        "savestateRewindCheat=false",
    }

    if not transientPatchInstalled then
        failures[#failures + 1] = "transient diagnostic record was not installed"
    end
    if transientPrgPatchWrites ~= 91 then
        failures[#failures + 1] =
            "transient PRG patch write count=" ..
            tostring(transientPrgPatchWrites) .. ", expected 91"
    end
    if transientPrgRestoreWrites ~= 91 then
        failures[#failures + 1] =
            "transient PRG restore write count=" ..
            tostring(transientPrgRestoreWrites) .. ", expected 91"
    end
    if not restoreOk then
        failures[#failures + 1] =
            "transient diagnostic record was not restored"
    end

    local uniqueReads = 0
    for _ in pairs(targetReadBytes) do
        uniqueReads = uniqueReads + 1
    end
    report[#report + 1] = string.format(
        "targetUniqueBytesRead=%d/%d",
        uniqueReads,
        #TARGET_RECORD
    )
    if targetReadEvents < #TARGET_RECORD then
        failures[#failures + 1] =
            "too few target record reads: " .. tostring(targetReadEvents)
    end
    if uniqueReads ~= #TARGET_RECORD then
        failures[#failures + 1] =
            "incomplete target record read coverage: " .. tostring(uniqueReads)
    end
    if targetReadMismatches ~= 0 then
        failures[#failures + 1] =
            "target read value mismatches: " ..
            tostring(targetReadMismatches)
    end

    for page = 1, 3 do
        local pageData = pageEvidence[page]
        if pageData == nil then
            failures[#failures + 1] =
                "missing completed target page " .. tostring(page)
        else
            report[#report + 1] = string.format(
                "page%d frame=%d signature=%08X bgBase=$%04X",
                page,
                pageData.frame,
                pageData.signature,
                pageData.patternBase
            )
            for _, glyph in ipairs(glyphs) do
                local glyphData = pageData.glyphs[glyph.code]
                local required = requiredOnPage(page, glyph.code)
                report[#report + 1] = string.format(
                    "page%d glyph=%s code=$%02X required=%s " ..
                    "sourcePlane0=%d/8 sourcePlane1=%d/8 events=%d " ..
                    "ppuWritesNear=%d refs=%s",
                    page,
                    glyph.label,
                    glyph.code,
                    tostring(required),
                    glyphData.sourcePlane0,
                    glyphData.sourcePlane1,
                    glyphData.sourceEvents,
                    glyphData.ppuWritesNearSourceReads,
                    formatReferences(glyphData.references)
                )
                if required and (
                    glyphData.sourcePlane0 ~= 8 or
                    glyphData.sourceEvents < 16
                ) then
                    failures[#failures + 1] = string.format(
                        "page %d %s font bitmap was not fully read",
                        page,
                        glyph.label
                    )
                end
                if required and glyphData.ppuWritesNearSourceReads < 32 then
                    failures[#failures + 1] = string.format(
                        "page %d %s font read was not followed by CHR writes",
                        page,
                        glyph.label
                    )
                end
                local referenceCount = 0
                local matchingReferences = 0
                for _, reference in ipairs(glyphData.references) do
                    referenceCount = referenceCount + 1
                    if reference.matches then
                        matchingReferences = matchingReferences + 1
                    end
                end
                if required and (
                    referenceCount == 0 or
                    matchingReferences ~= referenceCount
                ) then
                    failures[#failures + 1] = string.format(
                        "page %d %s generated tiles not referenced by dialogue",
                        page,
                        glyph.label
                    )
                end
            end
        end
    end

    for _, glyph in ipairs(glyphs) do
        local encodedRead = false
        for index = 1, #TARGET_RECORD do
            if string.byte(TARGET_RECORD, index) == glyph.code and
               targetReadBytes[index - 1] then
                encodedRead = true
                break
            end
        end
        report[#report + 1] = string.format(
            "glyph=%s code=$%02X romOffset=$%06X romTile=%s " ..
            "encodedTargetByteRead=%s",
            glyph.label,
            glyph.code,
            glyph.romOffset,
            glyph.expectedHex,
            tostring(encodedRead)
        )
        report[#report + 1] = string.format(
            "glyph=%s sourceCpu=$%04X-$%04X " ..
            "sourceReadEvents=%d sourcePlane0Unique=%d/8 " ..
            "sourcePlane1Unique=%d/8 " ..
            "ppuWritesNearSourceReads=%d",
            glyph.label,
            glyph.cpuFirst,
            glyph.cpuLast,
            glyph.sourceReadEvents,
            (function()
                local count = 0
                for index in pairs(glyph.sourceReadBytes) do
                    if index < 8 then
                        count = count + 1
                    end
                end
                return count
            end)(),
            (function()
                local count = 0
                for index in pairs(glyph.sourceReadBytes) do
                    if index >= 8 then
                        count = count + 1
                    end
                end
                return count
            end)(),
            glyph.ppuWritesNearSourceReads
        )
        if not encodedRead then
            failures[#failures + 1] =
                glyph.label .. " code was not read from target record"
        end
    end

    if #failures == 0 then
        report[#report + 1] = "result=PASS"
    else
        report[#report + 1] = "result=FAIL"
        report[#report + 1] = "failures=" .. table.concat(failures, "; ")
    end
    writeText(
        "french_charset_exhaustive_validation.txt",
        table.concat(report, "\n") .. "\n"
    )

    local state = emu.getState()
    if #failures == 0 then
        print(string.format(
            "POKEMON_FRENCH_CHARSET_EXHAUSTIVE_PASS mapper=163 region=%s " ..
            "frames=%d nmi=%d pages=3 record=$%06X cpu=$%04X-$%04X " ..
            "reads=%d unique=%d glyphs=16 sameFrameEvidence=true " ..
            "mode=assisted_transient_prg_record restored=true",
            tostring(state["region"]),
            frames,
            nmiCount,
            targetFileOffset,
            targetCpuFirst,
            targetCpuLast,
            targetReadEvents,
            uniqueReads
        ))
        emu.stop(0)
    else
        print(
            "POKEMON_FRENCH_CHARSET_EXHAUSTIVE_FAIL mapper=163 region=" ..
            tostring(state["region"]) .. " " ..
            table.concat(failures, "; ")
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

emu.addMemoryCallback(function(address, value)
    if not mapperBankKnown or currentBank() ~= targetPair then
        return
    end
    local index = address - targetCpuFirst
    local expected = string.byte(TARGET_RECORD, index + 1)
    targetReadEvents = targetReadEvents + 1
    targetReadBytes[index] = true
    if value ~= expected then
        targetReadMismatches = targetReadMismatches + 1
    end
    if targetFirstReadFrame == nil then
        targetFirstReadFrame = frames
        targetActive = true
        print(string.format(
            "POKEMON_FRENCH_CHARSET_RECORD_READ_START frame=%d " ..
            "pair=%d cpu=$%04X file=$%06X",
            frames,
            targetPair,
            targetCpuFirst,
            targetFileOffset
        ))
    end
    targetLastReadFrame = frames
end, emu.callbackType.read, targetCpuFirst, targetCpuLast)

local fontCpuFirst = glyphs[1].cpuFirst
local fontCpuLast = glyphs[#glyphs].cpuLast
emu.addMemoryCallback(function(address, value)
    if currentBank() ~= glyphs[1].pair then
        return
    end
    for _, glyph in ipairs(glyphs) do
        if address >= glyph.cpuFirst and address <= glyph.cpuLast then
            local index = address - glyph.cpuFirst
            local expected = string.byte(glyph.tile, index + 1)
            if value ~= expected then
                error(string.format(
                    "live font read mismatch %s $%04X: $%02X != $%02X",
                    glyph.label,
                    address,
                    value,
                    expected
                ))
            end
            glyph.sourceReadEvents = glyph.sourceReadEvents + 1
            glyph.sourceReadBytes[index] = true
            glyph.sourceReadLog[#glyph.sourceReadLog + 1] = {
                frame = frames,
                index = index,
            }
            glyph.lastSourceReadFrame = frames
            return
        end
    end
end, emu.callbackType.read, fontCpuFirst, fontCpuLast)

emu.addMemoryCallback(function(address)
    if (address & 0x07) ~= 0x07 then
        return
    end
    ppuDataWrites = ppuDataWrites + 1
    for _, glyph in ipairs(glyphs) do
        if glyph.lastSourceReadFrame ~= nil and
           frames - glyph.lastSourceReadFrame <= 1 then
            glyph.ppuWritesNearSourceReads =
                glyph.ppuWritesNearSourceReads + 1
            glyph.ppuWriteLog[#glyph.ppuWriteLog + 1] = frames
        end
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
    end

    if not targetActive and frames >= 360 and
       frames <= 5200 and (frames - 360) % 30 == 0 then
        desiredInput.a = true
    elseif not targetActive and frames >= 363 and
       frames <= 5203 and (frames - 363) % 30 == 0 then
        desiredInput.a = false
    end

    if advanceAt ~= nil then
        if frames == advanceAt then
            desiredInput.a = true
        elseif frames == advanceAt + 3 then
            desiredInput.a = false
            advanceAt = nil
        end
    end

    if targetActive and promptArrowVisible() then
        local signature = dialoguePixelSignature()
        if signature ~= lastPromptSignature then
            lastPromptSignature = signature
            targetPage = targetPage + 1
            if targetPage <= 3 then
                captureTargetPage(targetPage, signature)
                if targetPage < 3 then
                    advanceAt = frames + 60
                elseif not finished then
                    finished = true
                    finalize()
                    return
                end
            end
        end
    end

    if targetActive and targetPage == 2 and
       targetReadBytes[#TARGET_RECORD - 1] then
        local signature = dialoguePixelSignature()
        if signature == finalPageSignature then
            finalPageStableFrames = finalPageStableFrames + 1
        else
            finalPageSignature = signature
            finalPageStableFrames = 1
        end
        if finalPageStableFrames >= 12 and not finished then
            targetPage = 3
            captureTargetPage(3, signature)
            finished = true
            finalize()
            return
        end
    end

    if frames == 6500 and not finished then
        local restoreOk = restoreTransientRecord()
        writeBinary(
            "french_charset_exhaustive_timeout.png",
            emu.takeScreenshot()
        )
        print(string.format(
            "POKEMON_FRENCH_CHARSET_EXHAUSTIVE_FAIL mapper=163 region=%s " ..
            "timeout frames=%d targetActive=%s targetPage=%d reads=%d " ..
            "bank=%d restored=%s",
            tostring(emu.getState()["region"]),
            frames,
            tostring(targetActive),
            targetPage,
            targetReadEvents,
            currentBank(),
            tostring(restoreOk)
        ))
        emu.stop(1)
    end
end, emu.eventType.endFrame)
