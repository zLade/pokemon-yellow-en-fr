-- Passive runtime probe for the Nanjing mapper used by NJ046 (iNES 163).
--
-- Mesen 2.2.1 models mapper 163 registers in $5000-$5FFF.  Unlike the
-- Mapper 30 matrix used by Poker Dungeon, this probe never writes mapper
-- registers itself: it observes the game's bootstrap and bank switching so
-- that the test cannot perturb copy-protection or CHR scanline behaviour.

local frames = 0
local writes = {}
local reads = {}
local firstWrites = {}
local banks = {}
local lowBank = 0
local highBank = 0

local function registerKey(address)
    if address == 0x5101 then
        return 0x5101
    end
    return address & 0x7300
end

local function increment(tableValue, key)
    tableValue[key] = (tableValue[key] or 0) + 1
end

emu.addMemoryCallback(function(address, value)
    local key = registerKey(address)
    increment(writes, key)
    if #firstWrites < 24 then
        table.insert(firstWrites, string.format("$%04X=$%02X", address, value))
    end

    if key == 0x5000 then
        lowBank = value & 0x0F
    elseif key == 0x5200 then
        highBank = value & 0x0F
    end
    banks[lowBank | (highBank << 4)] = true
end, emu.callbackType.write, 0x5000, 0x5FFF)

emu.addMemoryCallback(function(address)
    increment(reads, registerKey(address))
end, emu.callbackType.read, 0x5000, 0x5FFF)

emu.addEventCallback(function()
    frames = frames + 1
    if frames ~= 1200 then
        return
    end

    local writeCount = 0
    for _, count in pairs(writes) do
        writeCount = writeCount + count
    end
    local readCount = 0
    for _, count in pairs(reads) do
        readCount = readCount + count
    end
    local distinctBanks = 0
    for _ in pairs(banks) do
        distinctBanks = distinctBanks + 1
    end

    local failures = {}
    -- Lua starts after Mesen's initial RESET trampoline, so $5300/$5200
    -- bootstrap writes are verified statically by validate_mapper163.py.
    -- Runtime must still exercise the mapper continuously and visit several
    -- 32 KiB mappings without the probe touching the registers itself.
    if (writes[0x5100] or 0) < 1 then
        table.insert(failures, "missing runtime write to $5100")
    end
    if (writes[0x5000] or 0) < 100 then
        table.insert(
            failures,
            "too few runtime writes to $5000: " ..
            tostring(writes[0x5000] or 0)
        )
    end
    if distinctBanks < 4 then
        table.insert(
            failures,
            "too few observed 32 KiB bank values: " .. tostring(distinctBanks)
        )
    end

    local state = emu.getState()
    local summary = string.format(
        "region=%s frames=%d writes=%d reads=%d banks=%d r5000=%d r5100=%d r5101=%d r5200=%d r5300=%d r5500=%d",
        tostring(state["region"]), frames, writeCount, readCount, distinctBanks,
        writes[0x5000] or 0, writes[0x5100] or 0, writes[0x5101] or 0,
        writes[0x5200] or 0, writes[0x5300] or 0, reads[0x5500] or 0
    )
    print("MAPPER163_TRACE first=" .. table.concat(firstWrites, ","))
    if #failures == 0 then
        print("MAPPER163_PASS " .. summary)
        emu.stop(0)
    else
        print(
            "MAPPER163_FAIL " .. summary .. " " ..
            table.concat(failures, "; ")
        )
        emu.stop(1)
    end
end, emu.eventType.endFrame)
