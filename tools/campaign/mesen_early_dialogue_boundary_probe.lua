-- Natural, controller-only proof of the early dialogue layout contract.
--
-- The route is the proven campaign path from cold boot to laboratory control.
-- dialogue_capture.lua passively observes the translated PRG records and
-- blocks only controller A presses long enough to archive every rendered page,
-- including final pages without a wait arrow.  No emulated memory is written.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
local romPath = os.getenv("POKEMON_YELLOW_MESEN_ROM")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end
if romPath == nil or romPath == "" then
    error("POKEMON_YELLOW_MESEN_ROM is not set")
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
local DialogueCapture = loadModule("dialogue_capture.lua")
local DialogueTargets = loadModule("dialogue_targets.lua")

local BEDROOM_NAMETABLE = 0xE8ABD336
local DOWNSTAIRS_NAMETABLE = 0xE9D58C68
local OUTSIDE_NAMETABLE = 0xDD441740
local LAB_NAMETABLE = 0x7FFE1D9C
local CHECKSUM_SAMPLE_PERIOD = 5
local OUTSIDE_STABLE_FRAMES = 120
local TOWN_EAST_STEP_PULSES = 12
local FORCED_SEQUENCE_STABLE_FRAMES = 180
local LAB_CONTROL_STABLE_FRAMES = 240
local MOTHER_APPROACH_X = 0x40
local MOTHER_APPROACH_Y = 0x40

local frame = 0
local cachedNametable = 0

local function writeBinary(filename, data)
    local file = assert(io.open(
        outputDirectory .. "\\" .. filename,
        "wb"
    ))
    file:write(data)
    file:close()
end

local function writeText(filename, data)
    local file = assert(io.open(
        outputDirectory .. "\\" .. filename,
        "w"
    ))
    file:write(data)
    file:close()
end

local function nametableChecksum()
    local hash = 0
    for address = 0x2000, 0x2FFF do
        hash = (
            hash * 257 + emu.read(
                address,
                emu.memType.nesPpuDebug
            )
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

local capture = DialogueCapture.new({
    output_directory = outputDirectory,
    rom_path = romPath,
    targets = DialogueTargets,
    frame = function()
        return frame
    end,
})

local inputQueue = InputQueue.new(function(input, controller)
    capture:applyInput(input, controller)
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
    town_east_step_pulses = 0,
    oak_first_checkpointed = false,
    oak_lab_checkpointed = false,
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

local function abortAndRetry(ctx)
    ctx.input:abort()
    ctx.retries = ctx.retries + 1
    return "retry"
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

local routeEvidence = {}
local capturedCheckpoints = {}

local function captureCheckpoint(name)
    if capturedCheckpoints[name] then
        return
    end
    capturedCheckpoints[name] = true
    local position = coordinates()
    routeEvidence[#routeEvidence + 1] = {
        frame = frame,
        checkpoint = name,
        nametable = cachedNametable,
        x = position.x,
        y = position.y,
        required_completed =
            capture:completedRequiredTargetCount(),
        page_captures = capture:captureCount(),
    }
    writeBinary(name .. "_screen.png", emu.takeScreenshot())
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
        if cachedNametable == BEDROOM_NAMETABLE then
            ctx.input:abort()
            return true
        end
        if ctx.input:is_idle() then
            ctx.input:pulse("a", 3, 27, "advance_intro_dialogue")
        end
        return false
    end,
    timeout = 7500,
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
            captureCheckpoint("00_bedroom_path_aligned")
            return true, position
        end
        if ctx.input:is_idle() then
            local direction = position.x < 0xC0
                and "right"
                or "left"
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
        if cachedNametable == DOWNSTAIRS_NAMETABLE then
            ctx.input:abort()
            return true, coordinates()
        end
        if cachedNametable == BEDROOM_NAMETABLE
            and ctx.input:is_idle()
        then
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
        if elapsed >= 30
            and cachedNametable == DOWNSTAIRS_NAMETABLE
        then
            captureCheckpoint("01_downstairs_spawn")
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

engine:add_state("move_left_of_stairs", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        if cachedNametable ~= DOWNSTAIRS_NAMETABLE then
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
        if cachedNametable ~= DOWNSTAIRS_NAMETABLE then
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
    next = "align_below_mother",
})

-- The mother sprite is one tile below this controller-reached position in the
-- downstairs screen.  Face down, interact naturally, and let DialogueCapture
-- hold each A press until the complete translated page has been archived.
engine:add_state("align_below_mother", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        if cachedNametable ~= DOWNSTAIRS_NAMETABLE then
            return false
        end
        local position = coordinates()
        if positionInRange(
            position,
            "x",
            MOTHER_APPROACH_X - 2,
            MOTHER_APPROACH_X + 2
        ) and positionInRange(
            position,
            "y",
            MOTHER_APPROACH_Y - 2,
            MOTHER_APPROACH_Y + 2
        ) then
            ctx.input:abort()
            captureCheckpoint("01a_mother_approach")
            return true, position
        end
        pulseToward(
            ctx,
            position,
            "x",
            MOTHER_APPROACH_X,
            "left",
            "right",
            "downstairs_align_below_mother"
        )
        return false
    end,
    timeout = 600,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "talk_to_mother",
})

engine:add_state("talk_to_mother", {
    entry = function(ctx)
        ctx.input:abort()
        ctx.input:pulse("down", 4, 6, "face_mother")
    end,
    success = function(ctx)
        if capture:milestoneCompleted("mother_downstairs") then
            ctx.input:abort()
            captureCheckpoint("01b_mother_dialogue_complete")
            return true, coordinates()
        end
        if ctx.input:is_idle() then
            ctx.input:pulse("a", 3, 24, "advance_mother_dialogue")
        end
        return false
    end,
    timeout = 3600,
    recovery = function(ctx)
        ctx.input:abort()
        captureCheckpoint("01b_mother_dialogue_timeout")
        return "fail"
    end,
    max_recoveries = 0,
    next = "dismiss_mother_dialogue",
})

-- DialogueCapture archives the stable final page before it is dismissed.
-- Send one natural A press, then wait until the box has had time to close
-- before resuming movement around the table.
engine:add_state("dismiss_mother_dialogue", {
    entry = function(ctx)
        ctx.input:abort()
        ctx.input:pulse("a", 3, 90, "dismiss_mother_dialogue")
    end,
    success = function(ctx, elapsed)
        if elapsed >= 90 and ctx.input:is_idle() then
            ctx.input:abort()
            captureCheckpoint("01c_mother_dialogue_dismissed")
            return true, coordinates()
        end
        return false
    end,
    timeout = 300,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "round_table_left",
})

engine:add_state("round_table_left", {
    entry = function(ctx)
        ctx.input:abort()
    end,
    success = function(ctx)
        if cachedNametable ~= DOWNSTAIRS_NAMETABLE then
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
        if cachedNametable ~= DOWNSTAIRS_NAMETABLE then
            return false
        end
        local position = coordinates()
        if positionInRange(position, "y", 0x9E, 0xA2) then
            ctx.input:abort()
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
        if cachedNametable ~= DOWNSTAIRS_NAMETABLE then
            return false
        end
        local position = coordinates()
        if positionInRange(position, "x", 0x4E, 0x52) then
            ctx.input:abort()
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
        if cachedNametable == OUTSIDE_NAMETABLE then
            ctx.input:abort()
            ctx.outside_candidate = cachedNametable
            ctx.outside_candidate_since = frame
            return true, {
                nametable = cachedNametable,
                position = coordinates(),
            }
        end
        if cachedNametable == DOWNSTAIRS_NAMETABLE
            and ctx.input:is_idle()
        then
            ctx.input:pulse(
                "down",
                4,
                1,
                "walk_through_front_door"
            )
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
        if cachedNametable ~= OUTSIDE_NAMETABLE then
            ctx.outside_candidate = nil
            ctx.outside_candidate_since = nil
            return false
        end
        if cachedNametable ~= ctx.outside_candidate then
            ctx.outside_candidate = cachedNametable
            ctx.outside_candidate_since = frame
            return false
        end
        if frame - ctx.outside_candidate_since
            >= OUTSIDE_STABLE_FRAMES
        then
            captureCheckpoint("02_outside_stable")
            writeBinary(
                "early_dialogue_outside_nametable_4k.bin",
                nametableBytes()
            )
            return true, {
                nametable = cachedNametable,
                position = coordinates(),
                stable_frames =
                    frame - ctx.outside_candidate_since,
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

engine:add_state("align_town_north_path", {
    entry = function(ctx)
        ctx.input:abort()
        ctx.town_east_step_pulses = 0
    end,
    success = function(ctx)
        if ctx.town_east_step_pulses
                >= TOWN_EAST_STEP_PULSES
            and ctx.input:is_idle()
        then
            captureCheckpoint("03_town_north_path_aligned")
            return true, {
                position = coordinates(),
                east_step_pulses =
                    ctx.town_east_step_pulses,
            }
        end
        if ctx.input:is_idle() then
            ctx.town_east_step_pulses =
                ctx.town_east_step_pulses + 1
            ctx.input:pulse(
                "right",
                4,
                4,
                "town_align_north_path"
            )
        end
        return false
    end,
    timeout = 600,
    recovery = abortAndRetry,
    max_recoveries = 1,
    next = "walk_north_to_forced_sequence",
})

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
            captureCheckpoint("04_oak_sequence_candidate")
            return true, {
                nametable = cachedNametable,
                position = position,
                stable_frames =
                    frame - ctx.motion_signature_since,
            }
        end
        if ctx.input:is_idle() then
            ctx.input:pulse(
                "up",
                4,
                1,
                "town_oak_approach"
            )
        end
        return false
    end,
    timeout = 2400,
    recovery = function(ctx)
        ctx.input:abort()
        captureCheckpoint("04_oak_sequence_timeout")
        return "fail"
    end,
    max_recoveries = 0,
    next = "advance_oak_to_lab",
})

engine:add_state("advance_oak_to_lab", {
    entry = function(ctx)
        ctx.input:abort()
        ctx.scene_signature = nil
        ctx.scene_signature_since = frame
    end,
    success = function(ctx, elapsed)
        local position = coordinates()
        if capture:milestoneCompleted("oak_first_meeting")
            and not ctx.oak_first_checkpointed
        then
            ctx.oak_first_checkpointed = true
            captureCheckpoint("04a_oak_first_meeting_complete")
        end
        if capture:milestoneCompleted("oak_lab_initial")
            and not ctx.oak_lab_checkpointed
        then
            ctx.oak_lab_checkpointed = true
            captureCheckpoint("04b_oak_lab_initial_complete")
        end
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
            and cachedNametable == LAB_NAMETABLE
            and positionInRange(position, "x", 0x7E, 0x82)
            and positionInRange(position, "y", 0x6E, 0x72)
            and frame - ctx.scene_signature_since
                >= LAB_CONTROL_STABLE_FRAMES
            and capture:allRequiredCompleted()
        then
            ctx.input:abort()
            ctx.endpoint = "lab_control"
            captureCheckpoint("05_lab_control")
            writeBinary(
                "early_dialogue_lab_nametable_4k.bin",
                nametableBytes()
            )
            return true, {
                nametable = cachedNametable,
                position = position,
                stable_frames =
                    frame - ctx.scene_signature_since,
            }
        end
        if ctx.input:is_idle() then
            ctx.input:pulse(
                "a",
                3,
                24,
                "advance_oak_capture_sequence"
            )
        end
        return false
    end,
    timeout = 7200,
    recovery = function(ctx)
        ctx.input:abort()
        captureCheckpoint("05_lab_control_timeout")
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
            (tostring(row.message or ""):gsub(
                "[\t\r\n]",
                " "
            )),
        }, "\t")
    end
    return table.concat(lines, "\n") .. "\n"
end

local function routeEvidenceText()
    local lines = {
        "frame\tcheckpoint\tnametable_checksum\tx\ty\t" ..
            "required_targets_completed\tpage_captures",
    }
    for _, row in ipairs(routeEvidence) do
        lines[#lines + 1] = string.format(
            "%d\t%s\t%08X\t%02X\t%02X\t%d\t%d",
            row.frame,
            row.checkpoint,
            row.nametable,
            row.x,
            row.y,
            row.required_completed,
            row.page_captures
        )
    end
    return table.concat(lines, "\n") .. "\n"
end

local function validationText(errors)
    local lines = {
        "mode=natural_passive_controller",
        "writes_to_game=0",
        "endpoint=" .. context.endpoint,
        "required_targets=" ..
            tostring(capture:requiredTargetCount()),
        "required_completed=" ..
            tostring(capture:completedRequiredTargetCount()),
        "page_captures=" .. tostring(capture:captureCount()),
        "layouts=" .. capture:layoutSummary(true),
        "jadielle=false",
        "errors=" .. tostring(#errors),
    }
    for index, message in ipairs(errors) do
        lines[#lines + 1] = string.format(
            "error_%d=%s",
            index,
            tostring(message):gsub("[\r\n]", " ")
        )
    end
    return table.concat(lines, "\n") .. "\n"
end

local function writeEvidence(errors)
    capture:writeEvidence()
    writeText("early_dialogue_route.tsv", routeEvidenceText())
    writeText("early_dialogue_engine_journal.tsv", journalText())
    writeText(
        "early_dialogue_memory_writes.tsv",
        memory:format_journal()
    )
    writeText(
        "early_dialogue_validation.txt",
        validationText(errors)
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

    -- Observe the completed frame before the route queues its next A pulse.
    capture:tick()

    if frame % CHECKSUM_SAMPLE_PERIOD == 0 then
        cachedNametable = nametableChecksum()
    end

    local status = engine:tick()
    if status == "running" then
        return
    end

    inputQueue:abort()
    finalized = true
    local errors = capture:validationErrors()
    writeEvidence(errors)

    if status ~= "completed" or #errors ~= 0 then
        local failure = engine:get_last_error() or {}
        writeBinary(
            "early_dialogue_failure_screen.png",
            emu.takeScreenshot()
        )
        print(string.format(
            "POKEMON_EARLY_DIALOGUE_BOUNDARY_FAIL frame=%d " ..
            "state=%s reason=%s observer_errors=%d layouts=%s",
            frame,
            tostring(failure.state),
            tostring(failure.message),
            #errors,
            capture:layoutSummary(true)
        ))
        emu.stop(1)
        return
    end

    local position = coordinates()
    print(string.format(
        "POKEMON_EARLY_DIALOGUE_BOUNDARY_PASS mapper=163 region=%s " ..
        "frames=%d endpoint=%s nametable=%08X x=%02X y=%02X " ..
        "required=%d/%d pages=%d layouts=%s " ..
        "mode=natural_passive_controller writes_to_game=0 " ..
        "jadielle=false",
        tostring(emu.getState()["region"]),
        frame,
        context.endpoint,
        cachedNametable,
        position.x,
        position.y,
        capture:completedRequiredTargetCount(),
        capture:requiredTargetCount(),
        capture:captureCount(),
        capture:layoutSummary(true)
    ))
    emu.stop(0)
end, emu.eventType.endFrame)
