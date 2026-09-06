-- State-driven, controller-only campaign prototype.
--
-- Proven route: cold boot -> new game -> bedroom -> Pallet Town ->
-- Professor Oak -> laboratory -> Pikachu -> first rival victory ->
-- stable laboratory exit.
-- Unlike an FM3 macro, this waits for screen signatures and reads the player
-- coordinates before pressing the next direction.  It performs no game-memory
-- writes, savestate loads, rewind or cheats.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

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

local BEDROOM_NAMETABLES = {
    [0xE8ABD336] = true, -- historical French graphics
    [0x5CAD3FE8] = true, -- enlarged SACHA player-menu graphics
}
local DOWNSTAIRS_NAMETABLES = {
    [0xE9D58C68] = true, -- historical French graphics
    [0x5DD6F91A] = true, -- enlarged SACHA player-menu graphics
}
local OUTSIDE_NAMETABLES = {
    [0xDD441740] = true, -- historical French graphics
    [0x514583F2] = true, -- enlarged SACHA player-menu graphics
}
local CHECKSUM_SAMPLE_PERIOD = 5
local OUTSIDE_STABLE_FRAMES = 120
local TOWN_EAST_STEP_PULSES = 12
local FORCED_SEQUENCE_STABLE_FRAMES = 180
local LAB_CONTROL_STABLE_FRAMES = 240
local STARTER_BALL_X = 0xB0
local STARTER_BALL_Y = 0x60
local LAB_NAMETABLES = {
    [0x7FFE1D9C] = true, -- historical French graphics
    [0xE29DC822] = true, -- enlarged SACHA player-menu graphics
}
local RIVAL_RESOLUTION_MIN_FRAMES = 1800
-- Leave enough idle frames for the complete command/move labels to render.
-- The game accepts A before its typewriter has finished, which made older
-- evidence captures show misleading fragments such as "AT" or "utili".
local RIVAL_BATTLE_ADVANCE_GAP_FRAMES = 180
local RIVAL_BATTLE_TRACE_PERIOD = 60
local RIVAL_WIN_EXP_NAMETABLE = 0x00A7ECFE
local RIVAL_WIN_REWARD_NAMETABLE = 0x11D12886
local PARTY_COUNT_ADDRESS = 0x6030
local PARTY_LEAD_SPECIES_ADDRESS = 0x6033
local PARTY_LEAD_LEVEL_ADDRESS = 0x6039
local PIKACHU_SPECIES_ID = 0x19
local frame = 0
local cachedNametable = 0

local function writeBinary(filename, data)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    file:write(data)
    file:close()
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

local function nametableBytes()
    local chunks = {}
    local chunk = {}
    for address = 0x2000, 0x2FFF do
        chunk[#chunk + 1] = string.char(
            emu.read(address, emu.memType.nesPpuDebug)
        )
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

local inputQueue = InputQueue.new(function(input, controller)
    emu.setInput(input, controller)
end, 0)

local memory = MemoryGuard.new({
    mode = "controller",
    read = function(address, memoryType)
        return emu.read(address, memoryType)
    end,
    frame = function()
        return frame
    end,
})

local context = {
    input = inputQueue,
    memory = memory,
    retries = 0,
    outside_candidate = nil,
    outside_candidate_since = nil,
    motion_signature = nil,
    motion_signature_since = nil,
    scene_signature = nil,
    scene_signature_since = nil,
    battle_return_signature = nil,
    battle_return_signature_since = nil,
    lab_exit_candidate = nil,
    lab_exit_candidate_since = nil,
    rival_trigger_position = nil,
    rival_battle_active_seen = false,
    rival_battle_win_seen = false,
    rival_battle_return_seen = false,
    town_east_step_pulses = 0,
    endpoint = "unknown",
}

local function coordinates()
    return RamMap.read_player_coordinates(
        function(address, memoryType)
            return memory:read(address, memoryType)
        end,
        {nesDebug = emu.memType.nesDebug}
    )
end

local function leadPartySummary()
    return {
        count = memory:read(
            PARTY_COUNT_ADDRESS,
            emu.memType.nesMemory
        ),
        species = memory:read(
            PARTY_LEAD_SPECIES_ADDRESS,
            emu.memType.nesMemory
        ),
        level = memory:read(
            PARTY_LEAD_LEVEL_ADDRESS,
            emu.memType.nesMemory
        ),
    }
end

local function abortAndRetry(ctx)
    ctx.input:abort()
    ctx.retries = ctx.retries + 1
    return "retry"
end

local routeEvidence = {}
local capturedCheckpoints = {}

local function captureCheckpoint(name)
    if capturedCheckpoints[name] then
        return
    end
    capturedCheckpoints[name] = true
    local position = coordinates()
    local party = leadPartySummary()
    routeEvidence[#routeEvidence + 1] = {
        frame = frame,
        checkpoint = name,
        nametable = cachedNametable,
        x = position.x,
        y = position.y,
        party_count = party.count,
        lead_species = party.species,
        lead_level = party.level,
    }
    writeBinary(name .. "_screen.png", emu.takeScreenshot())
end

local function positionInRange(position, axis, minimum, maximum)
    local value = position[axis]
    return value >= minimum and value <= maximum
end

local function pulseToward(
    ctx,
    position,
    axis,
    target,
    negativeButton,
    positiveButton,
    label
)
    if not ctx.input:is_idle() then
        return
    end
    local button = position[axis] < target
        and positiveButton
        or negativeButton
    ctx.input:pulse(button, 4, 1, label)
end

local engine = Engine.new({
    now = function()
        return frame
    end,
})

engine:add_state("boot_delay", {
    entry = function() end,
    success = function(_, elapsed)
        return elapsed >= 180
    end,
    timeout = 300,
    recovery = function()
        return "fail"
    end,
    max_recoveries = 0,
    next = "title_start",
})

engine:add_state("title_start", {
    entry = function(ctx)
        ctx.input:pulse("start", 4, 20, "title_start")
    end,
    success = function(ctx)
        return ctx.input:is_idle()
    end,
    timeout = 180,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "advance_intro",
})

engine:add_state("advance_intro", {
    entry = function() end,
    success = function(ctx)
        if BEDROOM_NAMETABLES[cachedNametable] then
            ctx.input:abort()
            return true
        end
        if ctx.input:is_idle() then
            ctx.input:pulse("a", 3, 27, "advance_dialogue")
        end
        return false
    end,
    timeout = 6000,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "align_bedroom_door",
})

engine:add_state("align_bedroom_door", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        local position = coordinates()
        if position.x >= 0xBE and position.x <= 0xC2 then
            ctx.input:abort()
            return true, position
        end
        if ctx.input:is_idle() then
            local direction = position.x < 0xC0 and "right" or "left"
            ctx.input:pulse(direction, 4, 1, "align_door_x")
        end
        return false
    end,
    timeout = 1200,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "take_bedroom_stairs",
})

engine:add_state("take_bedroom_stairs", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        if DOWNSTAIRS_NAMETABLES[cachedNametable] then
            ctx.input:abort()
            return true, coordinates()
        end
        if BEDROOM_NAMETABLES[cachedNametable] and ctx.input:is_idle() then
            ctx.input:pulse("up", 4, 1, "walk_into_stairs")
        end
        return false
    end,
    timeout = 1200,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "prove_downstairs_spawn",
})

engine:add_state("prove_downstairs_spawn", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(_, elapsed)
        if elapsed >= 30 and DOWNSTAIRS_NAMETABLES[cachedNametable] then
            captureCheckpoint("00_downstairs_spawn")
            return true, coordinates()
        end
        return false
    end,
    timeout = 120,
    recovery = function(ctx)
        ctx.input:abort()
        return "fail"
    end,
    max_recoveries = 0,
    next = "move_left_of_stairs",
})

-- The table blocks a direct diagonal to the front door.  The following
-- states reproduce the route established by the controller-only discovery
-- captures, but stop on coordinates rather than fixed frame numbers.
engine:add_state("move_left_of_stairs", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        if not DOWNSTAIRS_NAMETABLES[cachedNametable] then
            return false
        end
        local position = coordinates()
        if positionInRange(position, "x", 0x9E, 0xA2) then
            ctx.input:abort()
            return true, position
        end
        pulseToward(
            ctx,
            position,
            "x",
            0xA0,
            "left",
            "right",
            "downstairs_stairs_to_table"
        )
        return false
    end,
    timeout = 600,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "descend_right_of_table",
})

engine:add_state("descend_right_of_table", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        if not DOWNSTAIRS_NAMETABLES[cachedNametable] then
            return false
        end
        local position = coordinates()
        if positionInRange(position, "y", 0x3E, 0x42) then
            ctx.input:abort()
            return true, position
        end
        pulseToward(
            ctx,
            position,
            "y",
            0x40,
            "up",
            "down",
            "downstairs_table_right_edge"
        )
        return false
    end,
    timeout = 600,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "round_table_left",
})

engine:add_state("round_table_left", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        if not DOWNSTAIRS_NAMETABLES[cachedNametable] then
            return false
        end
        local position = coordinates()
        if positionInRange(position, "x", 0x1E, 0x22) then
            ctx.input:abort()
            return true, position
        end
        pulseToward(
            ctx,
            position,
            "x",
            0x20,
            "left",
            "right",
            "downstairs_round_table"
        )
        return false
    end,
    timeout = 600,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "move_below_table",
})

engine:add_state("move_below_table", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        if not DOWNSTAIRS_NAMETABLES[cachedNametable] then
            return false
        end
        local position = coordinates()
        if positionInRange(position, "y", 0x9E, 0xA2) then
            ctx.input:abort()
            captureCheckpoint("01_below_table")
            return true, position
        end
        pulseToward(
            ctx,
            position,
            "y",
            0xA0,
            "up",
            "down",
            "downstairs_below_table"
        )
        return false
    end,
    timeout = 600,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "align_front_door",
})

engine:add_state("align_front_door", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        if not DOWNSTAIRS_NAMETABLES[cachedNametable] then
            return false
        end
        local position = coordinates()
        if positionInRange(position, "x", 0x4E, 0x52) then
            ctx.input:abort()
            captureCheckpoint("02_front_door_aligned")
            return true, position
        end
        pulseToward(
            ctx,
            position,
            "x",
            0x50,
            "left",
            "right",
            "downstairs_align_front_door"
        )
        return false
    end,
    timeout = 600,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "leave_house",
})

engine:add_state("leave_house", {
    entry = function(ctx)
        ctx.input:abort()
        ctx.outside_candidate = nil
        ctx.outside_candidate_since = nil
    end,
    success = function(ctx)
        if OUTSIDE_NAMETABLES[cachedNametable] then
            ctx.input:abort()
            ctx.outside_candidate = cachedNametable
            ctx.outside_candidate_since = frame
            return true, {
                nametable = cachedNametable,
                position = coordinates(),
            }
        end
        if DOWNSTAIRS_NAMETABLES[cachedNametable]
            and ctx.input:is_idle()
        then
            ctx.input:pulse("down", 4, 1, "walk_through_front_door")
        end
        return false
    end,
    timeout = 1200,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "prove_outside_stable",
})

engine:add_state("prove_outside_stable", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        if not OUTSIDE_NAMETABLES[cachedNametable] then
            ctx.outside_candidate = nil
            ctx.outside_candidate_since = nil
            return false
        end
        if cachedNametable ~= ctx.outside_candidate then
            ctx.outside_candidate = cachedNametable
            ctx.outside_candidate_since = frame
            return false
        end
        if frame - ctx.outside_candidate_since >= OUTSIDE_STABLE_FRAMES then
            captureCheckpoint("03_outside_stable")
            writeBinary(
                "campaign_prototype_outside_nametable_4k.bin",
                nametableBytes()
            )
            return true, {
                nametable = cachedNametable,
                position = coordinates(),
                stable_frames = frame - ctx.outside_candidate_since,
            }
        end
        return false
    end,
    timeout = 600,
    recovery = function(ctx)
        ctx.input:abort()
        return "fail"
    end,
    max_recoveries = 0,
    next = "align_town_north_path",
})

-- Pallet Town scrolls before the player's OAM X reaches the target path, so a
-- screen coordinate cannot identify the east approach.  The original
-- controller-only reference movie proves a clear twelve-step corridor.  Keep
-- the pulse count isolated so it is easy to recalibrate after a rebuilt ROM.
engine:add_state("align_town_north_path", {
    entry = function(ctx)
        ctx.input:abort()
        ctx.town_east_step_pulses = 0
    end,
    success = function(ctx)
        if ctx.town_east_step_pulses >= TOWN_EAST_STEP_PULSES
            and ctx.input:is_idle()
        then
            captureCheckpoint("04_town_north_path_aligned")
            return true, {
                position = coordinates(),
                east_step_pulses = ctx.town_east_step_pulses,
            }
        end
        if ctx.input:is_idle() then
            ctx.town_east_step_pulses =
                ctx.town_east_step_pulses + 1
            ctx.input:pulse("right", 4, 4, "town_align_north_path")
        end
        return false
    end,
    timeout = 600,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "walk_north_to_forced_sequence",
})

-- Discovery-backed stopping rule: while UP is being sent, either the player
-- coordinates or the scrolling nametable continues to change.  A long stable
-- interval therefore identifies the first forced sequence (Professor Oak on
-- the north edge of Pallet Town) without writing or guessing a game-state
-- address.
engine:add_state("walk_north_to_forced_sequence", {
    entry = function(ctx)
        ctx.input:abort()
        ctx.motion_signature = nil
        ctx.motion_signature_since = frame
    end,
    success = function(ctx, elapsed)
        local position = coordinates()
        local signature = string.format(
            "%08X:%02X:%02X",
            cachedNametable,
            position.x,
            position.y
        )
        if signature ~= ctx.motion_signature then
            ctx.motion_signature = signature
            ctx.motion_signature_since = frame
        end
        if elapsed >= 30
            and frame - ctx.motion_signature_since
                >= FORCED_SEQUENCE_STABLE_FRAMES
        then
            ctx.input:abort()
            captureCheckpoint("05_oak_sequence_candidate")
            return true, {
                nametable = cachedNametable,
                position = position,
                stable_frames = frame - ctx.motion_signature_since,
            }
        end
        if ctx.input:is_idle() then
            ctx.input:pulse("up", 4, 1, "town_oak_approach")
        end
        return false
    end,
    timeout = 2400,
    recovery = function(ctx)
        ctx.input:abort()
        captureCheckpoint("05_oak_sequence_timeout")
        return "fail"
    end,
    max_recoveries = 0,
    next = "advance_oak_to_lab",
})

-- Mash A only while the forced Oak/capture sequence owns control.  Once the
-- laboratory map is idle, further A presses are harmless at the entrance and
-- the unchanged signature gives us a controller-only proof that control has
-- returned.
engine:add_state("advance_oak_to_lab", {
    entry = function(ctx)
        ctx.input:abort()
        ctx.scene_signature = nil
        ctx.scene_signature_since = frame
    end,
    success = function(ctx, elapsed)
        local position = coordinates()
        local signature = string.format(
            "%08X:%02X:%02X",
            cachedNametable,
            position.x,
            position.y
        )
        if signature ~= ctx.scene_signature then
            ctx.scene_signature = signature
            ctx.scene_signature_since = frame
        end
        if elapsed >= 600
            and positionInRange(position, "x", 0x7E, 0x82)
            and positionInRange(position, "y", 0x6E, 0x72)
            and frame - ctx.scene_signature_since
                >= LAB_CONTROL_STABLE_FRAMES
        then
            ctx.input:abort()
            captureCheckpoint("06_lab_control")
            return true, {
                nametable = cachedNametable,
                position = position,
                stable_frames = frame - ctx.scene_signature_since,
            }
        end
        if ctx.input:is_idle() then
            ctx.input:pulse("a", 3, 24, "advance_oak_capture_sequence")
        end
        return false
    end,
    timeout = 4800,
    recovery = function(ctx)
        ctx.input:abort()
        captureCheckpoint("06_lab_control_timeout")
        return "fail"
    end,
    max_recoveries = 0,
    next = "align_starter_ball_x",
})

engine:add_state("align_starter_ball_x", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        local position = coordinates()
        if positionInRange(
            position,
            "x",
            STARTER_BALL_X - 2,
            STARTER_BALL_X + 2
        ) then
            ctx.input:abort()
            return true, position
        end
        pulseToward(
            ctx,
            position,
            "x",
            STARTER_BALL_X,
            "left",
            "right",
            "lab_align_starter_ball_x"
        )
        return false
    end,
    timeout = 600,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "approach_starter_ball",
})

engine:add_state("approach_starter_ball", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        local position = coordinates()
        if positionInRange(
            position,
            "y",
            STARTER_BALL_Y - 2,
            STARTER_BALL_Y + 2
        ) then
            ctx.input:abort()
            captureCheckpoint("07_starter_ball_aligned")
            return true, position
        end
        pulseToward(
            ctx,
            position,
            "y",
            STARTER_BALL_Y,
            "up",
            "down",
            "lab_approach_starter_ball"
        )
        return false
    end,
    timeout = 300,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "claim_pikachu",
})

-- The natural party structure is persistent SRAM and is observed read-only.
-- A fresh party of one species $19 at level 5 is the definitive proof that
-- the forced Yellow-version starter (Pikachu, National #025) was granted.
engine:add_state("claim_pikachu", {
    entry = function(ctx)
        ctx.input:abort()
        ctx.input:pulse("a", 3, 24, "interact_starter_ball")
    end,
    success = function(ctx)
        local party = leadPartySummary()
        if party.count == 1
            and party.species == PIKACHU_SPECIES_ID
            and party.level == 5
        then
            ctx.input:abort()
            captureCheckpoint("08_pikachu_obtained")
            return true, party
        end
        if ctx.input:is_idle() then
            ctx.input:pulse("a", 3, 24, "advance_starter_sequence")
        end
        return false
    end,
    timeout = 3600,
    recovery = function(ctx)
        ctx.input:abort()
        captureCheckpoint("08_pikachu_timeout")
        return "fail"
    end,
    max_recoveries = 0,
    next = "finish_pikachu_sequence",
})

-- The party fields are committed before the translated conversation has
-- necessarily exhausted every page.  Wait for the clean lab view rather than
-- assuming the SRAM update also means movement control has returned.
engine:add_state("finish_pikachu_sequence", {
    entry = function(ctx)
        ctx.input:abort()
        ctx.scene_signature = nil
        ctx.scene_signature_since = frame
    end,
    success = function(ctx)
        local position = coordinates()
        local party = leadPartySummary()
        local signature = string.format(
            "%08X:%02X:%02X",
            cachedNametable,
            position.x,
            position.y
        )
        if signature ~= ctx.scene_signature then
            ctx.scene_signature = signature
            ctx.scene_signature_since = frame
        end
        if LAB_NAMETABLES[cachedNametable]
            and party.count == 1
            and party.species == PIKACHU_SPECIES_ID
            and party.level == 5
            and frame - ctx.scene_signature_since >= 240
        then
            ctx.input:abort()
            captureCheckpoint("09_pikachu_sequence_complete")
            return true, {
                nametable = cachedNametable,
                position = position,
                stable_frames = frame - ctx.scene_signature_since,
            }
        end
        if not LAB_NAMETABLES[cachedNametable]
            and ctx.input:is_idle()
        then
            ctx.input:pulse("a", 3, 24, "finish_pikachu_dialogue")
        end
        return false
    end,
    timeout = 3600,
    recovery = function(ctx)
        ctx.input:abort()
        captureCheckpoint("09_pikachu_sequence_timeout")
        return "fail"
    end,
    max_recoveries = 0,
    next = "walk_to_rival_trigger",
})

engine:add_state("walk_to_rival_trigger", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx, elapsed)
        local position = coordinates()
        if elapsed >= 30 and not LAB_NAMETABLES[cachedNametable] then
            ctx.input:abort()
            ctx.rival_trigger_position = position
            captureCheckpoint("10_rival_trigger")
            return true, position
        end
        if ctx.input:is_idle() then
            ctx.input:pulse("down", 4, 1, "lab_walk_to_exit")
        end
        return false
    end,
    timeout = 1200,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "complete_rival_battle",
})

-- The first rival encounter is forced.  Require both phases: a non-lab battle
-- view after the intro delay, then a durable return to the clean laboratory.
-- Exact victory-text nametable hashes are useful evidence when they match, but
-- translated text changes those hashes; the durable post-battle laboratory
-- return is therefore also accepted as resolution evidence.  This does not
-- assume the pirated port always grants the reference game's level-up in SRAM.
engine:add_state("complete_rival_battle", {
    entry = function(ctx)
        ctx.input:abort()
        ctx.battle_return_signature = nil
        ctx.battle_return_signature_since = frame
        ctx.rival_battle_active_seen = false
        ctx.rival_battle_win_seen = false
        ctx.rival_battle_return_seen = false
        ctx.rival_battle_return_capture_pending = false
    end,
    success = function(ctx, elapsed)
        local position = coordinates()
        local party = leadPartySummary()
        if elapsed >= 240
            and elapsed <= 6000
            and elapsed % RIVAL_BATTLE_TRACE_PERIOD == 0
            and not LAB_NAMETABLES[cachedNametable]
        then
            writeBinary(
                string.format("rival_battle_trace_%04d.png", elapsed),
                emu.takeScreenshot()
            )
        end
        if elapsed >= 240 and not LAB_NAMETABLES[cachedNametable] then
            if not ctx.rival_battle_active_seen then
                captureCheckpoint("11_rival_battle_active")
            end
            ctx.rival_battle_active_seen = true
        end
        if cachedNametable == RIVAL_WIN_EXP_NAMETABLE
            or cachedNametable == RIVAL_WIN_REWARD_NAMETABLE
        then
            if not ctx.rival_battle_win_seen then
                captureCheckpoint("12_rival_battle_won")
            end
            ctx.rival_battle_win_seen = true
        end
        if ctx.rival_battle_active_seen
            and elapsed >= RIVAL_RESOLUTION_MIN_FRAMES
            and LAB_NAMETABLES[cachedNametable]
            and positionInRange(position, "x", 0x7E, 0x82)
            and party.count == 1
            and party.species == PIKACHU_SPECIES_ID
            and party.level >= 5
        then
            ctx.rival_battle_return_capture_pending =
                not ctx.rival_battle_return_seen
            ctx.rival_battle_return_seen = true
        end
        local rivalBattleResolved =
            ctx.rival_battle_win_seen
            or ctx.rival_battle_return_seen
        local signature = string.format(
            "%08X:%02X:%02X:%02X",
            cachedNametable,
            position.x,
            position.y,
            party.level
        )
        if signature ~= ctx.battle_return_signature then
            ctx.battle_return_signature = signature
            ctx.battle_return_signature_since = frame
        end
        -- The first LAB_NAMETABLE frame is still inside the fade and can be
        -- completely black.  Keep the logical return evidence immediately,
        -- but delay its screenshot until the laboratory has been stable long
        -- enough to be visibly rendered.
        if ctx.rival_battle_return_capture_pending
            and LAB_NAMETABLES[cachedNametable]
            and frame - ctx.battle_return_signature_since >= 120
        then
            captureCheckpoint("12_rival_battle_returned")
            ctx.rival_battle_return_capture_pending = false
        end
        if ctx.rival_battle_active_seen
            and rivalBattleResolved
            and elapsed >= RIVAL_RESOLUTION_MIN_FRAMES
            and LAB_NAMETABLES[cachedNametable]
            and positionInRange(position, "x", 0x7E, 0x82)
            and party.count == 1
            and party.species == PIKACHU_SPECIES_ID
            and party.level >= 5
            and frame - ctx.battle_return_signature_since >= 120
        then
            ctx.input:abort()
            captureCheckpoint("13_rival_battle_resolved")
            return true, {
                nametable = cachedNametable,
                position = position,
                party = party,
                stable_frames =
                    frame - ctx.battle_return_signature_since,
            }
        end
        local waitingForStableReturn =
            rivalBattleResolved
            and elapsed >= RIVAL_RESOLUTION_MIN_FRAMES
            and LAB_NAMETABLES[cachedNametable]
        if not waitingForStableReturn
            and ctx.input:is_idle()
        then
            ctx.input:pulse(
                "a",
                3,
                RIVAL_BATTLE_ADVANCE_GAP_FRAMES,
                "advance_rival_battle"
            )
        end
        return false
    end,
    timeout = 18000,
    recovery = function(ctx)
        ctx.input:abort()
        captureCheckpoint("13_rival_battle_timeout")
        return "fail"
    end,
    max_recoveries = 0,
    next = "leave_lab",
})

engine:add_state("leave_lab", {
    entry = function(ctx)
        ctx.input:abort()
        ctx.lab_exit_candidate = nil
        ctx.lab_exit_candidate_since = nil
    end,
    success = function(ctx)
        local position = coordinates()
        if not LAB_NAMETABLES[cachedNametable]
            and positionInRange(position, "x", 0x7E, 0x82)
            and positionInRange(position, "y", 0x6E, 0x72)
        then
            local candidate = string.format(
                "%08X:%02X:%02X",
                cachedNametable,
                position.x,
                position.y
            )
            if candidate ~= ctx.lab_exit_candidate then
                ctx.lab_exit_candidate = candidate
                ctx.lab_exit_candidate_since = frame
            elseif frame - ctx.lab_exit_candidate_since
                >= OUTSIDE_STABLE_FRAMES
            then
                ctx.input:abort()
                captureCheckpoint("14_outside_lab_stable")
                ctx.endpoint = "outside_lab_stable"
                return true, {
                    nametable = cachedNametable,
                    position = position,
                    stable_frames =
                        frame - ctx.lab_exit_candidate_since,
                }
            end
        else
            ctx.lab_exit_candidate = nil
            ctx.lab_exit_candidate_since = nil
        end
        if LAB_NAMETABLES[cachedNametable]
            and ctx.input:is_idle()
        then
            ctx.input:pulse("down", 4, 1, "walk_through_lab_exit")
        end
        return false
    end,
    timeout = 1800,
    recovery = function(ctx)
        ctx.input:abort()
        captureCheckpoint("14_lab_exit_timeout")
        return "fail"
    end,
    max_recoveries = 0,
})

engine:start("boot_delay", context)
local finalized = false

local function journalText()
    local lines = {
        "frame\tkind\tstate\ttarget\treason\tmessage",
    }
    for _, row in ipairs(engine:get_journal()) do
        lines[#lines + 1] = table.concat({
            tostring(row.frame or ""),
            tostring(row.kind or ""),
            tostring(row.state or ""),
            tostring(row.target or ""),
            tostring(row.reason or ""),
            (tostring(row.message or ""):gsub("[\t\r\n]", " ")),
        }, "\t")
    end
    return table.concat(lines, "\n") .. "\n"
end

local function routeEvidenceText()
    local lines = {
        "frame\tcheckpoint\tnametable_checksum\tx\ty\t" ..
            "party_count\tlead_species\tlead_level",
    }
    for _, row in ipairs(routeEvidence) do
        lines[#lines + 1] = string.format(
            "%d\t%s\t%08X\t%02X\t%02X\t%02X\t%02X\t%02X",
            row.frame,
            row.checkpoint,
            row.nametable,
            row.x,
            row.y,
            row.party_count,
            row.lead_species,
            row.lead_level
        )
    end
    return table.concat(lines, "\n") .. "\n"
end

local function writeEvidence()
    writeBinary("campaign_prototype_journal.tsv", journalText())
    writeBinary("campaign_prototype_route.tsv", routeEvidenceText())
    writeBinary(
        "campaign_prototype_memory_writes.tsv",
        memory:format_journal()
    )
end

emu.addEventCallback(function()
    inputQueue:tick()
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if finalized then
        return
    end
    frame = frame + 1
    if frame % CHECKSUM_SAMPLE_PERIOD == 0 then
        cachedNametable = nametableChecksum()
    end

    local status = engine:tick()
    if status == "running" then
        return
    end

    inputQueue:abort()
    finalized = true
    writeEvidence()
    if status ~= "completed" then
        local failure = engine:get_last_error() or {}
        writeBinary(
            "campaign_prototype_failure_screen.png",
            emu.takeScreenshot()
        )
        print(string.format(
            "POKEMON_CAMPAIGN_PROTOTYPE_FAIL frame=%d state=%s " ..
                "nametable=%08X reason=%s",
            frame,
            tostring(failure.state),
            cachedNametable,
            tostring(failure.message)
        ))
        emu.stop(1)
        return
    end

    local position = coordinates()
    print(string.format(
        "POKEMON_CAMPAIGN_PROTOTYPE_PASS mapper=163 region=%s " ..
        "frames=%d endpoint=%s nametable=%08X " ..
        "x=%02X y=%02X " ..
        "mode=controller writes_to_game=0 retries=%d",
        tostring(emu.getState()["region"]),
        frame,
        context.endpoint,
        cachedNametable,
        position.x,
        position.y,
        context.retries
    ))
    emu.stop(0)
end, emu.eventType.endFrame)
