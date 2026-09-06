-- Shared assisted-runtime support for critical restored payloads.
--
-- The caller selects one 32 KiB PRG pair.  This module verifies the final
-- payload bytes against the disk ROM, temporarily repoints known dialogue
-- harness references in Mesen's loaded PRG image, observes normal CPU reads
-- of every payload byte, and restores every pointer before completion.

local Runtime = {}
Runtime.__index = Runtime

local function readFile(path)
    local file = assert(io.open(path, "rb"))
    local data = file:read("*a")
    file:close()
    return data
end

local function writeText(outputDirectory, filename, data)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "w"))
    file:write(data)
    file:close()
end

local function fromHex(hex)
    if #hex % 2 ~= 0 or string.find(hex, "[^0-9a-fA-F]") ~= nil then
        error("invalid payload hexadecimal data")
    end
    return (string.gsub(hex, "..", function(pair)
        return string.char(tonumber(pair, 16))
    end))
end

local function splitTabs(line)
    local fields = {}
    local startAt = 1
    while true do
        local tabAt = string.find(line, "\t", startAt, true)
        if tabAt == nil then
            fields[#fields + 1] = string.sub(line, startAt)
            return fields
        end
        fields[#fields + 1] = string.sub(line, startAt, tabAt - 1)
        startAt = tabAt + 1
    end
end

local function parseSpec(path, selectedGroup)
    local data = readFile(path):gsub("\r\n", "\n"):gsub("\r", "\n")
    local lines = {}
    for line in (data .. "\n"):gmatch("(.-)\n") do
        lines[#lines + 1] = line
    end
    if lines[1] ~= "schema\tnj046-en2-critical-restoration-runtime/v1" then
        error("unexpected critical restoration runtime schema")
    end
    local candidate = splitTabs(lines[2] or "")
    if #candidate ~= 2 or candidate[1] ~= "candidate_sha256" or
       not candidate[2]:match("^[0-9a-fA-F]+$") or #candidate[2] ~= 64 then
        error("invalid candidate SHA-256 in restoration runtime spec")
    end
    local header = splitTabs(lines[3] or "")
    local expectedHeader = {
        "group",
        "stable_key",
        "harness_reference_hex",
        "target_file_offset_hex",
        "target_prg_offset_hex",
        "target_cpu_address_hex",
        "payload_length",
        "payload_sha256",
        "payload_hex",
    }
    if #header ~= #expectedHeader then
        error("invalid restoration runtime TSV column count")
    end
    for index, expected in ipairs(expectedHeader) do
        if header[index] ~= expected then
            error("invalid restoration runtime TSV header " .. tostring(index))
        end
    end
    local rows = {}
    for lineIndex = 4, #lines do
        local line = lines[lineIndex]
        if line ~= "" then
            local fields = splitTabs(line)
            if #fields ~= #expectedHeader then
                error("invalid restoration runtime row " .. tostring(lineIndex))
            end
            local row = {}
            for index, name in ipairs(expectedHeader) do
                row[name] = fields[index]
            end
            if row.group == selectedGroup then
                row.harnessReference = tonumber(
                    row.harness_reference_hex:sub(3), 16
                )
                row.targetFileOffset = tonumber(
                    row.target_file_offset_hex:sub(3), 16
                )
                row.targetPrgOffset = tonumber(
                    row.target_prg_offset_hex:sub(3), 16
                )
                row.targetCpuAddress = tonumber(
                    row.target_cpu_address_hex:sub(3), 16
                )
                row.payloadLength = tonumber(row.payload_length, 10)
                row.payload = fromHex(row.payload_hex)
                if row.payloadLength ~= #row.payload then
                    error("payload length mismatch for " .. row.stable_key)
                end
                rows[#rows + 1] = row
            end
        end
    end
    return candidate[2]:lower(), rows
end

local function pairForFileOffset(offset)
    return (offset - 16) // 0x8000
end

function Runtime.new(options)
    local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
    local romPath = os.getenv("POKEMON_YELLOW_MESEN_ROM")
    local inputPath = os.getenv("POKEMON_YELLOW_MESEN_INPUT")
    if outputDirectory == nil or outputDirectory == "" then
        error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
    end
    if romPath == nil or romPath == "" then
        error("POKEMON_YELLOW_MESEN_ROM is not set")
    end
    if inputPath == nil or inputPath == "" then
        error("POKEMON_YELLOW_MESEN_INPUT is not set")
    end
    local candidateSha256, rows = parseSpec(inputPath, options.group)
    if #rows ~= options.expectedCount then
        error(
            options.group .. " restoration count=" .. tostring(#rows) ..
            ", expected " .. tostring(options.expectedCount)
        )
    end
    local rom = readFile(romPath)
    if string.sub(rom, 1, 4) ~= "NES\026" then
        error("critical restoration probe requires an iNES ROM")
    end
    local byHarness = {}
    for _, row in ipairs(rows) do
        if byHarness[row.harnessReference] ~= nil then
            error("duplicate restoration harness reference")
        end
        byHarness[row.harnessReference] = row
        if pairForFileOffset(row.harnessReference) ~=
           pairForFileOffset(row.targetFileOffset) then
            error("cross-pair restoration target for " .. row.stable_key)
        end
        if row.targetPrgOffset ~= row.targetFileOffset - 16 then
            error("PRG/file offset mismatch for " .. row.stable_key)
        end
        local pairStart =
            16 + pairForFileOffset(row.targetFileOffset) * 0x8000
        local expectedCpu = 0x8000 + row.targetFileOffset - pairStart
        if row.targetCpuAddress ~= expectedCpu then
            error("CPU target mismatch for " .. row.stable_key)
        end
        local diskPayload = string.sub(
            rom,
            row.targetFileOffset + 1,
            row.targetFileOffset + row.payloadLength
        )
        if diskPayload ~= row.payload or
           string.byte(rom, row.targetFileOffset + row.payloadLength + 1) ~= 0x0D then
            error("disk payload mismatch for " .. row.stable_key)
        end
        row.harnessPrgOffset = row.harnessReference - 16
        row.originalLow = string.byte(rom, row.harnessReference + 1)
        row.originalHigh = string.byte(rom, row.harnessReference + 2)
        row.expectedLow = row.targetCpuAddress & 0xFF
        row.expectedHigh = (row.targetCpuAddress >> 8) & 0xFF
        row.readBytes = {}
        row.readEvents = 0
    end
    local self = setmetatable({
        group = options.group,
        expectedCount = options.expectedCount,
        outputDirectory = outputDirectory,
        candidateSha256 = candidateSha256,
        rows = rows,
        patchWrites = 0,
        restoreWrites = 0,
        installed = false,
        restored = false,
    }, Runtime)
    emu.addMemoryCallback(function(address, value)
        self:_observeRead(address, value)
    end, emu.callbackType.read, 0x8000, 0xFFFF)
    return self
end

function Runtime:_loadedByte(offset)
    return emu.read(offset, emu.memType.nesPrgRom)
end

function Runtime:_writeLoadedByte(offset, value, restoring)
    if self:_loadedByte(offset) ~= value then
        emu.write(offset, value, emu.memType.nesPrgRom)
        if restoring then
            self.restoreWrites = self.restoreWrites + 1
        else
            self.patchWrites = self.patchWrites + 1
        end
    end
end

function Runtime:install()
    if self.installed then
        error("critical restoration pointers already installed")
    end
    for _, row in ipairs(self.rows) do
        if self:_loadedByte(row.harnessPrgOffset) ~= row.originalLow or
           self:_loadedByte(row.harnessPrgOffset + 1) ~= row.originalHigh then
            error("loaded harness differs from disk for " .. row.stable_key)
        end
        self:_writeLoadedByte(row.harnessPrgOffset, row.expectedLow, false)
        self:_writeLoadedByte(row.harnessPrgOffset + 1, row.expectedHigh, false)
        if self:_loadedByte(row.harnessPrgOffset) ~= row.expectedLow or
           self:_loadedByte(row.harnessPrgOffset + 1) ~= row.expectedHigh then
            error("failed to install pointer for " .. row.stable_key)
        end
    end
    self.installed = true
end

function Runtime:_observeRead(address, value)
    local converted = emu.convertAddress(address, emu.memType.nesMemory)
    if converted == nil or converted.memType ~= emu.memType.nesPrgRom then
        return
    end
    for _, row in ipairs(self.rows) do
        local first = row.targetPrgOffset
        local last = first + row.payloadLength
        if converted.address >= first and converted.address <= last then
            local index = converted.address - first
            local expected = index == row.payloadLength
                and 0x0D
                or string.byte(row.payload, index + 1)
            if value ~= expected then
                error("live payload read mismatch for " .. row.stable_key)
            end
            row.readBytes[index] = true
            row.readEvents = row.readEvents + 1
            return
        end
    end
end

function Runtime:allRead()
    for _, row in ipairs(self.rows) do
        for index = 0, row.payloadLength do
            if not row.readBytes[index] then
                return false
            end
        end
    end
    return true
end

function Runtime:restore()
    if self.restored then
        return true
    end
    for _, row in ipairs(self.rows) do
        self:_writeLoadedByte(row.harnessPrgOffset, row.originalLow, true)
        self:_writeLoadedByte(
            row.harnessPrgOffset + 1,
            row.originalHigh,
            true
        )
    end
    for _, row in ipairs(self.rows) do
        if self:_loadedByte(row.harnessPrgOffset) ~= row.originalLow or
           self:_loadedByte(row.harnessPrgOffset + 1) ~= row.originalHigh then
            return false
        end
    end
    self.restored = true
    return true
end

function Runtime:writeReport(filename, extraLines)
    local lines = {
        "schema=nj046-en2-critical-restoration-runtime-result/v1",
        "group=" .. self.group,
        "candidate_sha256=" .. self.candidateSha256,
        "mode=assisted_transient_prg_pointer_patch",
        "writes_to_game_ram=0",
        "payload_count=" .. tostring(#self.rows),
        "patch_writes=" .. tostring(self.patchWrites),
        "restore_writes=" .. tostring(self.restoreWrites),
        "restored=" .. tostring(self.restored),
    }
    for _, row in ipairs(self.rows) do
        local unique = 0
        for _ in pairs(row.readBytes) do
            unique = unique + 1
        end
        lines[#lines + 1] = string.format(
            "payload=%s harness=0x%06X target=0x%06X " ..
            "length=%d unique_reads=%d/%d events=%d",
            row.stable_key,
            row.harnessReference,
            row.targetFileOffset,
            row.payloadLength,
            unique,
            row.payloadLength + 1,
            row.readEvents
        )
    end
    for _, line in ipairs(extraLines or {}) do
        lines[#lines + 1] = line
    end
    writeText(
        self.outputDirectory,
        filename,
        table.concat(lines, "\n") .. "\n"
    )
end

return Runtime
