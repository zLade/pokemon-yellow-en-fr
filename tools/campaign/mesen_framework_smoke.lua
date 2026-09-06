-- Executable self-test for the campaign framework.
--
-- Run this file with tools/run-mesen-pokemon-scenario.ps1 and expect
-- POKEMON_CAMPAIGN_FRAMEWORK_PASS.  It performs no game-memory writes.

local function scriptDirectory()
    local source = debug.getinfo(1, "S").source or ""
    if source:sub(1, 1) == "@" then
        source = source:sub(2)
    end
    local directory = source:match("^(.*)[/\\\\][^/\\\\]+$")
    if directory == nil or directory == "" then
        error("cannot determine campaign script directory")
    end
    return directory
end

local directory = scriptDirectory()
local separator = directory:find("\\", 1, true) and "\\" or "/"
local function loadModule(filename)
    return dofile(directory .. separator .. filename)
end

local Engine = loadModule("engine.lua")
local InputQueue = loadModule("input_queue.lua")
local MemoryGuard = loadModule("memory_guard.lua")
local RamMap = loadModule("ram_map.lua")
local SpeciesPlan = loadModule("species_plan.lua")

local function assertEqual(actual, expected, label)
    if actual ~= expected then
        error(string.format(
            "%s: expected %s, got %s",
            label,
            tostring(expected),
            tostring(actual)
        ))
    end
end

local function runEngineTest()
    local frame = 0
    local context = {recovered = false, entries = 0}
    local engine = Engine.new({now = function()
        return frame
    end})
    engine:add_state("probe", {
        entry = function(ctx)
            ctx.entries = ctx.entries + 1
        end,
        success = function(ctx)
            return ctx.recovered, "probe-ok"
        end,
        timeout = 1,
        recovery = function(ctx, details)
            assertEqual(details.reason, "timeout", "recovery reason")
            ctx.recovered = true
            return "retry"
        end,
        max_recoveries = 1,
        next = "finish",
    })
    engine:add_state("finish", {
        entry = function() end,
        success = function()
            return true, "campaign-ok"
        end,
        timeout = 1,
        recovery = function()
            return "fail"
        end,
        max_recoveries = 0,
    })

    engine:start("probe", context)
    assertEqual(engine:tick(), "running", "engine first tick")
    frame = 1
    assertEqual(engine:tick(), "running", "engine recovery tick")
    frame = 2
    assertEqual(engine:tick(), "running", "engine transition tick")
    frame = 3
    assertEqual(engine:tick(), "completed", "engine completion")
    assertEqual(engine:get_result(), "campaign-ok", "engine result")
    assertEqual(context.entries, 2, "entry called after retry")
end

local function runInputQueueTest()
    local applied = {}
    local queue = InputQueue.new(function(state)
        applied[#applied + 1] = state
    end, 0)
    queue:pulse("a", 2, 1)
    queue:pulse("right", 1, 1)
    for _ = 1, 5 do
        queue:tick()
    end
    assertEqual(applied[1].a, true, "A frame 1")
    assertEqual(applied[2].a, true, "A frame 2")
    assertEqual(applied[3].a, false, "mandatory A release")
    assertEqual(applied[4].right, true, "Right frame")
    assertEqual(applied[5].right, false, "mandatory Right release")
    assertEqual(queue:is_idle(), true, "queue idle after release")

    queue:pulse("up", 3, 1)
    queue:tick()
    queue:abort()
    assertEqual(applied[#applied].up, false, "abort releases Up")
    assertEqual(queue:is_idle(), true, "queue idle after abort")
end

local function runMemoryGuardTest()
    local fakeMemory = {
        [RamMap.pokedex_unlock.address] = 0x01,
        [RamMap.player_oam_shadow.x.address] = 0x48,
        [RamMap.player_oam_shadow.y.address] = 0x70,
    }
    local memoryTypes = {
        nesMemory = "nesMemory",
        nesDebug = "nesDebug",
    }
    local function read(address)
        return fakeMemory[address] or 0
    end
    local function write(address, value)
        fakeMemory[address] = value
    end

    local controller = MemoryGuard.new({
        mode = "controller",
        read = read,
        deny_raises = false,
    })
    local allowed, denial = controller:write(
        RamMap.pokedex_unlock.address,
        0x21,
        memoryTypes.nesMemory,
        "self-test"
    )
    assertEqual(allowed, false, "controller write denied")
    assert(denial:find("read%-only") ~= nil)
    assertEqual(
        fakeMemory[RamMap.pokedex_unlock.address],
        0x01,
        "controller memory unchanged"
    )

    local assisted = MemoryGuard.new({
        mode = "assisted",
        read = read,
        write = write,
        deny_raises = false,
        whitelist = RamMap.assisted_write_whitelist(memoryTypes),
    })
    local unlockValue = RamMap.pokedex_unlock_value(
        fakeMemory[RamMap.pokedex_unlock.address]
    )
    assertEqual(assisted:write(
        RamMap.pokedex_unlock.address,
        unlockValue,
        memoryTypes.nesMemory,
        "self-test unlock"
    ), true, "assisted masked write")
    assertEqual(
        fakeMemory[RamMap.pokedex_unlock.address],
        0x21,
        "assisted memory changed"
    )
    assertEqual(assisted:write(
        0x6001,
        0xFF,
        memoryTypes.nesMemory,
        "self-test out of range"
    ), false, "unlisted address denied")

    local coordinates = RamMap.read_player_coordinates(
        read,
        memoryTypes
    )
    assertEqual(coordinates.x, 0x48, "player X")
    assertEqual(coordinates.y, 0x70, "player Y")
    local firstSeen = RamMap.pokedex_bit_location("seen", 1)
    assertEqual(firstSeen.address, 0x60B3, "seen #001 address")
    assertEqual(firstSeen.mask, 0x01, "seen #001 mask")
    local lastCaught = RamMap.pokedex_bit_location("caught", 151)
    assertEqual(lastCaught.address, 0x60B1, "caught #151 address")
    assertEqual(lastCaught.mask, 0x40, "caught #151 mask")
    assertEqual(#assisted:get_journal(), 2, "assisted journal rows")
end

local function runSpeciesPlanTest()
    local canonical = SpeciesPlan.new(151)
    local extended = SpeciesPlan.new({goal = 159})
    assertEqual(#canonical:targets(), 151, "canonical targets")
    assertEqual(#extended:targets(), 159, "extended targets")
    assertEqual(extended.kind, "rom_table_159", "extended plan kind")

    local owned = {}
    for speciesId = 1, 150 do
        owned[speciesId] = true
    end
    local progress = canonical:progress(owned)
    assertEqual(progress.owned, 150, "owned count")
    assertEqual(progress.remaining, 1, "remaining count")
    assertEqual(canonical:next_missing(owned), 151, "next missing")
    owned[151] = true
    assertEqual(canonical:progress(owned).complete, true, "151 complete")
    assertEqual(#extended:checkpoint_batches(25), 7, "159 batches")
end

local alreadyRun = false
emu.addEventCallback(function()
    if alreadyRun then
        return
    end
    alreadyRun = true
    runEngineTest()
    runInputQueueTest()
    runMemoryGuardTest()
    runSpeciesPlanTest()
    print(string.format(
        "POKEMON_CAMPAIGN_FRAMEWORK_PASS tests=4 writes_to_game=0 region=%s",
        tostring(emu.getState()["region"])
    ))
    emu.stop(0)
end, emu.eventType.endFrame)
