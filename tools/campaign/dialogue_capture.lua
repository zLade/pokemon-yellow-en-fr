-- Passive, natural dialogue-page observer for Mesen 2.2.1.
--
-- The observer never writes emulated memory.  It locates exact translated
-- records in the disk ROM, follows mapper-163 bank selection, observes the
-- CPU reading those records, and captures the completed pages produced by
-- the game.  The first rendered page determines whether the engine used a
-- 17+19 or 19+19 column contract.

local DialogueCapture = {}
DialogueCapture.__index = DialogueCapture

local LAYOUTS = {
    {
        name = "17_19",
        first_line_width = 17,
        first_page_bytes = 36,
        subsequent_page_bytes = 38,
        tile_base = 0x40,
    },
    {
        name = "19_19",
        first_line_width = 19,
        first_page_bytes = 19,
        subsequent_page_bytes = 19,
        tile_base = 0xD4,
    },
}

local TILE_BASES = {0x40, 0xD4}

local function requireNonEmptyString(value, label)
    if type(value) ~= "string" or value == "" then
        error(label .. " must be a non-empty string", 3)
    end
end

local function fromHex(hex)
    requireNonEmptyString(hex, "payload_hex")
    if #hex % 2 ~= 0 or string.find(hex, "[^0-9a-fA-F]") ~= nil then
        error("invalid hexadecimal payload", 3)
    end
    return (string.gsub(hex, "..", function(pair)
        return string.char(tonumber(pair, 16))
    end))
end

local function toHex(data)
    return (string.gsub(data, ".", function(value)
        return string.format("%02X", string.byte(value))
    end))
end

local function readFile(path)
    local file = assert(io.open(path, "rb"))
    local data = file:read("*a")
    file:close()
    return data
end

local function writeBinary(path, data)
    local file = assert(io.open(path, "wb"))
    file:write(data)
    file:close()
end

local function writeText(path, data)
    local file = assert(io.open(path, "w"))
    file:write(data)
    file:close()
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

local function checksum(memoryType, first, last)
    local hash = 0
    for address = first, last do
        hash = (
            hash * 257 + emu.read(address, memoryType)
        ) % 0x100000000
    end
    return hash
end

local function currentPc()
    return emu.getState()["cpu.pc"] or 0
end

local function pcCountsText(counts)
    local pcs = {}
    for pc in pairs(counts) do
        pcs[#pcs + 1] = pc
    end
    table.sort(pcs)
    local rows = {}
    for _, pc in ipairs(pcs) do
        rows[#rows + 1] = string.format(
            "%04X:%d",
            pc,
            counts[pc]
        )
    end
    return table.concat(rows, ",")
end

local function copyInput(input)
    return {
        a = input.a == true,
        b = input.b == true,
        select = input.select == true,
        start = input.start == true,
        up = input.up == true,
        down = input.down == true,
        left = input.left == true,
        right = input.right == true,
    }
end

local function promptArrowVisible()
    local sprite = 63 * 4
    local y = emu.read(sprite, emu.memType.nesSpriteRam)
    local dialogueArrowY =
        (y >= 190 and y <= 193)
        or (y >= 222 and y <= 225)
    return dialogueArrowY
        and emu.read(
            sprite + 1,
            emu.memType.nesSpriteRam
        ) == 0xFF
        and emu.read(
            sprite + 3,
            emu.memType.nesSpriteRam
        ) == 208
end

local function dialoguePixelSignature()
    local hash = 0
    for y = 165, 235, 2 do
        for x = 40, 199, 2 do
            hash = (hash * 257 + emu.getPixel(x, y)) % 0x100000000
        end
    end
    return hash
end

local function nametableAddress(globalX, globalY)
    local x = globalX % 64
    local y = globalY % 60
    local tableX = x // 32
    local tableY = y // 30
    return 0x2000
        + (tableY * 2 + tableX) * 0x400
        + (y % 30) * 32
        + (x % 32)
end

local function mapperRegisterKey(address)
    if address == 0x5101 then
        return 0x5101
    end
    return address & 0x7300
end

local function pageSpan(layout, page, payloadLength)
    local first
    local capacity
    if page == 1 then
        first = 0
        capacity = layout.first_page_bytes
    else
        first = layout.first_page_bytes
            + (page - 2) * layout.subsequent_page_bytes
        capacity = layout.subsequent_page_bytes
    end
    if first >= payloadLength then
        return nil
    end
    return first, math.min(payloadLength - 1, first + capacity - 1)
end

local function pageCount(layout, payloadLength)
    if payloadLength <= 0 then
        return 0
    end
    if payloadLength <= layout.first_page_bytes then
        return 1
    end
    return 1
        + (
            payloadLength - layout.first_page_bytes
            + layout.subsequent_page_bytes - 1
        ) // layout.subsequent_page_bytes
end

local function pageFirstLineWidth(layout, page)
    if page == 1 then
        return layout.first_line_width
    end
    return 19
end

local function pageSourceReadComplete(target, layout, page)
    local first, last = pageSpan(layout, page, #target.payload)
    if first == nil then
        return false
    end
    for index = first, last do
        if not target.read_bytes[index] then
            return false
        end
    end
    return true
end

local function scalarStateDump()
    local state = emu.getState()
    local keys = {}
    for key, value in pairs(state) do
        local valueType = type(value)
        if valueType == "number"
            or valueType == "string"
            or valueType == "boolean"
        then
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

function DialogueCapture.new(options)
    options = options or {}
    requireNonEmptyString(
        options.output_directory,
        "output_directory"
    )
    requireNonEmptyString(options.rom_path, "rom_path")
    if type(options.targets) ~= "table" or #options.targets == 0 then
        error("targets must be a non-empty array", 2)
    end
    if type(options.frame) ~= "function" then
        error("frame callback is required", 2)
    end

    local self = setmetatable({
        _output_directory = options.output_directory,
        _rom_path = options.rom_path,
        _frame = options.frame,
        _targets = {},
        _active = nil,
        _captures = {},
        _errors = {},
        _low_bank = 0,
        _high_bank = 0,
        _mapper_bank_known = false,
        _advance_not_before = nil,
        _a_passthrough_until = -1,
        _last_advance_frame = nil,
        _stable_signature = nil,
        _stable_frames = 0,
        _blocked_a_frames = 0,
        _written = false,
    }, DialogueCapture)

    self:_loadTargets(options.targets)
    self:_installCallbacks()
    return self
end

function DialogueCapture:_currentBank()
    return self._low_bank | (self._high_bank << 4)
end

function DialogueCapture:_recordError(message)
    self._errors[#self._errors + 1] = tostring(message)
end

function DialogueCapture:_loadTargets(specifications)
    local rom = readFile(self._rom_path)
    if string.sub(rom, 1, 4) ~= "NES\026" then
        error("not an iNES ROM: " .. self._rom_path, 2)
    end
    if string.byte(rom, 5) * 0x4000 ~= 0x200000
        or string.byte(rom, 6) ~= 0
    then
        error("unexpected mapper-163 PRG/CHR layout", 2)
    end
    local mapper =
        ((string.byte(rom, 7) >> 4) | (string.byte(rom, 8) & 0xF0))
    if mapper ~= 163 then
        error("unexpected iNES mapper: " .. tostring(mapper), 2)
    end

    for _, specification in ipairs(specifications) do
        local record = fromHex(specification.payload_hex)
        if string.byte(record, #record) ~= 0x0D then
            error(
                string.format(
                    "$%06X payload is missing its $0D terminator",
                    specification.source_offset or 0
                ),
                2
            )
        end
        local occurrenceCount = 0
        local foundAt = nil
        local searchAt = 1
        while true do
            local occurrence = string.find(
                rom,
                record,
                searchAt,
                true
            )
            if occurrence == nil then
                break
            end
            occurrenceCount = occurrenceCount + 1
            foundAt = occurrence
            searchAt = occurrence + 1
        end
        if occurrenceCount ~= 1 then
            error(
                string.format(
                    "$%06X record occurrence count=%d, expected 1",
                    specification.source_offset or 0,
                    occurrenceCount
                ),
                2
            )
        end

        local fileOffset = foundAt - 1
        local pair = (fileOffset - 16) // 0x8000
        local pairStart = 16 + pair * 0x8000
        local cpuFirst = 0x8000 + fileOffset - pairStart
        local cpuLast = cpuFirst + #record - 1
        if cpuFirst < 0x8000 or cpuLast > 0xFFFF then
            error(
                string.format(
                    "$%06X record crosses a mapper window",
                    specification.source_offset or 0
                ),
                2
            )
        end

        self._targets[#self._targets + 1] = {
            source_offset = assert(specification.source_offset),
            label = assert(specification.label),
            required = specification.required == true,
            milestone = specification.milestone or "",
            record = record,
            payload = string.sub(record, 1, #record - 1),
            file_offset = fileOffset,
            prg_offset = fileOffset - 16,
            pair = pair,
            cpu_first = cpuFirst,
            cpu_last = cpuLast,
            read_events = 0,
            read_bytes = {},
            read_pcs = {},
            read_mismatches = 0,
            first_read_frame = nil,
            last_read_frame = nil,
            ppu_2006_write_events = 0,
            ppu_2007_write_events = 0,
            ppu_2006_pc_samples = 0,
            ppu_2007_pc_samples = 0,
            ppu_2006_write_pcs = {},
            ppu_2007_write_pcs = {},
            detected_layout = nil,
            detected_tile_base = nil,
            detected_origin_x = nil,
            detected_origin_y = nil,
            expected_pages = nil,
            pages_captured = 0,
            last_captured_signature = nil,
            completed = false,
            activation_count = 0,
            layout_ambiguity_reported = false,
            layout_scan_attempts = 0,
            next_layout_scan_frame = 0,
            layout_pending_dumped = false,
        }
    end
end

function DialogueCapture:_addressMatchesTarget(target, address)
    if self._mapper_bank_known and self:_currentBank() == target.pair then
        return true
    end
    local converted = emu.convertAddress(
        address,
        emu.memType.nesMemory
    )
    return converted ~= nil
        and converted.memType == emu.memType.nesPrgRom
        and converted.address >= target.prg_offset
        and converted.address <= target.prg_offset + #target.record - 1
end

function DialogueCapture:_activate(target)
    if target.completed then
        return
    end
    if self._active ~= nil and self._active ~= target then
        self:_recordError(string.format(
            "target overlap: $%06X started before $%06X completed",
            target.source_offset,
            self._active.source_offset
        ))
    end
    if self._active ~= target then
        self._active = target
        target.activation_count = target.activation_count + 1
        self._advance_not_before = nil
        self._a_passthrough_until = -1
        self._last_advance_frame = nil
        self._stable_signature = nil
        self._stable_frames = 0
        print(string.format(
            "POKEMON_DIALOGUE_RECORD_START frame=%d source=$%06X " ..
            "file=$%06X pair=%d cpu=$%04X-$%04X label=%s",
            self._frame(),
            target.source_offset,
            target.file_offset,
            target.pair,
            target.cpu_first,
            target.cpu_last,
            target.label
        ))
    end
end

function DialogueCapture:_observeRead(target, address, value)
    if not self:_addressMatchesTarget(target, address) then
        return
    end
    local index = address - target.cpu_first
    if index < 0 or index >= #target.record then
        return
    end
    local expected = string.byte(target.record, index + 1)
    target.read_events = target.read_events + 1
    target.read_bytes[index] = true
    local pc = currentPc()
    target.read_pcs[pc] = (target.read_pcs[pc] or 0) + 1
    if value ~= expected then
        target.read_mismatches = target.read_mismatches + 1
    end
    if target.first_read_frame == nil then
        target.first_read_frame = self._frame()
    end
    target.last_read_frame = self._frame()
    self:_activate(target)
end

function DialogueCapture:_installCallbacks()
    emu.addMemoryCallback(function(address, value)
        local key = mapperRegisterKey(address)
        if key == 0x5000 then
            self._low_bank = value & 0x0F
            self._mapper_bank_known = true
        elseif key == 0x5200 then
            self._high_bank = value & 0x0F
            self._mapper_bank_known = true
        end
    end, emu.callbackType.write, 0x5000, 0x5FFF)

    for _, target in ipairs(self._targets) do
        local observedTarget = target
        emu.addMemoryCallback(function(address, value)
            self:_observeRead(observedTarget, address, value)
        end, emu.callbackType.read, target.cpu_first, target.cpu_last)
    end

    -- Record the exact code paths that program $2006 and stream $2007 while
    -- each observed record is active.  These are passive bus callbacks.
    emu.addMemoryCallback(function(address)
        local target = self._active
        if target == nil or target.completed then
            return
        end
        local register = address & 0x07
        if register ~= 0x06 and register ~= 0x07 then
            return
        end
        if register == 0x06 then
            target.ppu_2006_write_events =
                target.ppu_2006_write_events + 1
            local sample = target.ppu_2006_pc_samples < 64
                or target.ppu_2006_write_events % 128 == 0
            if not sample then
                return
            end
            target.ppu_2006_pc_samples =
                target.ppu_2006_pc_samples + 1
            local pc = currentPc()
            target.ppu_2006_write_pcs[pc] =
                (target.ppu_2006_write_pcs[pc] or 0) + 1
        else
            target.ppu_2007_write_events =
                target.ppu_2007_write_events + 1
            local sample = target.ppu_2007_pc_samples < 64
                or target.ppu_2007_write_events % 128 == 0
            if not sample then
                return
            end
            target.ppu_2007_pc_samples =
                target.ppu_2007_pc_samples + 1
            local pc = currentPc()
            target.ppu_2007_write_pcs[pc] =
                (target.ppu_2007_write_pcs[pc] or 0) + 1
        end
    end, emu.callbackType.write, 0x2000, 0x3FFF)
end

function DialogueCapture:_positionReferenceMatches(
    pageIndex,
    line,
    lineIndex,
    firstLineWidth,
    tileBase,
    originX,
    originY
)
    local x
    if line == 1 then
        x = originX + (19 - firstLineWidth) + lineIndex
    else
        x = originX + lineIndex
    end
    local y = originY + (line - 1) * 2
    local topTileId = (tileBase + pageIndex * 2) & 0xFF
    local topAddress = nametableAddress(x, y)
    local bottomAddress = nametableAddress(x, y + 1)
    return emu.read(
        topAddress,
        emu.memType.nesPpuDebug
    ) == topTileId
        and emu.read(
            bottomAddress,
            emu.memType.nesPpuDebug
        ) == ((topTileId + 1) & 0xFF)
end

function DialogueCapture:_referenceCoverage(
    target,
    layout,
    page,
    tileBase,
    originX,
    originY
)
    local first, last = pageSpan(layout, page, #target.payload)
    if first == nil then
        return 0, 0
    end
    local firstLineWidth = pageFirstLineWidth(layout, page)
    local matches = 0
    local total = last - first + 1
    for recordIndex = first, last do
        local pageIndex = recordIndex - first
        local line
        local lineIndex
        if pageIndex < firstLineWidth then
            line = 1
            lineIndex = pageIndex
        else
            line = 2
            lineIndex = pageIndex - firstLineWidth
        end
        if self:_positionReferenceMatches(
            pageIndex,
            line,
            lineIndex,
            firstLineWidth,
            tileBase,
            originX,
            originY
        ) then
            matches = matches + 1
        end
    end
    return matches, total
end

function DialogueCapture:_bestOrigin(target, layout, tileBase, page)
    local bestMatches = -1
    local bestTotal = 0
    local bestX = nil
    local bestY = nil
    for originY = 0, 59 do
        for originX = 0, 63 do
            if self:_positionReferenceMatches(
                0,
                1,
                0,
                pageFirstLineWidth(layout, page),
                tileBase,
                originX,
                originY
            ) then
                local matches, total = self:_referenceCoverage(
                    target,
                    layout,
                    page,
                    tileBase,
                    originX,
                    originY
                )
                if matches > bestMatches then
                    bestMatches = matches
                    bestTotal = total
                    bestX = originX
                    bestY = originY
                end
            end
        end
    end
    if bestMatches < 0 then
        local first, last = pageSpan(layout, page, #target.payload)
        local total = first == nil and 0 or last - first + 1
        return 0, total, nil, nil
    end
    return bestMatches, bestTotal, bestX, bestY
end

function DialogueCapture:_detectLayout(target)
    if target.last_read_frame == nil
        or self._frame() - target.last_read_frame < 12
        or self._stable_frames < 12
        or self._frame() < target.next_layout_scan_frame
    then
        return false
    end
    target.next_layout_scan_frame = self._frame() + 30
    target.layout_scan_attempts = target.layout_scan_attempts + 1

    local exact = {}
    local observations = {}
    for _, layout in ipairs(LAYOUTS) do
        local tileBase = layout.tile_base
        local matches, total, originX, originY =
            self:_bestOrigin(target, layout, tileBase, 1)
        observations[#observations + 1] = string.format(
            "%s@%02X/nt%s,%s:%d/%d",
            layout.name,
            tileBase,
            originX and string.format("%02d", originX) or "--",
            originY and string.format("%02d", originY) or "--",
            matches,
            total
        )
        if total > 0 and matches == total then
            exact[#exact + 1] = {
                layout = layout,
                tile_base = tileBase,
                origin_x = originX,
                origin_y = originY,
            }
        end
    end
    if #exact == 1 then
        target.detected_layout = exact[1].layout
        target.detected_tile_base = exact[1].tile_base
        target.detected_origin_x = exact[1].origin_x
        target.detected_origin_y = exact[1].origin_y
        target.expected_pages = pageCount(
            exact[1].layout,
            #target.payload
        )
        print(string.format(
            "POKEMON_DIALOGUE_LAYOUT_DETECTED frame=%d source=$%06X " ..
            "layout=%s tile_base=$%02X origin=nt%02d,%02d " ..
            "pages=%d refs=%s",
            self._frame(),
            target.source_offset,
            exact[1].layout.name,
            exact[1].tile_base,
            exact[1].origin_x,
            exact[1].origin_y,
            target.expected_pages,
            table.concat(observations, ",")
        ))
        return true
    end
    if #exact > 1 and not target.layout_ambiguity_reported then
        target.layout_ambiguity_reported = true
        self:_recordError(string.format(
            "$%06X layout ambiguous: %s",
            target.source_offset,
            table.concat(observations, ",")
        ))
    end
    if #exact == 0
        and target.layout_scan_attempts >= 3
        and not target.layout_pending_dumped
    then
        target.layout_pending_dumped = true
        local prefix = string.format(
            "dialogue_%06X_layout_pending_frame_%05d",
            target.source_offset,
            self._frame()
        )
        local output = self._output_directory .. "\\"
        writeBinary(output .. prefix .. ".png", emu.takeScreenshot())
        writeBinary(
            output .. prefix .. "_chr_ram_8k.bin",
            memoryBytes(emu.memType.nesChrRam, 0x0000, 0x1FFF)
        )
        writeBinary(
            output .. prefix .. "_ppu_pattern_8k.bin",
            memoryBytes(emu.memType.nesPpuDebug, 0x0000, 0x1FFF)
        )
        writeBinary(
            output .. prefix .. "_nametable_4k.bin",
            memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
        )
        writeBinary(
            output .. prefix .. "_palette_32.bin",
            memoryBytes(emu.memType.nesPpuDebug, 0x3F00, 0x3F1F)
        )
        writeBinary(
            output .. prefix .. "_oam_256.bin",
            memoryBytes(emu.memType.nesSpriteRam, 0x00, 0xFF)
        )
        writeText(
            output .. prefix .. "_mesen_state.txt",
            scalarStateDump()
        )
        writeText(
            output .. prefix .. "_layout_observations.txt",
            table.concat(observations, ",") .. "\n"
        )
        print(string.format(
            "POKEMON_DIALOGUE_LAYOUT_PENDING frame=%d source=$%06X " ..
            "attempts=%d refs=%s file=%s",
            self._frame(),
            target.source_offset,
            target.layout_scan_attempts,
            table.concat(observations, ","),
            prefix .. ".png"
        ))
    end
    return false
end

function DialogueCapture:_capturePage(
    target,
    page,
    signature,
    arrowVisible,
    matches,
    total
)
    local layout = assert(target.detected_layout)
    local first, last = pageSpan(layout, page, #target.payload)
    local prefix = string.format(
        "dialogue_%06X_%s_tiles_%02X_nt_%02d_%02d_" ..
        "page_%02d_frame_%05d",
        target.source_offset,
        layout.name,
        target.detected_tile_base,
        target.detected_origin_x,
        target.detected_origin_y,
        page,
        self._frame()
    )
    local output = self._output_directory .. "\\"
    local screenshot = emu.takeScreenshot()

    writeBinary(output .. prefix .. ".png", screenshot)
    writeBinary(
        output .. prefix .. "_chr_ram_8k.bin",
        memoryBytes(emu.memType.nesChrRam, 0x0000, 0x1FFF)
    )
    writeBinary(
        output .. prefix .. "_ppu_pattern_8k.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x0000, 0x1FFF)
    )
    writeBinary(
        output .. prefix .. "_nametable_4k.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
    )
    writeBinary(
        output .. prefix .. "_palette_32.bin",
        memoryBytes(emu.memType.nesPpuDebug, 0x3F00, 0x3F1F)
    )
    writeBinary(
        output .. prefix .. "_oam_256.bin",
        memoryBytes(emu.memType.nesSpriteRam, 0x00, 0xFF)
    )
    writeText(
        output .. prefix .. "_mesen_state.txt",
        scalarStateDump()
    )
    writeText(
        output .. prefix .. "_expected_page_hex.txt",
        toHex(string.sub(target.payload, first + 1, last + 1)) ..
            "\n"
    )

    target.pages_captured = page
    target.last_captured_signature = signature
    self._last_advance_frame = nil
    self._captures[#self._captures + 1] = {
        frame = self._frame(),
        source_offset = target.source_offset,
        label = target.label,
        file_offset = target.file_offset,
        layout = layout.name,
        tile_base = target.detected_tile_base,
        origin_x = target.detected_origin_x,
        origin_y = target.detected_origin_y,
        page = page,
        expected_pages = target.expected_pages,
        payload_first = first,
        payload_last = last,
        expected_hex =
            toHex(string.sub(target.payload, first + 1, last + 1)),
        arrow_visible = arrowVisible,
        pixel_signature = signature,
        reference_matches = matches,
        reference_total = total,
        chr_checksum = checksum(
            emu.memType.nesChrRam,
            0x0000,
            0x1FFF
        ),
        nametable_checksum = checksum(
            emu.memType.nesPpuDebug,
            0x2000,
            0x2FFF
        ),
        filename = prefix .. ".png",
    }

    print(string.format(
        "POKEMON_DIALOGUE_PAGE_CAPTURE frame=%d source=$%06X " ..
        "layout=%s tile_base=$%02X origin=nt%02d,%02d page=%d/%d " ..
        "arrow=%s refs=%d/%d signature=%08X file=%s",
        self._frame(),
        target.source_offset,
        layout.name,
        target.detected_tile_base,
        target.detected_origin_x,
        target.detected_origin_y,
        page,
        target.expected_pages,
        tostring(arrowVisible),
        matches,
        total,
        signature,
        prefix .. ".png"
    ))

    if page < target.expected_pages then
        self._advance_not_before = self._frame() + 60
    else
        target.completed = true
        self._active = nil
        self._advance_not_before = nil
        self._a_passthrough_until = -1
        print(string.format(
            "POKEMON_DIALOGUE_RECORD_COMPLETE frame=%d source=$%06X " ..
            "layout=%s tile_base=$%02X origin=nt%02d,%02d pages=%d " ..
            "source_pcs=%s ppu2006_pcs=%s " ..
            "ppu2007_pcs=%s",
            self._frame(),
            target.source_offset,
            layout.name,
            target.detected_tile_base,
            target.detected_origin_x,
            target.detected_origin_y,
            target.pages_captured,
            pcCountsText(target.read_pcs),
            pcCountsText(target.ppu_2006_write_pcs),
            pcCountsText(target.ppu_2007_write_pcs)
        ))
    end
end

function DialogueCapture:applyInput(input, controller)
    local filtered = copyInput(input)
    local frame = self._frame()
    local target = self._active
    if filtered.a and target ~= nil and not target.completed then
        local allow = frame <= self._a_passthrough_until
        if not allow
            and self._advance_not_before ~= nil
            and frame >= self._advance_not_before
        then
            allow = true
            self._advance_not_before = nil
            self._a_passthrough_until = frame + 4
            self._last_advance_frame = frame
            self._stable_signature = nil
            self._stable_frames = 0
        end
        if not allow then
            filtered.a = false
            self._blocked_a_frames = self._blocked_a_frames + 1
        end
    end
    emu.setInput(filtered, controller)
end

function DialogueCapture:tick()
    local target = self._active
    if target == nil or target.completed then
        return
    end

    local arrowVisible = promptArrowVisible()
    local signature = dialoguePixelSignature()
    if signature == self._stable_signature then
        self._stable_frames = self._stable_frames + 1
    else
        self._stable_signature = signature
        self._stable_frames = 1
    end

    if target.detected_layout == nil then
        if not self:_detectLayout(target) then
            return
        end
    end

    local page = target.pages_captured + 1
    local matches, total = self:_referenceCoverage(
        target,
        target.detected_layout,
        page,
        target.detected_tile_base,
        target.detected_origin_x,
        target.detected_origin_y
    )
    if total == 0 or matches ~= total then
        return
    end
    if not pageSourceReadComplete(
        target,
        target.detected_layout,
        page
    ) then
        return
    end

    local mayBeNextPage = target.pages_captured == 0
        or (
            self._last_advance_frame ~= nil
            and self._frame() - self._last_advance_frame >= 20
        )
    if not mayBeNextPage then
        return
    end

    if page < target.expected_pages then
        local ordinarySliceComplete =
            target.detected_layout.name == "19_19"
            and target.last_read_frame ~= nil
            and self._frame() - target.last_read_frame >= 12
            and self._stable_frames >= 12
        if arrowVisible or ordinarySliceComplete then
            self:_capturePage(
                target,
                page,
                signature,
                arrowVisible,
                matches,
                total
            )
        end
        return
    end

    -- The final page has no wait-arrow in this engine.  Require the complete
    -- record terminator to have been read, exact tile references, and a
    -- stable rendered pixel signature before allowing the route to continue.
    if target.read_bytes[#target.record - 1]
        and not arrowVisible
        and self._stable_frames >= 12
    then
        self:_capturePage(
            target,
            page,
            signature,
            false,
            matches,
            total
        )
    end
end

function DialogueCapture:allRequiredCompleted()
    for _, target in ipairs(self._targets) do
        if target.required and not target.completed then
            return false
        end
    end
    return true
end

function DialogueCapture:milestoneCompleted(name)
    for _, target in ipairs(self._targets) do
        if target.milestone == name and target.completed then
            return true
        end
    end
    return false
end

function DialogueCapture:captureCount()
    return #self._captures
end

function DialogueCapture:requiredTargetCount()
    local count = 0
    for _, target in ipairs(self._targets) do
        if target.required then
            count = count + 1
        end
    end
    return count
end

function DialogueCapture:completedRequiredTargetCount()
    local count = 0
    for _, target in ipairs(self._targets) do
        if target.required and target.completed then
            count = count + 1
        end
    end
    return count
end

function DialogueCapture:layoutSummary(requiredOnly)
    local rows = {}
    for _, target in ipairs(self._targets) do
        if (not requiredOnly or target.required)
            and target.detected_layout ~= nil
        then
            rows[#rows + 1] = string.format(
                "%06X:%s",
                target.source_offset,
                target.detected_layout.name ..
                    "@" ..
                    string.format(
                        "%02X",
                        target.detected_tile_base
                    ) ..
                    string.format(
                        "/nt%02d,%02d",
                        target.detected_origin_x,
                        target.detected_origin_y
                    )
            )
        end
    end
    if #rows == 0 then
        return "none"
    end
    return table.concat(rows, ",")
end

function DialogueCapture:validationErrors()
    local errors = {}
    for _, message in ipairs(self._errors) do
        errors[#errors + 1] = message
    end
    for _, target in ipairs(self._targets) do
        if target.read_mismatches ~= 0 then
            errors[#errors + 1] = string.format(
                "$%06X read mismatches=%d",
                target.source_offset,
                target.read_mismatches
            )
        end
        if target.required and not target.completed then
            errors[#errors + 1] = string.format(
                "$%06X required target incomplete (%d pages)",
                target.source_offset,
                target.pages_captured
            )
        end
        if target.completed then
            local uniqueReads = 0
            for _ in pairs(target.read_bytes) do
                uniqueReads = uniqueReads + 1
            end
            if uniqueReads ~= #target.record then
                errors[#errors + 1] = string.format(
                    "$%06X record reads=%d/%d",
                    target.source_offset,
                    uniqueReads,
                    #target.record
                )
            end
            if target.detected_layout == nil then
                errors[#errors + 1] = string.format(
                    "$%06X has no detected runtime layout",
                    target.source_offset
                )
            end
            if target.detected_tile_base == nil then
                errors[#errors + 1] = string.format(
                    "$%06X has no detected runtime tile base",
                    target.source_offset
                )
            end
            if target.detected_origin_x == nil
                or target.detected_origin_y == nil
            then
                errors[#errors + 1] = string.format(
                    "$%06X has no detected runtime nametable origin",
                    target.source_offset
                )
            end
            if target.pages_captured ~= target.expected_pages then
                errors[#errors + 1] = string.format(
                    "$%06X pages=%d/%s",
                    target.source_offset,
                    target.pages_captured,
                    tostring(target.expected_pages)
                )
            end
        end
    end
    return errors
end

function DialogueCapture:_pageEvidenceText()
    local lines = {
        "frame\tsource_offset\tlabel\tfile_offset\tlayout\ttile_base\t" ..
            "origin_x\torigin_y\tpage\texpected_pages\tpayload_first\t" ..
            "payload_last\t" ..
            "expected_hex\tarrow_visible\tpixel_signature\t" ..
            "reference_matches\treference_total\tchr_checksum\t" ..
            "nametable_checksum\tpng",
    }
    for _, row in ipairs(self._captures) do
        lines[#lines + 1] = string.format(
            "%d\t%06X\t%s\t%06X\t%s\t%02X\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t" ..
            "%s\t%08X\t%d\t%d\t%08X\t%08X\t%s",
            row.frame,
            row.source_offset,
            row.label,
            row.file_offset,
            row.layout,
            row.tile_base,
            row.origin_x,
            row.origin_y,
            row.page,
            row.expected_pages,
            row.payload_first,
            row.payload_last,
            row.expected_hex,
            tostring(row.arrow_visible),
            row.pixel_signature,
            row.reference_matches,
            row.reference_total,
            row.chr_checksum,
            row.nametable_checksum,
            row.filename
        )
    end
    return table.concat(lines, "\n") .. "\n"
end

function DialogueCapture:_targetEvidenceText()
    local lines = {
        "source_offset\tlabel\trequired\tmilestone\tfile_offset\t" ..
            "pair\tcpu_first\tcpu_last\tpayload_bytes\tread_events\t" ..
            "unique_reads\tread_mismatches\tfirst_read_frame\t" ..
            "last_read_frame\tactivation_count\tdetected_layout\t" ..
            "detected_tile_base\tdetected_origin_x\tdetected_origin_y\t" ..
            "expected_pages\t" ..
            "pages_captured\t" ..
            "completed\tread_pc_counts\t" ..
            "ppu_2006_write_events\tppu_2006_pc_samples\t" ..
            "ppu_2006_pc_counts\tppu_2007_write_events\t" ..
            "ppu_2007_pc_samples\tppu_2007_pc_counts",
    }
    for _, target in ipairs(self._targets) do
        local uniqueReads = 0
        for _ in pairs(target.read_bytes) do
            uniqueReads = uniqueReads + 1
        end
        lines[#lines + 1] = string.format(
            "%06X\t%s\t%s\t%s\t%06X\t%d\t%04X\t%04X\t%d\t" ..
            "%d\t%d\t%d\t%s\t%s\t%d\t%s\t%s\t%s\t%s\t%s\t%d\t%s\t" ..
            "%s\t%d\t%d\t%s\t%d\t%d\t%s",
            target.source_offset,
            target.label,
            tostring(target.required),
            target.milestone,
            target.file_offset,
            target.pair,
            target.cpu_first,
            target.cpu_last,
            #target.payload,
            target.read_events,
            uniqueReads,
            target.read_mismatches,
            tostring(target.first_read_frame or ""),
            tostring(target.last_read_frame or ""),
            target.activation_count,
            target.detected_layout
                and target.detected_layout.name
                or "",
            target.detected_tile_base
                and string.format("%02X", target.detected_tile_base)
                or "",
            tostring(target.detected_origin_x or ""),
            tostring(target.detected_origin_y or ""),
            tostring(target.expected_pages or ""),
            target.pages_captured,
            tostring(target.completed),
            pcCountsText(target.read_pcs),
            target.ppu_2006_write_events,
            target.ppu_2006_pc_samples,
            pcCountsText(target.ppu_2006_write_pcs),
            target.ppu_2007_write_events,
            target.ppu_2007_pc_samples,
            pcCountsText(target.ppu_2007_write_pcs)
        )
    end
    return table.concat(lines, "\n") .. "\n"
end

function DialogueCapture:_runtimePcEvidenceText()
    local lines = {
        "source_offset\tlabel\tevent\tpc\tcount",
    }
    for _, target in ipairs(self._targets) do
        for _, specification in ipairs({
            {"source_read", target.read_pcs},
            {"ppu_2006_write", target.ppu_2006_write_pcs},
            {"ppu_2007_write", target.ppu_2007_write_pcs},
        }) do
            local pcs = {}
            for pc in pairs(specification[2]) do
                pcs[#pcs + 1] = pc
            end
            table.sort(pcs)
            for _, pc in ipairs(pcs) do
                lines[#lines + 1] = string.format(
                    "%06X\t%s\t%s\t%04X\t%d",
                    target.source_offset,
                    target.label,
                    specification[1],
                    pc,
                    specification[2][pc]
                )
            end
        end
    end
    return table.concat(lines, "\n") .. "\n"
end

function DialogueCapture:writeEvidence()
    if self._written then
        return
    end
    self._written = true
    local output = self._output_directory .. "\\"
    writeText(
        output .. "early_dialogue_pages.tsv",
        self:_pageEvidenceText()
    )
    writeText(
        output .. "early_dialogue_targets.tsv",
        self:_targetEvidenceText()
    )
    writeText(
        output .. "early_dialogue_runtime_pcs.tsv",
        self:_runtimePcEvidenceText()
    )
    writeText(
        output .. "early_dialogue_observer.txt",
        "mode=natural_passive_controller\n" ..
            "emu_memory_writes=0\n" ..
            "layout_candidates=17_19,19_19\n" ..
            "tile_base_candidates=40,D4\n" ..
            "runtime_render_contract=" ..
            "intro_two_lines,ordinary_one_19_column_slice\n" ..
            "origin_search=64x60_logical_nametable\n" ..
            "final_page_stable_frames=12\n" ..
            "advance_delay_frames=60\n" ..
            "blocked_a_frames=" ..
            tostring(self._blocked_a_frames) .. "\n" ..
            "captures=" .. tostring(#self._captures) .. "\n"
    )
end

return DialogueCapture
