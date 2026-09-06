-- Controller-only campaign explorer.
-- Replays the verified opening stream, then walks a bounded frontier while
-- recording unique screen/coordinate signatures. No RAM writes, savestates,
-- cheats or rewind are used.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
local inputPath = os.getenv("POKEMON_YELLOW_MESEN_INPUT")
if not outputDirectory or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end
if not inputPath or inputPath == "" then
    error("POKEMON_YELLOW_MESEN_INPUT is not set")
end

local inputFile = assert(io.open(inputPath, "rb"))
local opening = inputFile:read("*a")
inputFile:close()
if #opening < 5300 then
    error("opening controller stream is shorter than 5300 frames")
end

local frame = 0
local phase = "opening"
-- The current default is the verified post-rival checkpoint at frame 4917;
-- begin autonomous exploration there rather than depending on English dialog
-- pagination in the state-driven prototype.
local function configValue(name, fallback)
    local value = tonumber(os.getenv(name))
    if value then return value end
    local file = io.open((os.getenv("POKEMON_YELLOW_MESEN_OUTPUT") or ".") .. "\\explorer_config.txt", "r")
    if file then
        for line in file:lines() do
            local key, raw = line:match("^([^=]+)=([0-9A-Fa-fxX]+)$")
            if key == name then value = tonumber(raw) end
        end
        file:close()
    end
    return value or fallback
end
local EXPLORATION_START = configValue("POKEMON_EXPLORER_START_FRAME", 4917)
local EXPLORATION_BUDGET = configValue("POKEMON_EXPLORER_MAX_FRAMES", 18000)
local extendOnNewMap = configValue("POKEMON_EXPLORER_EXTEND_ON_NEW_MAP", 0) == 1
local newMapExtensionFrames = math.max(0, configValue("POKEMON_EXPLORER_NEW_MAP_EXTENSION_FRAMES", 1800))
local explorationMaxBudget = math.max(EXPLORATION_BUDGET,
    configValue("POKEMON_EXPLORER_MAX_BUDGET", EXPLORATION_BUDGET))
local GUIDED_ROUTE_END = configValue("POKEMON_EXPLORER_GUIDED_END_FRAME", EXPLORATION_START)
local houseGuide = configValue("POKEMON_EXPLORER_GUIDE_HOUSE_EXIT", 0) == 1
local houseGuideFrame = 0
local houseGuideBudget = math.max(0,
    configValue("POKEMON_EXPLORER_HOUSE_EXIT_BUDGET", 1800))
local downstairsGuide = configValue("POKEMON_EXPLORER_GUIDE_DOWNSTAIRS", 0) == 1
local downstairsGuideFrame = -1
local downstairsRoute = configValue("POKEMON_EXPLORER_DOWNSTAIRS_ROUTE", 1)
local transitionSeed = configValue("POKEMON_EXPLORER_TRANSITION_SEED", 0) == 1
local transitionSeedFrame = -1
local directTransition = configValue("POKEMON_EXPLORER_DIRECT_TRANSITION", 0) == 1
local directTransitionFrame = 0
local directTransitionBudget = configValue("POKEMON_EXPLORER_DIRECT_TRANSITION_BUDGET", 900)
local exteriorGuide = configValue("POKEMON_EXPLORER_GUIDE_EXTERIOR", 0) == 1
local exteriorGuideFrame = 0
local outdoorDoorGuide = configValue("POKEMON_EXPLORER_OUTDOOR_DOOR_GUIDE", 0) == 1
local outdoorDoorGuideFrame = 0
local outdoorDoorGuideBudget = math.max(0,
    configValue("POKEMON_EXPLORER_OUTDOOR_DOOR_GUIDE_BUDGET", 1200))
local exteriorSweepHold = configValue("POKEMON_EXPLORER_EXTERIOR_SWEEP_HOLD", 600)
local exteriorActionPeriod = configValue("POKEMON_EXPLORER_EXTERIOR_ACTION_PERIOD", 120)
local exteriorRouteOffset = configValue("POKEMON_EXPLORER_EXTERIOR_ROUTE_OFFSET", 0)
local lockRouteOffset = configValue("POKEMON_EXPLORER_LOCK_ROUTE_OFFSET", 0) == 1
local buildingProbe = configValue("POKEMON_EXPLORER_EXTERIOR_BUILDING_PROBE", 0) == 1
local buildingProbeAll = configValue("POKEMON_EXPLORER_BUILDING_PROBE_ALL", 0) == 1
local buildingProbeAllAfterInterior = configValue("POKEMON_EXPLORER_BUILDING_PROBE_ALL_AFTER_INTERIOR", 0) == 1
local buildingProbeFrame = 0
local buildingProbeDirection = configValue("POKEMON_EXPLORER_BUILDING_PROBE_DIRECTION", 2)
local buildingProbeBudget = configValue("POKEMON_EXPLORER_BUILDING_PROBE_BUDGET", 300)
local buildingApproachFrames = configValue("POKEMON_EXPLORER_BUILDING_APPROACH_FRAMES", 120)
local buildingApproachTurnFrames = configValue("POKEMON_EXPLORER_BUILDING_APPROACH_TURN_FRAMES", 120)
local buildingProbeLogLast = -30
local buildingOscillationCount = 0
local buildingTargetX = configValue("POKEMON_EXPLORER_BUILDING_TARGET_X", 0)
local buildingTargetY = configValue("POKEMON_EXPLORER_BUILDING_TARGET_Y", 0)
local buildingTerminalAction = configValue("POKEMON_EXPLORER_BUILDING_TERMINAL_ACTION", 0x10)
local buildingDoorAction = configValue("POKEMON_EXPLORER_BUILDING_DOOR_ACTION", 0x01)
local buildingDetourY = configValue("POKEMON_EXPLORER_BUILDING_DETOUR_Y", 0x40)
local buildingProbeHash = configValue("POKEMON_EXPLORER_BUILDING_PROBE_HASH", 0)
local buildingProbeHash2 = configValue("POKEMON_EXPLORER_BUILDING_PROBE_HASH2", 0)
local buildingProbeHash3 = configValue("POKEMON_EXPLORER_BUILDING_PROBE_HASH3", 0)
local buildingProbeHash4 = configValue("POKEMON_EXPLORER_BUILDING_PROBE_HASH4", 0)
local buildingProbeHash5 = configValue("POKEMON_EXPLORER_BUILDING_PROBE_HASH5", 0)
local buildingCorridorGuide = configValue("POKEMON_EXPLORER_BUILDING_CORRIDOR_GUIDE", 0) == 1
local buildingCorridorFrame = 0
local interiorHoldFrame = 0
local interiorHoldBudget = configValue("POKEMON_EXPLORER_INTERIOR_HOLD_BUDGET", 900)
local interiorConfirmHold = configValue("POKEMON_EXPLORER_INTERIOR_CONFIRM_HOLD", 0) == 1
local interiorConfirmActionSweep = configValue("POKEMON_EXPLORER_INTERIOR_CONFIRM_ACTION_SWEEP", 0) == 1
local interiorConfirmActionPeriod = configValue("POKEMON_EXPLORER_INTERIOR_CONFIRM_ACTION_PERIOD", 120)
local interiorConfirmIncludeMenu = configValue("POKEMON_EXPLORER_INTERIOR_CONFIRM_INCLUDE_MENU", 0) == 1
local interiorConfirmMoveSweep = configValue("POKEMON_EXPLORER_INTERIOR_CONFIRM_MOVE_SWEEP", 0) == 1
local interiorSweepFrame = 0
local interiorSweepSegment = configValue("POKEMON_EXPLORER_INTERIOR_SWEEP_SEGMENT", 360)
local interiorActionPulse = configValue("POKEMON_EXPLORER_INTERIOR_ACTION_PULSE", 15)
local genericActionPeriod = configValue("POKEMON_EXPLORER_GENERIC_ACTION_PERIOD", 180)
local moveActionSweep = configValue("POKEMON_EXPLORER_MOVE_ACTION_SWEEP", 0) == 1
local moveActionPeriod = configValue("POKEMON_EXPLORER_MOVE_ACTION_PERIOD", 120)
local blockedEdgeProbe = configValue("POKEMON_EXPLORER_BLOCKED_EDGE_PROBE", 0) == 1
local blockedEdgeProbeFrame = 0
local blockedEdgeProbeDirection = 0
local battlePcMin = configValue("POKEMON_EXPLORER_BATTLE_PC_MIN", 0xF200)
local battlePcMax = configValue("POKEMON_EXPLORER_BATTLE_PC_MAX", 0xF2FF)
local battleHash = configValue("POKEMON_EXPLORER_BATTLE_HASH", 0)
local stopOnBattle = configValue("POKEMON_EXPLORER_STOP_ON_BATTLE", 0) == 1
local battleActionPeriod = math.max(1, configValue("POKEMON_EXPLORER_BATTLE_ACTION_PERIOD", 45))
local battleActionHold = math.max(0, configValue("POKEMON_EXPLORER_BATTLE_ACTION_HOLD", 8))
local battleActionButton = math.max(0, math.min(0xFF,
    configValue("POKEMON_EXPLORER_BATTLE_ACTION_BUTTON", 0x01)))
local battleAlternateButton = math.max(0, math.min(0xFF,
    configValue("POKEMON_EXPLORER_BATTLE_ALTERNATE_BUTTON", 0x00)))
local battleMaxFrames = math.max(0, configValue("POKEMON_EXPLORER_BATTLE_MAX_FRAMES", 1800))
local battleCooldownLength = math.max(0, configValue("POKEMON_EXPLORER_BATTLE_COOLDOWN_FRAMES", 180))
local tracePc = configValue("POKEMON_EXPLORER_TRACE_PC", 0) == 1
local eventPcMin = configValue("POKEMON_EXPLORER_EVENT_PC_MIN", 0)
local eventPcMax = configValue("POKEMON_EXPLORER_EVENT_PC_MAX", 0)
local interiorConfirmHash = configValue("POKEMON_EXPLORER_INTERIOR_CONFIRM_HASH", 0)
local stopOnInterior = configValue("POKEMON_EXPLORER_STOP_ON_INTERIOR", 0) == 1
local dojoHash = configValue("POKEMON_EXPLORER_DOJO_HASH", 0)
local dojoContextHash = configValue("POKEMON_EXPLORER_DOJO_CONTEXT_HASH", 0)
local menuHash = configValue("POKEMON_EXPLORER_MENU_HASH", 0)
local menuRecoveryButton = math.max(0, math.min(0xFF,
    configValue("POKEMON_EXPLORER_MENU_RECOVERY_BUTTON", 0x02)))
local menuRecoveryPeriod = math.max(1, configValue("POKEMON_EXPLORER_MENU_RECOVERY_PERIOD", 30))
local menuRecoveryHold = math.max(0, configValue("POKEMON_EXPLORER_MENU_RECOVERY_HOLD", 6))
local menuRecoveryMaxFrames = math.max(0, configValue("POKEMON_EXPLORER_MENU_RECOVERY_MAX_FRAMES", 600))
local stopOnMenuTimeout = configValue("POKEMON_EXPLORER_STOP_ON_MENU_TIMEOUT", 0) == 1
local menuRecoveryFrame = 0
local menuRecoveryTimedOut = false
local menuRecoveries = 0
local captureAllTransitions = configValue("POKEMON_EXPLORER_CAPTURE_ALL_TRANSITIONS", 0) == 1
local checkpointPeriod = math.max(0, configValue("POKEMON_EXPLORER_CHECKPOINT_PERIOD", 600))
local frontierProbeHash = configValue("POKEMON_EXPLORER_FRONTIER_PROBE_HASH", 0)
local frontierProbeX = configValue("POKEMON_EXPLORER_FRONTIER_PROBE_X", 0)
local frontierProbeY = configValue("POKEMON_EXPLORER_FRONTIER_PROBE_Y", 0)
local frontierProbeAnyPosition = configValue("POKEMON_EXPLORER_FRONTIER_PROBE_ANY_POSITION", 0) == 1
local frontierProbeExtendOnActivation = configValue("POKEMON_EXPLORER_FRONTIER_PROBE_EXTEND_ON_ACTIVATION", 0) == 1
local frontierProbeExtensionFrames = configValue("POKEMON_EXPLORER_FRONTIER_PROBE_EXTENSION_FRAMES", 6000)
local frontierProbeDirection = configValue("POKEMON_EXPLORER_FRONTIER_PROBE_DIRECTION", 0)
local frontierProbeBudget = configValue("POKEMON_EXPLORER_FRONTIER_PROBE_BUDGET", 600)
local frontierProbeAll = configValue("POKEMON_EXPLORER_FRONTIER_PROBE_ALL", 0) == 1
local frontierProbeDiagonal = configValue("POKEMON_EXPLORER_FRONTIER_PROBE_DIAGONAL", 0) == 1
local frontierProbeDelay = configValue("POKEMON_EXPLORER_FRONTIER_PROBE_DELAY", 0)
local frontierProbeSequence = configValue("POKEMON_EXPLORER_FRONTIER_PROBE_SEQUENCE", 0)
local frontierProbeFrame = 0
local frontierCaptureDelay = -1
local frontierProbeActivated = false
local frontierProbeCompleted = false
local interiorDoorProbe = configValue("POKEMON_EXPLORER_INTERIOR_DOOR_PROBE", 0) == 1
local interiorDoorProbeFrame = 0
local actionIndex = 1
local actionFrame = 0
local routeIndex = 11
local routeFrame = 0
local signatureLast = ""
local stableFrames = 0
local seen = {}
local transitionCounts = {}
local captures = 0
local directions = {
    {name = "up", value = 0x10, opposite = 0x20},
    {name = "right", value = 0x80, opposite = 0x40},
    {name = "down", value = 0x20, opposite = 0x10},
    {name = "left", value = 0x40, opposite = 0x80},
}
local nodes = {}
local currentNode = nil
local movePhase = "settle"
local moveFrame = 0
local moveFrom = nil
local moveDirection = nil
local moveStartKey = nil
-- When DFS stagnates at a collision or doorway, sweep a short cross-shaped
-- recovery route before trying the frontier again. This breaks camera/door
-- deadlocks without requiring a savestate or RAM intervention.
local recoveryIndex = 0
local recoveryFrame = 0
local recoveryHold = configValue("POKEMON_EXPLORER_RECOVERY_HOLD_FRAMES", 120)
local recoveryRoute = {0x20, 0x40, 0x10, 0x80}
local recoveryActionSweep = configValue("POKEMON_EXPLORER_RECOVERY_ACTION_SWEEP", 0) == 1
local recoveryActionPeriod = configValue("POKEMON_EXPLORER_RECOVERY_ACTION_PERIOD", 90)
local recoverySpecialHash = configValue("POKEMON_EXPLORER_RECOVERY_MAP_HASH", 0)
local recoverySpecialStart = configValue("POKEMON_EXPLORER_RECOVERY_START_DIRECTION", 0)
local recoveryMapCounts = {}
local directionSeed = configValue("POKEMON_EXPLORER_DIRECTION_SEED", 0)
-- The verified cold-boot position is in the bedroom near the right wall;
-- begin with the likely south exit before applying generic edge heuristics.
local directionCursor = directionSeed == 0 and 3
    or (((directionSeed % #directions) + #directions) % #directions + 1)
local MOVE_HOLD_FRAMES = configValue("POKEMON_EXPLORER_MOVE_HOLD_FRAMES", 60)
local EDGE_HOLD_FRAMES = configValue("POKEMON_EXPLORER_EDGE_HOLD_FRAMES", 180)
local SETTLE_FRAMES = configValue("POKEMON_EXPLORER_SETTLE_FRAMES", 18)
local guidedFrame = 0
local guidedStart = EXPLORATION_START
local GUIDED_EVERY = 3000
local GUIDED_LENGTH = 600
local battleMode = false
local battleStopTriggered = false
local battleQuietFrames = 0
local battleFrame = 0
local battleCooldown = 0
local battleCount = 0
local battleCaptureCount = 0
local movedEdges = 0
local blockedEdges = 0
local mapHashes = {}
local exteriorReached = false
local buildingSeen = false
local buildingEntered = false
local interiorSeen = false
local interiorVisualSeen = false
local lastExteriorVisualHash = nil
local interiorEntryCaptured = false
local interiorCaptureDelay = -1
local lastStableHash = nil
local graphEdges = {}
local frontierExhausted = false
local terminationReason = "budget"
local stagnantFrames = 0
local lastCaptureCount = 0
local stagnationResets = 0
local writeText
local checksumNametable

local function writeSummary()
    local mapCount = 0
    for _ in pairs(mapHashes) do mapCount = mapCount + 1 end
    local recoveryCount = 0
    for _, count in pairs(recoveryMapCounts) do recoveryCount = recoveryCount + count end
    local state = emu.getState()
    local lastPc = state["cpu.pc"] or 0
    local lastX = emu.read(0x0304, emu.memType.nesDebug)
    local lastY = emu.read(0x0306, emu.memType.nesDebug)
    local lastMapHash = checksumNametable()
        writeText("exploration_summary.tsv", string.format(
            "frames\t%d\ncaptures\t%d\nmoved_edges\t%d\nblocked_edges\t%d\nmap_hashes\t%d\nbattles\t%d\nrecoveries\t%d\nmenu_recoveries\t%d\nmenu_recovery_timed_out\t%s\nmenu_recovery_button\t%02X\nmenu_recovery_period\t%d\nmenu_recovery_hold\t%d\nmenu_recovery_max_frames\t%d\nfrontier_probe_activated\t%s\nfrontier_probe_completed\t%s\nfrontier_exhausted\t%s\nstagnation_resets\t%d\nroute_offset\t%d\ndirection_seed\t%d\ndetour_y\t%02X\nlast_x\t%02X\nlast_y\t%02X\nlast_pc\t%04X\nlast_map_hash\t%08X\nexploration_start\t%d\nexploration_budget\t%d\nbuilding_target_x\t%d\nbuilding_target_y\t%d\nexterior_reached\t%s\nbuilding_seen\t%s\nbuilding_entered\t%s\ninterior_seen\t%s\ninterior_visual_seen\t%s\n",
            frame, captures, movedEdges, blockedEdges, mapCount, battleCount, recoveryCount,
            menuRecoveries, tostring(menuRecoveryTimedOut), menuRecoveryButton, menuRecoveryPeriod, menuRecoveryHold, menuRecoveryMaxFrames, tostring(frontierProbeActivated), tostring(frontierProbeCompleted), tostring(frontierExhausted), stagnationResets, exteriorRouteOffset,
            directionSeed, buildingDetourY, lastX, lastY, lastPc, lastMapHash, EXPLORATION_START, EXPLORATION_BUDGET, buildingTargetX, buildingTargetY, tostring(exteriorReached), tostring(buildingSeen), tostring(buildingEntered), tostring(interiorSeen), tostring(interiorVisualSeen)
    ))
    writeText("termination_reason.tsv", "reason\n" .. terminationReason .. "\n")
end
local function visualHash()
    local value = 2166136261
    -- The player sprite moves on the lower half of these maps. Restrict the
    -- visual fingerprint to stable upper scenery so walking in front of a
    -- door cannot masquerade as an interior transition.
    for y = 16, 80, 16 do
        for x = 8, 240, 16 do
            value = (value ~ emu.getPixel(x, y)) * 16777619 % 0x100000000
        end
    end
    return value
end
local firstNode = true
local startupSequence = {4, 1}
local startupHoldSequence = {4, 60}
local startupIndex = 1
local startupMove = false
local startupHold = 0
local startupAFrames = 0
local adaptiveHold = MOVE_HOLD_FRAMES
local consecutiveBlocked = 0
-- Known controller-only bridge from the lab exit to the Route 1/Viridian
-- diagnostic. It is replayed before frontier exploration begins.
local bridge = {
    {frames = 40, value = 0x20},
    {frames = 8, value = 0x00},
    {frames = 104, value = 0x40},
    {frames = 8, value = 0x00},
    {frames = 40, value = 0x20},
    {frames = 8, value = 0x00},
    {frames = 32, value = 0x10},
    {frames = 8, value = 0x00},
    {frames = 2, value = 0x01},
    {frames = 18, value = 0x00},
}

writeText = function(filename, text)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "w"))
    file:write(text)
    file:close()
end

local function writeBinary(filename, bytes)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    file:write(bytes)
    file:close()
end

local function writeVisibleScreenshot(filename)
    local first = emu.getPixel(8, 16)
    local varied = false
    for y = 16, 80, 16 do
        for x = 8, 240, 16 do
            if emu.getPixel(x, y) ~= first then varied = true; break end
        end
        if varied then break end
    end
    if varied then writeBinary(filename, emu.takeScreenshot()) end
end

checksumNametable = function()
    local hash = 0
    for address = 0x2000, 0x2FFF do
        hash = (hash * 257 + emu.read(address, emu.memType.nesPpuDebug))
            % 0x100000000
    end
    return hash
end

local function checksumContextRam()
    local hash = 0
    for address = 0x0300, 0x03FF do
        if address ~= 0x0304 and address ~= 0x0306 then
            hash = (hash * 257 + emu.read(address, emu.memType.nesDebug))
                % 0x100000000
        end
    end
    return hash
end

local function signature()
    local hash = checksumNametable()
    local contextHash = checksumContextRam()
    local x = emu.read(0x0304, emu.memType.nesDebug)
    local y = emu.read(0x0306, emu.memType.nesDebug)
    local b0 = emu.read(0x0300, emu.memType.nesDebug)
    local b1 = emu.read(0x0301, emu.memType.nesDebug)
    local b2 = emu.read(0x0302, emu.memType.nesDebug)
    local b3 = emu.read(0x0303, emu.memType.nesDebug)
    local c0 = emu.read(0x0308, emu.memType.nesDebug)
    local c1 = emu.read(0x0309, emu.memType.nesDebug)
    local c2 = emu.read(0x030A, emu.memType.nesDebug)
    local c3 = emu.read(0x030B, emu.memType.nesDebug)
    local nodeKey = string.format("%08X:%02X:%02X", hash, x & 0xF0, y & 0xF0)
    return nodeKey, hash, x, y, b0, b1, b2, b3, c0, c1, c2, c3, contextHash
end

local function mapLabel(hash)
    if hash == 0xCEC7D05A then return "bedroom_house" end
    if hash == 0xCFF1898C then return "downstairs_candidate" end
    if hash == 0xC3601464 then return "exterior_house" end
    if hash == 0x68EAC002 then return "building_interior_candidate" end
    if hash == 0xF16EB24A then return "verified_indoor_room" end
    return string.format("unknown_%08X", hash)
end

local function decode(value)
    return {
        a = (value & 0x01) ~= 0,
        b = (value & 0x02) ~= 0,
        select = (value & 0x04) ~= 0,
        start = (value & 0x08) ~= 0,
        up = (value & 0x10) ~= 0,
        down = (value & 0x20) ~= 0,
        left = (value & 0x40) ~= 0,
        right = (value & 0x80) ~= 0,
    }
end

local function captureIfNew()
    local key, hash, x, y, b0, b1, b2, b3, c0, c1, c2, c3, contextHash = signature()
    if hash == 0x143B5DCC and stableFrames >= SETTLE_FRAMES then
        buildingSeen = true
        lastExteriorVisualHash = visualHash()
    end
    if interiorConfirmHash ~= 0 and hash == interiorConfirmHash
        and stableFrames >= SETTLE_FRAMES then
        interiorSeen = true
        buildingEntered = true
        interiorVisualSeen = true
        if buildingProbeAllAfterInterior then buildingProbeFrame = 0 end
        if stopOnInterior then
            terminationReason = "interior"
            mapHashes[string.format("%08X", hash)] = true
            local stopLog = assert(io.open(outputDirectory .. "\\interior_stop.tsv", "w"))
            stopLog:write(string.format("frame\thash\tx\ty\tpc\n%d\t%08X\t%02X\t%02X\t%04X\n",
                frame, hash, x, y, emu.getState()["cpu.pc"] or 0))
            stopLog:close()
            writeSummary()
            writeGraph()
            writeFrontier()
            print(string.format(
                "POKEMON_CAMPAIGN_EXPLORER_INTERIOR_PASS frames=%d map=%08X battles=%d",
                frame, hash, battleCount))
            print("POKEMON_MESEN_PASS")
            emu.stop(0)
            return
        end
    end
    if stableFrames >= SETTLE_FRAMES then
        local mapKey = string.format("%08X", hash)
        if not mapHashes[mapKey] and extendOnNewMap and newMapExtensionFrames > 0 then
            EXPLORATION_BUDGET = math.min(explorationMaxBudget,
                EXPLORATION_BUDGET + newMapExtensionFrames)
            writeText("budget_extensions.tsv", string.format(
                "%d\t%08X\t%d\t%d\n", frame, hash,
                newMapExtensionFrames, EXPLORATION_BUDGET))
        end
        mapHashes[mapKey] = true
    end
    if stableFrames >= SETTLE_FRAMES and lastStableHash ~= nil
        and lastStableHash ~= hash
    then
        -- The cold-boot bedroom transitions directly into the known outdoor
        -- map. Mark it on entry as well as when leaving it; otherwise the
        -- exterior guide never activates after the first map transition.
        if hash == 0xCFF1898C
            or (lastStableHash == 0xCFF1898C and hash ~= 0xCFF1898C) then
            exteriorReached = true
        end
        if lastStableHash == 0x143B5DCC and hash == 0x68EAC002 then
            if not interiorEntryCaptured then interiorCaptureDelay = 120 end
        end
        local file = assert(io.open(outputDirectory .. "\\map_transitions.tsv", "a"))
        file:write(string.format("%d\t%08X\t%08X\t%02X\t%02X\n",
            frame, lastStableHash, hash, x, y))
        file:close()
        local contextFile = assert(io.open(outputDirectory .. "\\map_context.tsv", "a"))
        contextFile:write(string.format("%d\t%08X\t%08X\t%08X\n",
            frame, lastStableHash, hash, contextHash))
        contextFile:close()
        if hash == 0x9BA474C0 or hash == 0x451EA43C
            or lastStableHash == 0x9BA474C0 or lastStableHash == 0x451EA43C then
            local diagnostic = assert(io.open(outputDirectory .. "\\interior_diagnostics.tsv", "a"))
            diagnostic:write(string.format("%d\t%08X\t%08X\t%08X\t%02X\t%02X\t%04X\n",
                frame, lastStableHash, hash, contextHash, x, y, emu.getState()["cpu.pc"] or 0))
            diagnostic:close()
        end
        local transitionKey = string.format("%08X>%08X", lastStableHash, hash)
        transitionCounts[transitionKey] = (transitionCounts[transitionKey] or 0) + 1
        if (lastStableHash == 0x143B5DCC and hash == 0x68EAC002)
            or (lastStableHash == 0x68EAC002 and hash == 0x143B5DCC) then
            buildingOscillationCount = buildingOscillationCount + 1
            if buildingOscillationCount >= 3 then
                if buildingProbeDirection ~= 5 then
                    buildingProbeDirection = (buildingProbeDirection % 4) + 1
                end
                buildingProbeFrame = 0
                buildingOscillationCount = 0
            end
        end
        if transitionCounts[transitionKey] == 3 then
            writeText("loop_transitions.tsv", string.format(
                "%d\t%s\t%d\n", frame, transitionKey, transitionCounts[transitionKey]))
        end
        if captureAllTransitions or hash == 0x68EAC002 or hash == 0x4091785A
            or hash == 0x12A007D6 or hash == 0x2331057A then
            writeVisibleScreenshot(string.format("transition_%08X_%d.png", hash, frame))
        end
        nodes = {}
        currentNode = nil
        movePhase = "settle"
        adaptiveHold = MOVE_HOLD_FRAMES
        consecutiveBlocked = 0
    end
    if stableFrames >= SETTLE_FRAMES then lastStableHash = hash end
    if key == signatureLast then
        stableFrames = stableFrames + 1
    else
        if battleMode then
            local pulse = frame % 48
            emu.setInput(decode(pulse < 4 and 0x01 or 0x00), 0)
            return
        end
        signatureLast = key
        stableFrames = 0
    end
    if stableFrames < SETTLE_FRAMES then
        return key, hash, x, y
    end
    if seen[key] then
        return key, hash, x, y
    end
    seen[key] = true
    captures = captures + 1
    writeBinary(
        string.format("explore_%03d_screen.png", captures),
        emu.takeScreenshot()
    )
    local log = string.format("capture=%03d frame=%d phase=%s map=%s action=%s hash=%08X context=%08X x=%02X y=%02X ram=%02X%02X%02X%02X ctx=%02X%02X%02X%02X\n",
        captures, frame, phase, mapLabel(hash), directions[actionIndex].name, hash, contextHash, x, y, b0, b1, b2, b3, c0, c1, c2, c3)
    local existing = ""
    local handle = io.open(outputDirectory .. "\\exploration.tsv", "r")
    if handle then
        existing = handle:read("*a")
        handle:close()
    end
    writeText("exploration.tsv", existing .. log)
    return key, hash, x, y
end

local function appendEdge(fromKey, direction, toKey, moved)
    if moved then movedEdges = movedEdges + 1 else blockedEdges = blockedEdges + 1 end
    graphEdges[#graphEdges + 1] = {fromKey, direction, toKey, moved}
    local file = assert(io.open(outputDirectory .. "\\exploration_edges.tsv", "a"))
    file:write(string.format("%s\t%s\t%s\t%s\n", fromKey, direction, toKey, tostring(moved)))
    file:close()
end

local function writeGraph()
    local lines = {"digraph explorer {", "  rankdir=LR;"}
    for _, edge in ipairs(graphEdges) do
        local color = edge[4] and "green" or "red"
        local style = edge[4] and "solid" or "dashed"
        lines[#lines + 1] = string.format(
            '  "%s" -> "%s" [label="%s", color=%s, style=%s];',
            edge[1], edge[3], edge[2], color, style
        )
    end
    lines[#lines + 1] = "}"
    writeText("exploration_graph.dot", table.concat(lines, "\n") .. "\n")
end

local function writeFrontier()
    local lines = {"node\ttried\tremaining"}
    for key, node in pairs(nodes) do
        local tried, remaining = {}, {}
        for index, direction in ipairs(directions) do
            if node.tried[index] then tried[#tried + 1] = direction.name
            else remaining[#remaining + 1] = direction.name end
        end
        lines[#lines + 1] = string.format("%s\t%s\t%s", key,
            table.concat(tried, ","), table.concat(remaining, ","))
    end
    writeText("exploration_frontier.tsv", table.concat(lines, "\n") .. "\n")
end

local function logBattle(event, pc)
    local file = assert(io.open(outputDirectory .. "\\battles.tsv", "a"))
    file:write(string.format("%s\t%d\t%02X\t%02X\t%04X\n", event, frame,
        emu.read(0x0304, emu.memType.nesDebug),
        emu.read(0x0306, emu.memType.nesDebug), pc))
    file:close()
end

local function chooseNextDirection(node)
    if startupIndex <= #startupSequence then
        local index = startupSequence[startupIndex]
        startupHold = startupHoldSequence[startupIndex] or 60
        startupIndex = startupIndex + 1
        node.tried[index] = true
        startupMove = true
        return index
    end
    if firstNode then
        firstNode = false
        node.tried[3] = true
        return 3
    end
    local order = {1, 2, 3, 4}
    if node.x and node.x <= 0x20 then order = {4, 1, 3, 2}
    elseif node.x and node.x >= 0xD0 then order = {2, 1, 3, 4}
    elseif node.y and node.y <= 0x20 then order = {1, 2, 4, 3}
    elseif node.y and node.y >= 0xD0 then order = {3, 2, 4, 1} end
    for offset = 0, #directions - 1 do
        local index = order[((directionCursor + offset - 2) % #directions) + 1]
        if not node.tried[index] then
            directionCursor = (index % #directions) + 1
            node.tried[index] = true
            return index
        end
    end
    return nil
end

emu.addEventCallback(function()
    local value = 0
    if phase == "opening" or frame < EXPLORATION_START then
        value = string.byte(opening, frame + 1) or 0
    else
        if frame < GUIDED_ROUTE_END then
            value = string.byte(opening, frame + 1) or 0
            emu.setInput(decode(value), 0)
            return
        end
        if directTransition and directTransitionFrame < directTransitionBudget then
            local hash = checksumNametable()
            if hash == 0xCEC7D05A then
                local x = emu.read(0x0304, emu.memType.nesDebug)
                local y = emu.read(0x0306, emu.memType.nesDebug)
                local value = (x < 0xB8 and 0x80)
                    or (y > 0x70 and 0x10)
                    or 0x40
                emu.setInput(decode(value), 0)
                directTransitionFrame = directTransitionFrame + 1
                return
            end
            directTransition = false
        end
            if buildingProbe and exteriorReached and buildingProbeFrame < buildingProbeBudget
            and (buildingProbeAll or (buildingProbeAllAfterInterior and interiorSeen)
                or checksumNametable() == 0x143B5DCC
                or (buildingProbeHash ~= 0 and checksumNametable() == buildingProbeHash)
                or (buildingProbeHash2 ~= 0 and checksumNametable() == buildingProbeHash2)
                or checksumNametable() == 0x152085AA)
            and not (interiorConfirmHash ~= 0 and checksumNametable() == interiorConfirmHash) then
            local probeDirections = {0x80, 0x40, 0x20, 0x10}
            local probeIndex = buildingProbeDirection
            if probeIndex == 0 then
                probeIndex = (math.floor(buildingProbeFrame / 300) % 4) + 1
            end
            local value
            if checksumNametable() == 0x143B5DCC and buildingProbeDirection == 5
                and not (buildingProbeHash2 ~= 0 and checksumNametable() == buildingProbeHash2) then
                local probeX = emu.read(0x0304, emu.memType.nesDebug)
                local probeY = emu.read(0x0306, emu.memType.nesDebug)
                local targetX = buildingTargetX ~= 0 and buildingTargetX or 128
                local targetY = buildingTargetY ~= 0 and buildingTargetY or 112
                if probeX < 0x40 and probeY == targetY then value = 0x10
                elseif probeX < 0x40 and probeY > buildingDetourY then value = 0x10
                elseif probeX < 0x40 and probeY < buildingDetourY then value = 0x20
                elseif probeX < targetX and probeY == buildingDetourY then value = 0x80
                elseif probeY > targetY then value = 0x10
                elseif probeY < targetY then value = 0x20
                elseif probeX >= 0x70 then value = buildingTerminalAction
                elseif probeY > targetY then value = 0x10
                elseif probeX < targetX then value = 0x80
                elseif probeX > targetX then value = 0x40
                else value = 0x01 end
            elseif buildingProbeHash2 ~= 0 and checksumNametable() == buildingProbeHash2 then
                value = buildingDoorAction
            elseif checksumNametable() == 0x152085AA then
                value = ((buildingProbeFrame % 30) < 12 and 0x01 or 0x00)
            elseif checksumNametable() == 0x143B5DCC then
                if buildingProbeDirection == 3 then
                    value = buildingProbeFrame < buildingApproachFrames and 0x20
                        or (buildingProbeFrame < buildingApproachFrames + buildingApproachTurnFrames and 0x80 or 0x10)
                elseif buildingProbeDirection == 4 then
                    value = buildingProbeFrame < buildingApproachFrames and 0x10
                        or (buildingProbeFrame < buildingApproachFrames + buildingApproachTurnFrames and 0x80 or 0x20)
                else
                    value = buildingProbeFrame < buildingApproachFrames and 0x80
                        or (buildingProbeFrame < buildingApproachFrames + buildingApproachTurnFrames and 0x10 or 0x80)
                end
            else
                local phase = math.floor(buildingProbeFrame / 600) % 4
                value = probeDirections[phase + 1] or 0x80
            end
            if buildingProbeFrame % 30 < 8 then value = value | 0x01 end
            if frame - buildingProbeLogLast >= 30 then
                local log = assert(io.open(outputDirectory .. "\\building_probe.tsv", "a"))
                log:write(string.format("%d\t%08X\t%02X\t%02X\t%02X\n", frame,
                    checksumNametable(), emu.read(0x0304, emu.memType.nesDebug),
                    emu.read(0x0306, emu.memType.nesDebug), value))
                log:close()
                buildingProbeLogLast = frame
            end
            buildingProbeFrame = buildingProbeFrame + 1
            emu.setInput(decode(value), 0)
            return
        end
        if frontierProbeHash ~= 0 and checksumNametable() == frontierProbeHash
            and (frontierProbeAnyPosition
                or (emu.read(0x0304, emu.memType.nesDebug) == frontierProbeX
                    and emu.read(0x0306, emu.memType.nesDebug) == frontierProbeY))
            and frontierProbeFrame < frontierProbeBudget * (frontierProbeAll and 4 or 1) then
            local directions = {0x10, 0x80, 0x20, 0x40}
            local probeIndex = frontierProbeDirection
            if frontierProbeAll then
                probeIndex = (math.floor(frontierProbeFrame / frontierProbeBudget) % 4) + 1
            end
            local value = directions[probeIndex] or 0x40
            if frontierProbeFrame < frontierProbeDelay then value = 0 end
            if frontierProbeSequence == 1 then
                value = frontierProbeFrame < frontierProbeDelay + 480 and 0x40 or 0x10
            end
            if frontierProbeDiagonal then value = 0x50 end
            if frontierProbeFrame == 0 then
                frontierProbeActivated = true
                if frontierProbeExtendOnActivation then
                    EXPLORATION_BUDGET = EXPLORATION_BUDGET + frontierProbeExtensionFrames
                end
                frontierCaptureDelay = 45
                writeText("frontier_probe_activation.tsv", string.format(
                    "%d\t%08X\t%02X\t%02X\n", frame, frontierProbeHash,
                    emu.read(0x0304, emu.memType.nesDebug),
                    emu.read(0x0306, emu.memType.nesDebug)))
            end
            if frontierProbeFrame % 30 < 15 then value = value | 0x01 end
            frontierProbeFrame = frontierProbeFrame + 1
            if frontierProbeFrame >= frontierProbeBudget * (frontierProbeAll and 4 or 1) then
                frontierProbeCompleted = true
            end
            emu.setInput(decode(value), 0)
            return
        end
        if menuHash ~= 0 and checksumNametable() == menuHash
            and (menuRecoveryMaxFrames == 0 or menuRecoveryFrame < menuRecoveryMaxFrames) then
            menuRecoveries = menuRecoveries + 1
            local button = (menuRecoveryFrame % menuRecoveryPeriod) < menuRecoveryHold
                and menuRecoveryButton or 0x00
            menuRecoveryFrame = menuRecoveryFrame + 1
            if menuRecoveryMaxFrames > 0 and menuRecoveryFrame >= menuRecoveryMaxFrames then
                menuRecoveryTimedOut = true
                writeBinary("menu_timeout_screen.png", emu.takeScreenshot())
                writeText("menu_recovery_timeout.tsv", string.format(
                    "frame\thash\trecoveries\n%d\t%08X\t%d\n", frame,
                    checksumNametable(), menuRecoveries))
                if stopOnMenuTimeout then
                    terminationReason = "menu-timeout"
                    writeSummary()
                    writeGraph()
                    writeFrontier()
                    print("POKEMON_CAMPAIGN_EXPLORER_MENU_TIMEOUT_PASS")
                    print("POKEMON_MESEN_PASS")
                    emu.stop(0)
                    return
                end
            end
            emu.setInput(decode(button), 0)
            return
        end
        if buildingEntered and (checksumNametable() == 0x68EAC002
            or (interiorConfirmHold and interiorConfirmHash ~= 0
                and checksumNametable() == interiorConfirmHash))
            and interiorHoldFrame < interiorHoldBudget then
            local value = interiorHoldFrame % 60 < 8 and 0x01 or 0x00
            if interiorConfirmActionSweep and interiorConfirmHash ~= 0
                and checksumNametable() == interiorConfirmHash
                and interiorHoldFrame % interiorConfirmActionPeriod < 8 then
                local actionCount = interiorConfirmMoveSweep and 4
                    or (interiorConfirmIncludeMenu and 4 or 2)
                local action = math.floor(interiorHoldFrame / interiorConfirmActionPeriod) % actionCount
                value = interiorConfirmMoveSweep
                    and ({0x11, 0x41, 0x81, 0x11})[action + 1]
                    or (interiorConfirmIncludeMenu
                    and ({0x01, 0x02, 0x08, 0x04})[action + 1]
                    or ({0x01, 0x02})[action + 1])
            end
            interiorHoldFrame = interiorHoldFrame + 1
            emu.setInput(decode(value), 0)
            return
        end
        if outdoorDoorGuide and exteriorReached
            and outdoorDoorGuideFrame < outdoorDoorGuideBudget
        then
            local mapHash = checksumNametable()
            local x = emu.read(0x0304, emu.memType.nesDebug)
            local y = emu.read(0x0306, emu.memType.nesDebug)
            -- After leaving the house, the verified outdoor route places the
            -- player on the central path near x=0x80,y=0x70. Walk left to
            -- the blue-house doorway and pulse A to enter it. Do not run
            -- this waypoint on the known indoor house map.
            if mapHash ~= 0xCFF1898C and y >= 0x50 and y <= 0x90
                and x >= 0x20 and x <= 0xA0 then
                local value = x > 0x28 and 0x40 or 0x01
                if outdoorDoorGuideFrame % 30 < 8 then value = value | 0x01 end
                outdoorDoorGuideFrame = outdoorDoorGuideFrame + 1
                emu.setInput(decode(value), 0)
                return
            end
        end
        if interiorDoorProbe and buildingEntered and checksumNametable() == 0x68EAC002
            and interiorDoorProbeFrame < 2400 then
            -- Probe the transition with A alone, then each direction while
            -- pulsing A. This distinguishes an interactable door/PNJ from a
            -- one-frame map transition without assuming a room layout.
            local phase = math.floor(interiorDoorProbeFrame / 480)
            local route = {0x00, 0x80, 0x20, 0x40, 0x10}
            local value = route[phase + 1] or 0x10
            if phase > 0 and interiorDoorProbeFrame % 30 < interiorActionPulse then
                value = value | 0x01
            end
            interiorDoorProbeFrame = interiorDoorProbeFrame + 1
            emu.setInput(decode(value), 0)
            return
        end
        if buildingEntered and (checksumNametable() == 0x68EAC002
            or (interiorConfirmHash ~= 0 and checksumNametable() == interiorConfirmHash))
            and interiorSweepFrame < interiorSweepSegment * 4 then
            local route = {0x80, 0x20, 0x40, 0x10}
            local value = route[math.floor(interiorSweepFrame / interiorSweepSegment) + 1] or 0x10
            if interiorSweepFrame % 30 < interiorActionPulse then value = value | 0x01 end
            interiorSweepFrame = interiorSweepFrame + 1
            emu.setInput(decode(value), 0)
            return
        end
        local currentContextHash = checksumContextRam()
        if (dojoHash ~= 0 and checksumNametable() == dojoHash)
            or (dojoContextHash ~= 0 and currentContextHash == dojoContextHash) then
            local dojoPhase = math.floor((interiorSweepFrame % 1500) / 300)
            local dojoRoute = {0x20, 0x40, 0x20, 0x80, 0x10}
            local value = dojoRoute[dojoPhase + 1] or 0x10
            if interiorSweepFrame % 30 < interiorActionPulse then value = value | 0x01 end
            interiorSweepFrame = interiorSweepFrame + 1
            emu.setInput(decode(value), 0)
            return
        end
        if buildingCorridorGuide and exteriorReached and buildingCorridorFrame < 1200
            and checksumNametable() == 0x786B14C0 then
            local value = buildingCorridorFrame < 600 and 0x40 or 0x20
            if buildingCorridorFrame % 30 < 8 then value = value | 0x01 end
            buildingCorridorFrame = buildingCorridorFrame + 1
            emu.setInput(decode(value), 0)
            return
        end
        if exteriorGuide and exteriorReached and exteriorGuideFrame < exteriorSweepHold * 4 then
            local phase = math.floor(exteriorGuideFrame / exteriorSweepHold)
            local route = {0x20, 0x40, 0x20, 0x80}
            local routeIndex = ((phase + exteriorRouteOffset) % #route) + 1
            local value = route[routeIndex] or 0x20
            if exteriorGuideFrame % exteriorActionPeriod < 3 then value = value | 0x01 end
            exteriorGuideFrame = exteriorGuideFrame + 1
            emu.setInput(decode(value), 0)
            return
        end
        if buildingProbe and exteriorReached and buildingProbeFrame < buildingProbeBudget then
            local hash = checksumNametable()
            if hash == 0x143B5DCC or (buildingProbeAllAfterInterior and interiorSeen)
                or (buildingProbeHash ~= 0 and hash == buildingProbeHash)
                or (buildingProbeHash2 ~= 0 and hash == buildingProbeHash2)
                or (buildingProbeHash3 ~= 0 and hash == buildingProbeHash3)
                or (buildingProbeHash4 ~= 0 and hash == buildingProbeHash4)
                or (buildingProbeHash5 ~= 0 and hash == buildingProbeHash5)
                or hash == 0xD0922056 then
                if buildingProbeHash2 ~= 0 and hash == buildingProbeHash2 then
                    -- A configured target hash is the doorway itself: hold A
                    -- briefly instead of sending the probe direction away.
                    local doorValue = buildingDoorAction
                    buildingProbeFrame = buildingProbeFrame + 1
                    emu.setInput(decode(doorValue), 0)
                    return
                end
                if hash == 0x143B5DCC and buildingProbeDirection == 5 then
                    local directX = emu.read(0x0304, emu.memType.nesDebug)
                    local directY = emu.read(0x0306, emu.memType.nesDebug)
                    local targetX, targetY = buildingTargetX, buildingTargetY
                    if targetX == 0 then targetX = 128 end
                    if targetY == 0 then targetY = 112 end
                    local directValue
                    if directX < 0x40 and directY == targetY then directValue = 0x10
                    elseif directX < 0x40 and directY > buildingDetourY then directValue = 0x10
                    elseif directX < 0x40 and directY < buildingDetourY then directValue = 0x20
                    elseif directX < targetX and directY == buildingDetourY then directValue = 0x80
                    elseif directY > targetY then directValue = 0x10
                    elseif directY < targetY then directValue = 0x20
                    elseif directX >= 0x70 then directValue = buildingTerminalAction
                    elseif directY > targetY then directValue = 0x10
                    elseif directX < targetX then directValue = 0x80
                    elseif directX > targetX then directValue = 0x40
                    else directValue = 0x01 end
                    if buildingProbeFrame % 30 < 8 then directValue = directValue | 0x01 end
                    local directLog = assert(io.open(outputDirectory .. "\\building_probe.tsv", "a"))
                    directLog:write(string.format("%d\t%08X\t%02X\t%02X\t%02X\t%02X\t%02X\n", frame,
                        hash, directX, directY, directValue, targetX, targetY))
                    directLog:close()
                    buildingProbeFrame = buildingProbeFrame + 1
                    emu.setInput(decode(directValue), 0)
                    return
                end
                local probeDirections = {0x80, 0x40, 0x20, 0x10}
                local probeIndex = buildingProbeDirection
                if probeIndex == 0 then
                    probeIndex = (math.floor(buildingProbeFrame / 300) % 4) + 1
                end
                local value
                if (buildingProbeHash3 ~= 0 and checksumNametable() == buildingProbeHash3)
                    or (buildingProbeHash4 ~= 0 and checksumNametable() == buildingProbeHash4)
                    or (buildingProbeHash5 ~= 0 and checksumNametable() == buildingProbeHash5) then
                    value = 0x10 | ((buildingProbeFrame % 30) < 15 and 0x01 or 0x00)
                elseif checksumNametable() == 0xD0922056 then
                    local localPhase = math.floor((buildingProbeFrame % 240) / 60)
                    if localPhase == 0 then
                        value = 0x40
                    elseif localPhase == 1 then
                        value = 0x80
                    elseif localPhase == 2 then
                        value = 0x10 | ((buildingProbeFrame % 30) < 15 and 0x01 or 0x00)
                    else
                        value = 0x20 | ((buildingProbeFrame % 30) < 15 and 0x01 or 0x00)
                    end
                    local probeX = emu.read(0x0304, emu.memType.nesDebug)
                    local probeY = emu.read(0x0306, emu.memType.nesDebug)
                    if buildingTargetX ~= 0 and buildingTargetY ~= 0 then
                        if probeX < buildingTargetX then value = 0x80
                        elseif probeX > buildingTargetX then value = 0x40
                        elseif probeY < buildingTargetY then value = 0x20
                        elseif probeY > buildingTargetY then value = 0x10
                        else
                            local targetPhase = buildingProbeFrame % 240
                            if targetPhase < 60 then value = 0x01
                            elseif targetPhase < 90 then value = 0x20
                            elseif targetPhase < 120 then value = 0x10
                            elseif targetPhase < 180 then value = 0x01
                            elseif targetPhase < 210 then value = 0x40
                            else value = 0x80 end
                        end
                    elseif probeX >= 0x78 and probeX <= 0x84 and probeY >= 0x70 and probeY <= 0x74 then
                        value = (buildingProbeFrame % 45) < 25 and 0x01 or 0x00
                    end
                    if (value & 0x01) ~= 0 and buildingProbeFrame % 30 == 0 then
                        local candidate = assert(io.open(outputDirectory .. "\\building_interaction_candidates.tsv", "a"))
                        candidate:write(string.format("%d\t%08X\t%02X\t%02X\t%02X\n", frame,
                            checksumNametable(), emu.read(0x0304, emu.memType.nesDebug),
                            emu.read(0x0306, emu.memType.nesDebug), value))
                        candidate:close()
                        writeBinary(string.format("building_interaction_%d.png", frame), emu.takeScreenshot())
                    end
                elseif buildingProbeHash2 ~= 0 and checksumNametable() == buildingProbeHash2 then
                    value = 0x10
                    if buildingProbeFrame % 30 < 8 then value = value | 0x01 end
                elseif checksumNametable() == 0x143B5DCC
                    or (buildingProbeHash ~= 0 and checksumNametable() == buildingProbeHash)
                    or (buildingProbeHash2 ~= 0 and checksumNametable() == buildingProbeHash2) then
                    if buildingProbeDirection == 3 then
                        value = buildingProbeFrame < buildingApproachFrames and 0x20
                            or (buildingProbeFrame < buildingApproachFrames + buildingApproachTurnFrames and 0x80 or 0x10)
                    elseif buildingProbeDirection == 4 then
                        value = buildingProbeFrame < buildingApproachFrames and 0x10
                            or (buildingProbeFrame < buildingApproachFrames + buildingApproachTurnFrames and 0x80 or 0x20)
                    else
                        value = buildingProbeFrame < buildingApproachFrames and 0x80
                            or (buildingProbeFrame < buildingApproachFrames + buildingApproachTurnFrames and 0x10 or 0x80)
                    end
                else
                    value = probeDirections[probeIndex] or 0x80
                end
                if hash == 0x143B5DCC and buildingTargetX ~= 0 and buildingTargetY ~= 0 then
                    local probeX = emu.read(0x0304, emu.memType.nesDebug)
                    local probeY = emu.read(0x0306, emu.memType.nesDebug)
                    if probeY < buildingTargetY then value = 0x20
                    elseif probeY > buildingTargetY then value = 0x10
                    elseif probeX < buildingTargetX then value = 0x80
                    elseif probeX > buildingTargetX then value = 0x40
                    else value = 0x01 end
                end
                if buildingProbeFrame % 30 < 8 then value = value | 0x01 end
                if frame - buildingProbeLogLast >= 30 then
                    local log = assert(io.open(outputDirectory .. "\\building_probe.tsv", "a"))
                    log:write(string.format("%d\t%08X\t%02X\t%02X\t%02X\n", frame,
                        checksumNametable(), emu.read(0x0304, emu.memType.nesDebug),
                        emu.read(0x0306, emu.memType.nesDebug), value))
                    log:close()
                    buildingProbeLogLast = frame
                end
                buildingProbeFrame = buildingProbeFrame + 1
                emu.setInput(decode(value), 0)
                return
            end
        end
        if houseGuide and houseGuideFrame < houseGuideBudget then
            local x = emu.read(0x0304, emu.memType.nesDebug)
            local y = emu.read(0x0306, emu.memType.nesDebug)
            -- From the verified bedroom spawn, route to the right-side
            -- stair/door corridor before handing control to the explorer.
            local value = x < 0xBC and 0x80
                or (y > 0x74 and 0x10)
                or (x > 0xC2 and 0x40)
                or 0x20
            if houseGuideFrame % 120 < 3 then value = value | 0x01 end
            emu.setInput(decode(value), 0)
            return
        end
        if downstairsGuide then
            local hash = checksumNametable()
            if hash == 0xCFF1898C then
                if downstairsGuideFrame < 0 then downstairsGuideFrame = 0 end
            end
            if hash == 0xCFF1898C and downstairsGuideFrame >= 0 and downstairsGuideFrame < 1200 then
                local phaseIndex = math.floor(downstairsGuideFrame / 240) + 1
                local routes = {
                    {0x20, 0x40, 0x80, 0x20},
                    {0x40, 0x20, 0x80, 0x20},
                    {0x20, 0x80, 0x40, 0x20},
                }
                local route = routes[downstairsRoute] or routes[1]
                local phase = route[phaseIndex] or 0x20
                if downstairsGuideFrame % 120 < 3 then phase = phase | 0x01 end
                emu.setInput(decode(phase), 0)
                return
            end
        end
        if transitionSeed then
            local hash = checksumNametable()
            local x = emu.read(0x0304, emu.memType.nesDebug)
            local y = emu.read(0x0306, emu.memType.nesDebug)
            if hash == 0xCEC7D05A and x >= 0xB8 and x <= 0xC8
                and y >= 0x50 and y <= 0x70
            then
                if transitionSeedFrame < 0 then transitionSeedFrame = 0 end
                if transitionSeedFrame < 240 then
                    emu.setInput(decode(0x40), 0)
                    return
                end
            end
        end
        if startupAFrames > 0 then
            emu.setInput(decode(0x01), 0)
            return
        end
        if guidedFrame > 0 then
            local value = string.byte(opening, guidedStart + guidedFrame) or 0
            emu.setInput(decode(value), 0)
            return
        end
        if movePhase == "move" and moveDirection then
            value = directions[moveDirection].value
            if blockedEdgeProbe and blockedEdgeProbeFrame > 0 then
                local opposite = directions[moveDirection].opposite
                if blockedEdgeProbeFrame <= 30 then
                    value = opposite
                elseif blockedEdgeProbeFrame <= 60 then
                    value = directions[moveDirection].value | 0x01
                else
                    blockedEdgeProbeFrame = 0
                end
                if blockedEdgeProbeFrame > 0 then
                    blockedEdgeProbeFrame = blockedEdgeProbeFrame + 1
                end
            end
            if moveFrame % 90 < 3 then value = value | 0x01 end
            if moveActionSweep and moveFrame % moveActionPeriod < 4 then
                local action = math.floor(moveFrame / moveActionPeriod) % 4
                if action == 0 then value = value | 0x01
                elseif action == 1 then value = value | 0x02
                elseif action == 2 then value = value | 0x08
                else value = value | 0x04 end
            end
        elseif movePhase == "backtrack" and moveDirection then
            value = directions[moveDirection].opposite
        elseif genericActionPeriod > 0 and frame % genericActionPeriod < 4 then value = 0x01
        elseif genericActionPeriod > 0 and frame % genericActionPeriod >= math.floor(genericActionPeriod / 2)
            and frame % genericActionPeriod < math.floor(genericActionPeriod / 2) + 4 then value = 0x02 end
        local x = emu.read(0x0304, emu.memType.nesDebug)
        local y = emu.read(0x0306, emu.memType.nesDebug)
        if (x <= 0x20 or x >= 0xD0 or y <= 0x20 or y >= 0xD0)
            and frame % 120 < 3
        then
            value = value | 0x01
        end
    end
    emu.setInput(decode(value), 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frame = frame + 1
    if interiorCaptureDelay >= 0 then
        if interiorCaptureDelay == 0 and not interiorEntryCaptured then
            writeBinary("interior_entry_screen.png", emu.takeScreenshot())
            if lastExteriorVisualHash ~= nil and visualHash() ~= lastExteriorVisualHash then
                buildingEntered = true
                interiorVisualSeen = true
            end
            interiorEntryCaptured = true
        end
        interiorCaptureDelay = interiorCaptureDelay - 1
    end
    if frontierCaptureDelay >= 0 then
        if frontierCaptureDelay == 0 then
            writeBinary(string.format("frontier_probe_%08X_%d.png", frontierProbeHash, frame), emu.takeScreenshot())
            frontierCaptureDelay = -1
        else
            frontierCaptureDelay = frontierCaptureDelay - 1
        end
    end
    if houseGuide and houseGuideFrame < houseGuideBudget then
        houseGuideFrame = houseGuideFrame + 1
    end
    if downstairsGuide and downstairsGuideFrame >= 0 and downstairsGuideFrame < 1200 then
        downstairsGuideFrame = downstairsGuideFrame + 1
    end
    if transitionSeed and transitionSeedFrame >= 0 and transitionSeedFrame < 240 then
        transitionSeedFrame = transitionSeedFrame + 1
    end
    if frame < EXPLORATION_START then
            return
        end
        if battleCooldown > 0 then battleCooldown = battleCooldown - 1 end
        if battleMode then
            -- Keep advancing battle menus/turns instead of sending movement
            -- input while the battle detector is active. Screenshots and PC
            -- events remain the authoritative evidence of a real battle.
            local battleButton = battleActionButton
            if battleAlternateButton ~= 0
                and math.floor(battleFrame / battleActionPeriod) % 2 == 1 then
                battleButton = battleAlternateButton
            end
            emu.setInput(decode((battleFrame % battleActionPeriod) < battleActionHold
                and battleButton or 0x00), 0)
            battleFrame = battleFrame + 1
            if battleMaxFrames > 0 and battleFrame >= battleMaxFrames then
                logBattle("timeout", emu.getState()["cpu.pc"] or 0)
                battleMode = false
                battleQuietFrames = 0
                battleFrame = 0
                battleCooldown = battleCooldownLength
                stableFrames = 0
            end
            return
        end
        if recoveryIndex > 0 then
            local value = recoveryRoute[recoveryIndex]
            if recoveryFrame % 60 < 4 then value = value | 0x01 end
            if recoveryActionSweep and recoveryFrame % recoveryActionPeriod < 4 then
                -- Probe interaction/menu transitions without altering RAM. The
                -- four buttons are rotated at each recovery leg so a doorway
                -- or NPC requiring a non-A action can be discovered.
                local action = (math.floor(recoveryFrame / recoveryActionPeriod) + recoveryIndex) % 4
                value = value & 0xF0
                if action == 0 then value = value | 0x01       -- A
                elseif action == 1 then value = value | 0x02   -- B
                elseif action == 2 then value = value | 0x08   -- Start
                else value = value | 0x04 end                 -- Select
            end
            emu.setInput(decode(value), 0)
            recoveryFrame = recoveryFrame + 1
            if recoveryFrame >= recoveryHold then
                recoveryFrame = 0
                recoveryIndex = recoveryIndex + 1
                if recoveryIndex > #recoveryRoute then recoveryIndex = 0 end
            end
            return
        end
        if startupAFrames > 0 then
        startupAFrames = startupAFrames + 1
        if startupAFrames > 20 then startupAFrames = 0 end
    end
    if frame == EXPLORATION_START then
        phase = "exploration"
        actionFrame = 0
        writeText("exploration.tsv", "capture frame phase action hash x y\n")
        writeText("exploration_edges.tsv", "from\tdirection\tto\tmoved\n")
        writeText("battles.tsv", "event\tframe\tx\ty\tpc\n")
        writeText("battle_config.tsv", string.format(
            "field\tvalue\nperiod\t%d\nhold\t%d\nbutton\t%02X\nalternate_button\t%02X\nmax_frames\t%d\ncooldown_frames\t%d\n",
            battleActionPeriod, battleActionHold, battleActionButton, battleAlternateButton,
            battleMaxFrames, battleCooldownLength))
        writeText("map_transitions.tsv", "frame\tfrom_hash\tto_hash\tx\ty\n")
        writeText("map_context.tsv", "frame\tfrom_hash\tto_hash\tcontext_hash\n")
        writeText("interior_diagnostics.tsv", "frame\tfrom_hash\tto_hash\tcontext_hash\tx\ty\tpc\n")
        writeText("route_checkpoints.tsv", "frame\tnode\troute_offset\tdirection_cursor\tstagnant_frames\tdetour_y\n")
        writeText("exploration_checkpoint.tsv", "frame\tcaptures\tmoved_edges\tblocked_edges\tstagnant_frames\n")
        writeText("recovery.tsv", "frame\tnode\tmap_hash\tstart_direction\thold_frames\n")
        if tracePc then writeText("pc_trace.tsv", "frame\tpc\thash\n") end
    end
    if phase ~= "exploration" then
        return
    end
    if checkpointPeriod > 0 and frame % checkpointPeriod == 0 then
        writeGraph()
        writeFrontier()
        local checkpoint = assert(io.open(outputDirectory .. "\\exploration_checkpoint.tsv", "a"))
        checkpoint:write(string.format("%d\t%d\t%d\t%d\t%d\n", frame, captures,
            movedEdges, blockedEdges, stagnantFrames))
        checkpoint:close()
    end
    actionFrame = actionFrame + 1
    if tracePc and frame % 60 == 0 then
        local pcFile = assert(io.open(outputDirectory .. "\\pc_trace.tsv", "a"))
        pcFile:write(string.format("%d\t%04X\t%08X\n", frame,
            emu.getState()["cpu.pc"] or 0, checksumNametable()))
        pcFile:close()
    end
    if captures == lastCaptureCount then stagnantFrames = stagnantFrames + 1
    else stagnantFrames = 0; lastCaptureCount = captures end
    if stagnantFrames >= 1200 and currentNode and nodes[currentNode] then
        local checkpoint = assert(io.open(outputDirectory .. "\\route_checkpoints.tsv", "a"))
        checkpoint:write(string.format("%d\t%s\t%d\t%d\t%d\t%02X\n", frame, currentNode,
            exteriorRouteOffset, directionCursor, stagnantFrames, buildingDetourY))
        checkpoint:close()
        nodes[currentNode].tried = {}
        directionCursor = (directionCursor % #directions) + 1
        if exteriorReached and not lockRouteOffset then
            exteriorRouteOffset = (exteriorRouteOffset + 1) % 4
            exteriorGuideFrame = 0
        end
        if buildingProbeDirection == 5 then
            local previousDetour = buildingDetourY
            buildingDetourY = (buildingDetourY == 0x40) and 0xA0 or 0x40
            if previousDetour == 0xA0 and not lockRouteOffset then
                -- Both coordinate lanes failed: let the generic frontier
                -- explorer search lateral openings around the obstacle.
                buildingProbeDirection = 0
            end
            buildingProbeFrame = 0
        end
        movePhase = "settle"
        stagnantFrames = 0
        frontierExhausted = false
        stagnationResets = stagnationResets + 1
        recoveryIndex = 1
        recoveryFrame = 0
        local recoveryHash = checksumNametable()
        recoveryMapCounts[recoveryHash] = (recoveryMapCounts[recoveryHash] or 0) + 1
        if recoveryMapCounts[recoveryHash] > 1 and not lockRouteOffset then
            -- Rotate the opening direction on repeated failures of the same
            -- map. This explores all four approaches without another profile.
            recoveryIndex = ((recoveryMapCounts[recoveryHash] - 1) % #recoveryRoute) + 1
        elseif recoverySpecialHash ~= 0 and recoveryHash == recoverySpecialHash
            and recoverySpecialStart >= 1 and recoverySpecialStart <= #recoveryRoute
        then
            recoveryIndex = recoverySpecialStart
        end
        local recoveryFile = assert(io.open(outputDirectory .. "\\recovery.tsv", "a"))
        recoveryFile:write(string.format("%d\t%s\t%08X\t%d\t%d\n", frame,
            currentNode or "", recoveryHash, recoveryIndex, recoveryHold))
        recoveryFile:close()
    end
    local pc = emu.getState()["cpu.pc"] or 0
    if eventPcMin ~= 0 and eventPcMax ~= 0 and pc >= eventPcMin and pc <= eventPcMax then
        emu.setInput(decode((frame % 30) < 12 and 0x01 or 0x00), 0)
        return
    end
    if battleCooldown == 0 and ((battleHash ~= 0 and checksumNametable() == battleHash)
        or (pc >= battlePcMin and pc <= battlePcMax)) then
        if not battleMode and not battleStopTriggered then
            battleCount = battleCount + 1
            logBattle("start", pc)
            battleCaptureCount = battleCaptureCount + 1
            writeBinary(string.format("battle_%03d_%d.png", battleCaptureCount, frame), emu.takeScreenshot())
            if stopOnBattle then
                terminationReason = "battle"
                battleStopTriggered = true
                battleMode = true
                if interiorConfirmHash ~= 0 and checksumNametable() == interiorConfirmHash then
                    buildingEntered = true
                    interiorSeen = true
                    interiorVisualSeen = true
                end
                writeSummary()
                writeGraph()
                writeFrontier()
                local mapCountBattle = 0
                for _ in pairs(mapHashes) do mapCountBattle = mapCountBattle + 1 end
                print(string.format(
                    "POKEMON_CAMPAIGN_EXPLORER_PASS mapper=163 region=%s " ..
                    "frames=%d uniqueSignatures=%d captures=%d movedEdges=%d " ..
                    "blockedEdges=%d mapHashes=%d battles=%d",
                    tostring(emu.getState()["region"]), frame, captures, captures,
                    movedEdges, blockedEdges, mapCountBattle, battleCount))
                print("POKEMON_MESEN_PASS")
                emu.stop(0)
                return
            end
        end
        battleMode = true
        battleFrame = 0
        battleQuietFrames = 0
        movePhase = "settle"
    elseif battleMode then
        battleQuietFrames = battleQuietFrames + 1
        if battleQuietFrames >= 90 then
            logBattle("end", pc)
            battleMode = false
            battleQuietFrames = 0
            battleFrame = 0
            battleCooldown = battleCooldownLength
            stableFrames = 0
        end
    end
    if guidedFrame > 0 then
        guidedFrame = guidedFrame + 1
        if guidedFrame > GUIDED_LENGTH then guidedFrame = 0 end
    elseif actionFrame > 0 and actionFrame % GUIDED_EVERY == 0
        and guidedStart + GUIDED_LENGTH < #opening
    then
        guidedStart = guidedStart + GUIDED_LENGTH
        guidedFrame = 1
        movePhase = "settle"
    end
    if routeIndex <= #bridge then
        routeFrame = routeFrame + 1
        if routeFrame >= bridge[routeIndex].frames then
            routeIndex = routeIndex + 1
            routeFrame = 0
        end
        captureIfNew()
        return
    end
    local key, _, currentX, currentY = captureIfNew()
    if movePhase == "settle" and stableFrames >= SETTLE_FRAMES then
        if not currentNode then
            currentNode = key; nodes[key] = {tried = {}, x = currentX, y = currentY}
        end
        local node = nodes[currentNode]
        local nextDirection = chooseNextDirection(node)
        if nextDirection then
            actionIndex = nextDirection; moveDirection = nextDirection
            moveFrom = currentNode; moveStartKey = key
            movePhase = "move"; moveFrame = 0
        else
            if node.parent and node.parentDirection then
                movePhase = "backtrack"; moveFrame = 0
                moveDirection = node.parentDirection
                currentNode = node.parent
            else
                if exteriorReached then
                    -- A screen edge or camera scroll can make the local DFS
                    -- frontier empty without exhausting the outdoor map.
                    -- Rotate the seed direction and keep searching.
                    node.tried = {}
                    directionCursor = (directionCursor % #directions) + 1
                    movePhase = "settle"; moveFrame = 0
                    frontierExhausted = false
                else
                    movePhase = "done"
                    frontierExhausted = true
                end
            end
        end
    elseif movePhase == "move" then
        moveFrame = moveFrame + 1
        local holdLimit = startupMove and startupHold or adaptiveHold
        local edgeX = emu.read(0x0304, emu.memType.nesDebug)
        local edgeY = emu.read(0x0306, emu.memType.nesDebug)
        local outward = (edgeX <= 0x20 and moveDirection == 4)
            or (edgeX >= 0xD0 and moveDirection == 2)
            or (edgeY <= 0x20 and moveDirection == 1)
            or (edgeY >= 0xD0 and moveDirection == 3)
        if outward and not startupMove then holdLimit = EDGE_HOLD_FRAMES end
        if moveFrame >= holdLimit then
            local toKey, _, toX, toY = captureIfNew()
            local moved = toKey ~= moveStartKey
            appendEdge(moveFrom, directions[moveDirection].name, toKey, moved)
            if moved then
                consecutiveBlocked = 0
                adaptiveHold = MOVE_HOLD_FRAMES
            else
                consecutiveBlocked = consecutiveBlocked + 1
                if blockedEdgeProbe and consecutiveBlocked >= 1 then
                    blockedEdgeProbeDirection = moveDirection
                    blockedEdgeProbeFrame = 1
                end
                if consecutiveBlocked >= 3 then
                    adaptiveHold = 30
                    local retryNode = nodes[moveFrom]
                    if retryNode then
                        retryNode.retries = retryNode.retries or {}
                        local retryCount = retryNode.retries[moveDirection] or 0
                        if retryCount < 1 then
                            retryNode.retries[moveDirection] = retryCount + 1
                            retryNode.tried[moveDirection] = nil
                        end
                    end
                end
            end
            if moved and not nodes[toKey] then
                nodes[toKey] = {tried = {}, parent = moveFrom, parentDirection = moveDirection, x = toX, y = toY}
            end
            currentNode = toKey
            startupMove = false
            if startupIndex > #startupSequence and startupAFrames == 0 then
                startupAFrames = 1
            end
            movePhase = "settle"; moveFrame = 0
        end
    elseif movePhase == "backtrack" then
        moveFrame = moveFrame + 1
        if moveFrame >= MOVE_HOLD_FRAMES then movePhase = "settle"; moveFrame = 0 end
    end
    if frame >= EXPLORATION_START + EXPLORATION_BUDGET then
        writeSummary()
        writeGraph()
        writeFrontier()
        local mapCount = 0
        for _ in pairs(mapHashes) do mapCount = mapCount + 1 end
        print(string.format(
            "POKEMON_CAMPAIGN_EXPLORER_PASS mapper=163 region=%s " ..
            "frames=%d uniqueSignatures=%d captures=%d movedEdges=%d " ..
            "blockedEdges=%d mapHashes=%d battles=%d",
            tostring(emu.getState()["region"]), frame, captures, captures,
            movedEdges, blockedEdges, mapCount, battleCount
        ))
        print("POKEMON_MESEN_PASS")
        emu.stop(0)
    end
    if frame % 1000 == 0 then writeSummary(); writeGraph(); writeFrontier() end
end, emu.eventType.endFrame)
