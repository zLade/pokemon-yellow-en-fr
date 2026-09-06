-- Passive access probe for the 317 structured double-byte glyph records that
-- remain in PRG pairs 6 and 7 of Pokemon Yellow NES (mapper 163).
--
-- The candidate ROM is parsed directly from POKEMON_YELLOW_MESEN_ROM.  During
-- emulation, callbacks cover only the merged CPU ranges corresponding to the
-- 317 records.  emu.convertAddress then confirms the physical PRG-ROM offset.
-- The probe never writes game RAM or mapper registers: progression is done
-- exclusively with controller input.
--
-- Runtime coverage is scenario coverage, not a global reachability proof.
-- In particular, an "untouched" CSV row only means that this intro/new-game
-- run did not read the record.
--
-- POKEMON_YELLOW_GLYPH_SCENARIO selects one controller-only path:
--   intro        - title and early introduction (default)
--   bedroom_menu - deterministic new-game progression, then player menu
--   save_flow    - same progression, then SAVE selection/confirmation
-- A battle path is intentionally not guessed: no deterministic controller-only
-- route to one is currently established for this bootleg.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local romPath = os.getenv("POKEMON_YELLOW_MESEN_ROM")
if romPath == nil or romPath == "" then
    error("POKEMON_YELLOW_MESEN_ROM is not set")
end
local scenarioName =
    os.getenv("POKEMON_YELLOW_GLYPH_SCENARIO") or "intro"
local scenarioDefinitions = {
    intro = {
        finalFrame = 1920,
        minimumDistinctScreens = 5,
        captures = {
            [150] = true, [300] = true, [480] = true, [660] = true,
            [840] = true, [1020] = true, [1200] = true,
            [1440] = true, [1680] = true, [1920] = true,
        },
    },
    bedroom_menu = {
        finalFrame = 5200,
        minimumDistinctScreens = 6,
        captures = {
            [150] = true, [300] = true, [1200] = true, [2400] = true,
            [3600] = true, [4500] = true, [4800] = true,
            [5100] = true, [5200] = true,
        },
    },
    save_flow = {
        finalFrame = 6400,
        minimumDistinctScreens = 7,
        captures = {
            [150] = true, [300] = true, [1200] = true, [2400] = true,
            [4000] = true, [4800] = true, [5200] = true,
            [5750] = true, [6100] = true, [6400] = true,
        },
    },
}
local scenario = scenarioDefinitions[scenarioName]
if scenario == nil then
    error(
        "unknown POKEMON_YELLOW_GLYPH_SCENARIO: " ..
        tostring(scenarioName)
    )
end
print("POKEMON_GLYPH_ACCESS_LOAD rom=" .. romPath)
print("POKEMON_GLYPH_ACCESS_SCENARIO name=" .. scenarioName)

local INES_HEADER_SIZE = 16
local PRG_PAIR_SIZE = 0x8000
local EXPECTED_RECORD_COUNT = 317
local EXPECTED_GLYPH_PAIR_COUNT = 2707
local EXPECTED_PAYLOAD_SIZE = 6711
-- Polynomial hash (multiplier 257, modulo 2^32) of the canonical span list:
-- one uppercase "START-END" file-offset range per line, no trailing newline.
-- The SHA-256 of the same list is:
-- 5a9a4ab9e7f98d1ba0d21fe508a0056a70544977ee5a6cf5c7aad9343b8585c2
local EXPECTED_SPAN_HASH = 0x21C458E8

local function readFile(path)
    local file = assert(io.open(path, "rb"))
    local data = file:read("*a")
    file:close()
    return data
end

local function outputPath(filename)
    local last = string.sub(outputDirectory, -1)
    if last == "\\" or last == "/" then
        return outputDirectory .. filename
    end
    if string.find(outputDirectory, "/", 1, true) ~= nil and
       string.find(outputDirectory, "\\", 1, true) == nil then
        return outputDirectory .. "/" .. filename
    end
    return outputDirectory .. "\\" .. filename
end

local function writeFile(filename, data)
    local file = assert(io.open(outputPath(filename), "wb"))
    file:write(data)
    file:close()
end

local function polynomialHash(data)
    local hash = 0
    for index = 1, #data do
        hash = (hash * 257 + string.byte(data, index)) % 0x100000000
    end
    return hash
end

local romData = readFile(romPath)
print("POKEMON_GLYPH_ACCESS_ROM bytes=" .. tostring(#romData))
if #romData < INES_HEADER_SIZE or
   string.sub(romData, 1, 4) ~= string.char(0x4E, 0x45, 0x53, 0x1A) then
    error("candidate is not an iNES ROM: " .. romPath)
end
local records = {}
local recordIndexByFileOffset = {}
local readCallbackRangeCount = 0
local readCallbackByteCount = 0
local frames = 0

local function parsePayload(recordStart, recordEnd, pair)
    local payloadSize = recordEnd - recordStart
    if payloadSize < 1 or payloadSize > 320 then
        return
    end

    local offset = recordStart
    local glyphCount = 0
    local valid = true
    while offset < recordEnd do
        local value = string.byte(romData, offset + 1)
        if value >= 0xB0 and value <= 0xBF then
            if offset + 1 >= recordEnd then
                valid = false
                break
            end
            glyphCount = glyphCount + 1
            offset = offset + 2
        elseif value < 0x80 then
            offset = offset + 1
        else
            valid = false
            break
        end
    end

    if valid and glyphCount > 0 then
        records[#records + 1] = {
            startOffset = recordStart,
            endOffset = recordEnd,
            pair = pair,
            glyphCount = glyphCount,
            readEvents = 0,
            touchedOffsets = {},
            firstFrame = nil,
            lastFrame = nil,
        }
    end
end

local parsePair = 6
local parsePairEnd = INES_HEADER_SIZE + 7 * PRG_PAIR_SIZE
local parseRecordStart = INES_HEADER_SIZE + 6 * PRG_PAIR_SIZE
local parseCursor = parseRecordStart
local inventoryReady = false

local function onCandidateRecordRead(address)
    local converted = emu.convertAddress(address, emu.memType.nesMemory)
    if converted == nil or converted.memType ~= emu.memType.nesPrgRom then
        return
    end

    local fileOffset = INES_HEADER_SIZE + converted.address
    local recordIndex = recordIndexByFileOffset[fileOffset]
    if recordIndex == nil then
        return
    end

    local record = records[recordIndex]
    record.readEvents = record.readEvents + 1
    record.touchedOffsets[fileOffset] = true
    if record.firstFrame == nil then
        record.firstFrame = frames
    end
    record.lastFrame = frames
end

local function registerTargetedReadCallbacks()
    local cpuSpans = {}
    for recordIndex, record in ipairs(records) do
        for fileOffset = record.startOffset, record.endOffset - 1 do
            recordIndexByFileOffset[fileOffset] = recordIndex
        end

        local pairStart =
            INES_HEADER_SIZE + record.pair * PRG_PAIR_SIZE
        cpuSpans[#cpuSpans + 1] = {
            first = 0x8000 + record.startOffset - pairStart,
            last = 0x8000 + record.endOffset - pairStart - 1,
        }
    end

    table.sort(cpuSpans, function(left, right)
        if left.first == right.first then
            return left.last < right.last
        end
        return left.first < right.first
    end)

    local merged = {}
    for _, span in ipairs(cpuSpans) do
        local previous = merged[#merged]
        if previous == nil or span.first > previous.last + 1 then
            merged[#merged + 1] = {
                first = span.first,
                last = span.last,
            }
        elseif span.last > previous.last then
            previous.last = span.last
        end
    end

    for _, span in ipairs(merged) do
        emu.addMemoryCallback(
            onCandidateRecordRead,
            emu.callbackType.read,
            span.first,
            span.last
        )
        readCallbackByteCount =
            readCallbackByteCount + span.last - span.first + 1
    end
    readCallbackRangeCount = #merged
end

local function finalizeInventory()
    local glyphPairCount = 0
    local payloadSize = 0
    local spanLines = {}
    for _, record in ipairs(records) do
        glyphPairCount = glyphPairCount + record.glyphCount
        payloadSize = payloadSize + record.endOffset - record.startOffset
        spanLines[#spanLines + 1] = string.format(
            "%06X-%06X",
            record.startOffset,
            record.endOffset
        )
    end
    local spanHash = polynomialHash(table.concat(spanLines, "\n"))

    if #records ~= EXPECTED_RECORD_COUNT or
       glyphPairCount ~= EXPECTED_GLYPH_PAIR_COUNT or
       payloadSize ~= EXPECTED_PAYLOAD_SIZE or
       spanHash ~= EXPECTED_SPAN_HASH then
        error(string.format(
            "non-canonical glyph inventory: records=%d glyphPairs=%d " ..
            "payload=%d spanHash=%08X",
            #records,
            glyphPairCount,
            payloadSize,
            spanHash
        ))
    end
    print(string.format(
        "POKEMON_GLYPH_ACCESS_READY records=%d glyphPairs=%d payload=%d " ..
        "spanHash=%08X",
        #records,
        glyphPairCount,
        payloadSize,
        spanHash
    ))
    registerTargetedReadCallbacks()
    print(string.format(
        "POKEMON_GLYPH_ACCESS_TRACE ranges=%d cpuBytes=%d payloadBytes=%d",
        readCallbackRangeCount,
        readCallbackByteCount,
        payloadSize
    ))
    inventoryReady = true
end

local function parseInventorySlice()
    -- Spread ROM parsing over several end-frame callbacks so Mesen's
    -- one-second Lua watchdog cannot abort a valid exhaustive inventory.
    for _ = 1, 512 do
        if parsePair > 7 then
            finalizeInventory()
            return
        end
        if parsePairEnd > #romData then
            error(string.format(
                "candidate is too short for PRG pair %d: size=%d",
                parsePair,
                #romData
            ))
        end

        if parseCursor >= parsePairEnd then
            -- Preserve a possible final unterminated payload at bank end.
            parsePayload(parseRecordStart, parsePairEnd, parsePair)
            parsePair = parsePair + 1
            parsePairEnd =
                INES_HEADER_SIZE + (parsePair + 1) * PRG_PAIR_SIZE
            parseRecordStart =
                INES_HEADER_SIZE + parsePair * PRG_PAIR_SIZE
            parseCursor = parseRecordStart
        else
            local value = string.byte(romData, parseCursor + 1)
            if value >= 0xB0 and value <= 0xBF then
                -- The low byte may itself be 0x0D; it is data, not a
                -- delimiter (e.g. B1 0D in "Powder Snow").
                if parseCursor + 1 < parsePairEnd then
                    parseCursor = parseCursor + 2
                else
                    parseCursor = parseCursor + 1
                end
            elseif value == 0x0D then
                parsePayload(parseRecordStart, parseCursor, parsePair)
                parseCursor = parseCursor + 1
                parseRecordStart = parseCursor
            else
                parseCursor = parseCursor + 1
            end
        end
    end
end

local nmiCount = 0
local screenshotHashes = {}
local screenshotCount = 0
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

local screenshotFrames = scenario.captures

local function pulseAt(frame, button, duration)
    if frames == frame then
        desiredInput[button] = true
    elseif frames == frame + duration then
        desiredInput[button] = false
    end
end

local function tableSize(tableValue)
    local count = 0
    for _ in pairs(tableValue) do
        count = count + 1
    end
    return count
end

local function exportCsv()
    local lines = {
        "scenario,record_index,pair,file_start_inclusive,file_end_exclusive," ..
        "payload_bytes,glyph_pairs,status,read_events," ..
        "unique_bytes_touched,coverage_percent,first_frame,last_frame",
    }
    local touchedRecordCount = 0
    local totalRecordReadEvents = 0
    local totalRecordBytesTouched = 0

    for recordIndex, record in ipairs(records) do
        local uniqueBytes = tableSize(record.touchedOffsets)
        local status = "untouched"
        if record.readEvents > 0 then
            status = "touched"
            touchedRecordCount = touchedRecordCount + 1
        end
        totalRecordReadEvents =
            totalRecordReadEvents + record.readEvents
        totalRecordBytesTouched = totalRecordBytesTouched + uniqueBytes
        local firstFrame = ""
        local lastFrame = ""
        if record.firstFrame ~= nil then
            firstFrame = tostring(record.firstFrame)
            lastFrame = tostring(record.lastFrame)
        end
        lines[#lines + 1] = string.format(
            "%s,%d,%d,0x%06X,0x%06X,%d,%d,%s,%d,%d,%.2f,%s,%s",
            scenarioName,
            recordIndex,
            record.pair,
            record.startOffset,
            record.endOffset,
            record.endOffset - record.startOffset,
            record.glyphCount,
            status,
            record.readEvents,
            uniqueBytes,
            uniqueBytes * 100 / (record.endOffset - record.startOffset),
            firstFrame,
            lastFrame
        )
    end

    writeFile("glyph_access_records.csv", table.concat(lines, "\r\n") .. "\r\n")
    return touchedRecordCount, totalRecordReadEvents,
        totalRecordBytesTouched
end

emu.addEventCallback(function()
    nmiCount = nmiCount + 1
end, emu.eventType.nmi)

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if not inventoryReady then
        local parseOk, parseError = pcall(parseInventorySlice)
        if not parseOk then
            print(
                "POKEMON_GLYPH_ACCESS_FAIL parser=" ..
                tostring(parseError)
            )
            emu.stop(1)
            return
        end
        if inventoryReady then
            nmiCount = 0
        end
        return
    end

    frames = frames + 1

    pulseAt(180, "start", 4)
    if scenarioName == "intro" then
        -- Same human-safe cadence as the established intro probe.
        for pulseFrame = 360, 1860, 90 do
            pulseAt(pulseFrame, "a", 3)
        end
    else
        -- Reuse the deterministic new-game progression exercised by the
        -- player-menu and battery-save regression probes.
        for pulseFrame = 360, 4500, 30 do
            pulseAt(pulseFrame, "a", 3)
        end
        pulseAt(4900, "start", 4)
        if scenarioName == "save_flow" then
            for pulseFrame = 5300, 5660, 90 do
                pulseAt(pulseFrame, "down", 4)
            end
            pulseAt(5800, "a", 4)
            pulseAt(6100, "a", 4)
        end
    end
    if screenshotFrames[frames] then
        local png = emu.takeScreenshot()
        screenshotHashes[polynomialHash(png)] = true
        screenshotCount = screenshotCount + 1
    end

    if frames ~= scenario.finalFrame then
        return
    end

    local touchedRecordCount, recordReadEvents, recordBytesTouched =
        exportCsv()
    local distinctScreens = tableSize(screenshotHashes)
    local failures = {}

    if nmiCount < scenario.finalFrame - 100 then
        failures[#failures + 1] = "too few NMIs: " .. tostring(nmiCount)
    end
    if screenshotCount ~= tableSize(screenshotFrames) or
       distinctScreens < scenario.minimumDistinctScreens then
        failures[#failures + 1] = string.format(
            "scenario did not progress: screenshots=%d distinct=%d",
            screenshotCount,
            distinctScreens
        )
    end
    if readCallbackRangeCount < 1 then
        failures[#failures + 1] = "no targeted PRG callback range"
    end

    local summary = string.format(
        "mapper=163 region=%s scenario=%s frames=%d nmi=%d records=%d " ..
        "touchedRecords=%d recordReads=%d recordBytesTouched=%d " ..
        "callbackRanges=%d callbackCpuBytes=%d " ..
        "csv=glyph_access_records.csv",
        tostring(emu.getState()["region"]),
        scenarioName,
        frames,
        nmiCount,
        #records,
        touchedRecordCount,
        recordReadEvents,
        recordBytesTouched,
        readCallbackRangeCount,
        readCallbackByteCount
    )

    if #failures == 0 then
        print("POKEMON_GLYPH_ACCESS_PASS " .. summary)
        emu.stop(0)
    else
        print(
            "POKEMON_GLYPH_ACCESS_FAIL " .. summary .. " " ..
            table.concat(failures, "; ")
        )
        emu.stop(1)
    end
end, emu.eventType.endFrame)
