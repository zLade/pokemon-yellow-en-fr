-- Trace the internal-RAM bytes used while the in-game Pokedex is opened.
--
-- The script reaches the bedroom using controller input only, exports the
-- complete 2 KiB CPU RAM before/after opening the player menu and Pokedex,
-- and records every read/write address during Pokedex construction.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local traceActive = false
local ramReads = {}
local ramWrites = {}
local sramReads = {}
local sramWrites = {}
local sramAccessLog = {}
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

local function writeBinary(filename, data)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    file:write(data)
    file:close()
end

local function memoryBytes(first, last)
    local chunks = {}
    for address = first, last do
        chunks[#chunks + 1] = string.char(
            emu.read(address, emu.memType.nesDebug)
        )
    end
    return table.concat(chunks)
end

local function saveSnapshot(label)
    writeBinary(label .. "_cpu_ram_2k.bin", memoryBytes(0x0000, 0x07FF))
    local sram = {}
    for address = 0x6000, 0x7FFF do
        sram[#sram + 1] = string.char(
            emu.read(address, emu.memType.nesMemory)
        )
    end
    writeBinary(label .. "_sram_8k.bin", table.concat(sram))
    writeBinary(label .. "_screen.png", emu.takeScreenshot())
end

local function addressRanges(addresses)
    local sorted = {}
    for address in pairs(addresses) do
        sorted[#sorted + 1] = address
    end
    table.sort(sorted)
    local lines = {}
    local first = nil
    local last = nil
    for _, address in ipairs(sorted) do
        if first == nil then
            first = address
            last = address
        elseif address == last + 1 then
            last = address
        else
            lines[#lines + 1] = string.format("%04X-%04X", first, last)
            first = address
            last = address
        end
    end
    if first ~= nil then
        lines[#lines + 1] = string.format("%04X-%04X", first, last)
    end
    return table.concat(lines, "\n")
end

local function recordSramAccess(kind, address, value)
    -- $6800-$7FFF is also used as executable/scratch RAM.  Persistent game
    -- state lives in the primary $6000-$67FF block, so keep the trace focused
    -- and avoid exhausting the log on the dynamically loaded UI code.
    if address > 0x67FF then
        return
    end
    local tableValue = kind == "R" and sramReads or sramWrites
    tableValue[address] = (tableValue[address] or 0) + 1
    if #sramAccessLog >= 2048 then
        return
    end
    local state = emu.getState()
    local pc = state["cpu.pc"] or 0
    local converted = emu.convertAddress(pc, emu.memType.nesMemory)
    local prgOffset = -1
    if converted ~= nil and converted.memType == emu.memType.nesPrgRom then
        prgOffset = converted.address
    end
    sramAccessLog[#sramAccessLog + 1] = string.format(
        "%s frame=%04d addr=%04X value=%02X pc=%04X prg=%06X",
        kind,
        frames,
        address,
        value or 0,
        pc,
        prgOffset
    )
end

emu.addMemoryCallback(function(address)
    if traceActive and address <= 0x07FF then
        ramReads[address] = true
    end
end, emu.callbackType.read, 0x0000, 0x07FF)

emu.addMemoryCallback(function(address)
    if traceActive and address <= 0x07FF then
        ramWrites[address] = true
    end
end, emu.callbackType.write, 0x0000, 0x07FF)

emu.addMemoryCallback(function(address, value)
    if traceActive then
        recordSramAccess("R", address, value)
    end
end, emu.callbackType.read, 0x6000, 0x7FFF)

emu.addMemoryCallback(function(address, value)
    if traceActive then
        recordSramAccess("W", address, value)
    end
end, emu.callbackType.write, 0x6000, 0x7FFF)

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1
    pulseAt(180, "start", 4)
    for pulseFrame = 360, 4500, 30 do
        pulseAt(pulseFrame, "a", 3)
    end

    if frames == 4850 then
        saveSnapshot("01_bedroom")
    end
    pulseAt(4900, "start", 4)
    if frames == 5200 then
        saveSnapshot("02_player_menu")
    end
    -- The fresh-game menu gates Pokedex entry on $6000.  Enable it after
    -- preserving the unmodified menu snapshot so subsequent accesses expose
    -- the seen/owned data layout without changing the ROM or battery file.
    if frames == 5230 then
        emu.write(0x6000, 0x20, emu.memType.nesMemory)
        emu.write(0x6031, 151, emu.memType.nesMemory)
        emu.write(0x6032, 151, emu.memType.nesMemory)
        for index = 0, 17 do
            emu.write(0x609F + index, 0xFF, emu.memType.nesMemory)
            emu.write(0x60B3 + index, 0xFF, emu.memType.nesMemory)
        end
        -- Species IDs are one-based and LSB-first.  The final standard
        -- species is #151 at bit 6.  Keep #152's padding bit and the adjacent
        -- extension byte clear: the UI stops before #152 even though the ROM
        -- contains additional name records.
        emu.write(0x609F + 18, 0x7F, emu.memType.nesMemory)
        emu.write(0x60B3 + 18, 0x7F, emu.memType.nesMemory)
        emu.write(0x609F + 19, 0x00, emu.memType.nesMemory)
        emu.write(0x60B3 + 19, 0x00, emu.memType.nesMemory)
        emu.write(0x60C8, 151, emu.memType.nesMemory)
    end
    if frames == 5240 then
        traceActive = true
    end
    pulseAt(5250, "a", 4)
    if frames == 5550 then
        traceActive = false
        saveSnapshot("03_pokedex")
        writeBinary("pokedex_ram_reads.txt", addressRanges(ramReads))
        writeBinary("pokedex_ram_writes.txt", addressRanges(ramWrites))
        writeBinary("pokedex_sram_reads.txt", addressRanges(sramReads))
        writeBinary("pokedex_sram_writes.txt", addressRanges(sramWrites))
        writeBinary(
            "pokedex_sram_access_log.txt",
            table.concat(sramAccessLog, "\n")
        )
        local failures = {}
        if emu.read(0x6000, emu.memType.nesMemory) & 0x20 == 0 then
            failures[#failures + 1] = "Pokedex unlock bit missing"
        end
        if emu.read(0x6031, emu.memType.nesMemory) ~= 151 or
           emu.read(0x6032, emu.memType.nesMemory) ~= 151 then
            failures[#failures + 1] = "Pokedex counters are not 151/151"
        end
        for index = 0, 17 do
            if emu.read(0x609F + index, emu.memType.nesMemory) ~= 0xFF or
               emu.read(0x60B3 + index, emu.memType.nesMemory) ~= 0xFF then
                failures[#failures + 1] = "incomplete full-byte bitmap"
                break
            end
        end
        if emu.read(0x609F + 18, emu.memType.nesMemory) ~= 0x7F or
           emu.read(0x60B3 + 18, emu.memType.nesMemory) ~= 0x7F or
           emu.read(0x609F + 19, emu.memType.nesMemory) ~= 0x00 or
           emu.read(0x60B3 + 19, emu.memType.nesMemory) ~= 0x00 then
            failures[#failures + 1] = "invalid #151/padding mask"
        end
        if #failures == 0 then
            print(string.format(
                "POKEMON_POKEDEX_RAM_PASS mapper=163 region=%s frames=%d " ..
                "unlock=$6000:20 seen=$60B3 count=$6031:151 " ..
                "caught=$609F count=$6032:151",
                tostring(emu.getState()["region"]),
                frames
            ))
            emu.stop(0)
        else
            print("POKEMON_POKEDEX_RAM_FAIL " .. table.concat(failures, "; "))
            emu.stop(1)
        end
    end
end, emu.eventType.endFrame)
