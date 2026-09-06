-- RAM-guided exploration bot for the NJ046 Pokemon Yellow mapper-163 port.
-- Replays the deterministic opening, then learns topology from RAM rather
-- than following a timed route.

local out = assert(os.getenv("POKEMON_YELLOW_MESEN_OUTPUT"))
local inputPath = assert(os.getenv("POKEMON_YELLOW_MESEN_INPUT"))
local inputFile = assert(io.open(inputPath, "rb"))
local opening = inputFile:read("*a")
inputFile:close()

local function setting(name, default)
    local raw = os.getenv(name)
    if raw == nil or raw == "" then return default end
    return tonumber(raw) or default
end

local START = setting("POKEMON_EXPLORER_START_FRAME", 4917)
local BUDGET = setting("POKEMON_EXPLORER_MAX_FRAMES", 12000)
local X_ADDR = setting("POKEMON_ROUTE_X_ADDR", 0x0304)
local Y_ADDR = setting("POKEMON_ROUTE_Y_ADDR", 0x0306)
local MAP_START = setting("POKEMON_ROUTE_MAP_RAM_START", 0x0308)
local MAP_LENGTH = math.max(1, setting("POKEMON_ROUTE_MAP_RAM_LENGTH", 4))
-- One 16-frame probe corresponds to one visible metatile in this port.  Long
-- holds can skip the narrow horizontal alignment needed by building exits.
local GRID = math.max(1, setting("POKEMON_ROUTE_GRID_SIZE", 0x10))
local PROBE_FRAMES = math.max(8, setting("POKEMON_ROUTE_PROBE_FRAMES", 16))
local SETTLE_FRAMES = math.max(2, setting("POKEMON_ROUTE_SETTLE_FRAMES", 10))
local ACTION_FRAMES = math.max(1, setting("POKEMON_ROUTE_ACTION_FRAMES", 10))
local TRANSITION_STABLE = math.max(2, setting("POKEMON_ROUTE_TRANSITION_STABLE", 8))
local TRANSITION_SETTLE = math.max(30, setting("POKEMON_ROUTE_TRANSITION_SETTLE_FRAMES", 90))
local BATTLE_ADDR = setting("POKEMON_ROUTE_BATTLE_ADDR", -1)
local BATTLE_MASK = setting("POKEMON_ROUTE_BATTLE_MASK", 0xFF)
local BATTLE_VALUE = setting("POKEMON_ROUTE_BATTLE_VALUE", 1)
local BATTLE_PC_MIN = setting("POKEMON_EXPLORER_BATTLE_PC_MIN", 0xF200)
local BATTLE_PC_MAX = setting("POKEMON_EXPLORER_BATTLE_PC_MAX", 0xF2FF)
local BATTLE_CONFIRM = math.max(2, setting("POKEMON_ROUTE_BATTLE_CONFIRM_FRAMES", 10))
local BATTLE_RELEASE = math.max(2, setting("POKEMON_ROUTE_BATTLE_RELEASE_FRAMES", 90))

local frame, command, phase, phaseFrame = 0, 0, "boot", 0
local probe, currentMap, currentRawMap, currentNode = nil, nil, nil, nil
local pendingMap, pendingMapFrames = nil, 0
local zoneEpoch, transitionCooldown = 0, 0
local nodes, nodeCount = {}, 0
local movedEdges, blockedEdges, transitions = 0, 0, 0
local battles, completedBattles = 0, 0
local battle, battleFrames = false, 0
local battleCandidateFrames, battleReleaseFrames = 0, 0
local stationaryFrames, lastX, lastY = 0, nil, nil
local lastMoveDirection, avoidDirection = nil, nil

local directions = {
    {name = "up", value = 0x10, opposite = "down"},
    {name = "right", value = 0x80, opposite = "left"},
    {name = "down", value = 0x20, opposite = "up"},
    {name = "left", value = 0x40, opposite = "right"},
}

local trace = assert(io.open(out .. "\\route_bot_trace.tsv", "w"))
local edges = assert(io.open(out .. "\\route_bot_edges.tsv", "w"))
local events = assert(io.open(out .. "\\route_bot_events.tsv", "w"))
local ramProbe = assert(io.open(out .. "\\route_bot_ram_probe.tsv", "w"))
trace:write("frame\tphase\tmap_ram\tx\ty\tpc\tcommand\tbattle\n")
edges:write("frame\tmap_ram\tfrom_x\tfrom_y\tdirection\tresult\tto_map\tto_x\tto_y\n")
events:write("frame\tevent\tmap_ram\tx\ty\tpc\tdetail\n")
ramProbe:write("frame\treason\taddress\tvalue\n")

local function write(name, data)
    local handle = assert(io.open(out .. "\\" .. name, "w"))
    handle:write(data)
    handle:close()
end

local function readRam(address)
    return emu.read(address, emu.memType.nesDebug)
end

local function controller(value)
    return {
        a = (value & 0x01) ~= 0, b = (value & 0x02) ~= 0,
        select = (value & 0x04) ~= 0, start = (value & 0x08) ~= 0,
        up = (value & 0x10) ~= 0, down = (value & 0x20) ~= 0,
        left = (value & 0x40) ~= 0, right = (value & 0x80) ~= 0,
    }
end

local function mapRamKey()
    local values = {}
    for offset = 0, MAP_LENGTH - 1 do
        values[#values + 1] = string.format("%02X", readRam(MAP_START + offset))
    end
    return table.concat(values, "")
end

local function quantize(value)
    return math.floor(value / GRID) * GRID
end

local function nodeKey(mapKey, x, y)
    return string.format("%s:%02X:%02X", mapKey, quantize(x), quantize(y))
end

local function getNode(mapKey, x, y, parentDirection)
    local key = nodeKey(mapKey, x, y)
    local created = false
    if nodes[key] == nil then
        nodes[key] = {
            key = key, tried = {}, blocked = {}, traversals = {},
            x = x, y = y, map = mapKey, parent = parentDirection,
        }
        nodeCount = nodeCount + 1
        created = true
        events:write(string.format("%d\tnode\t%s\t%02X\t%02X\t0000\t%s\n",
            frame, mapKey, x, y, key))
    end
    return nodes[key], created
end

local function dumpRam(reason)
    for address = 0x0300, 0x033F do
        ramProbe:write(string.format("%d\t%s\t%04X\t%02X\n",
            frame, reason, address, readRam(address)))
    end
    ramProbe:flush()
end

local function markTransition(reason, rawMap, x, y, pc)
    if transitionCooldown > 0 then return end
    local previous = currentMap or ""
    zoneEpoch = zoneEpoch + 1
    currentRawMap = rawMap
    currentMap = string.format("%s@%d", rawMap, zoneEpoch)
    transitions = transitions + 1
    transitionCooldown = TRANSITION_SETTLE
    avoidDirection = lastMoveDirection
    if probe ~= nil then probe.transitionSeen = true end
    events:write(string.format("%d\ttransition\t%s\t%02X\t%02X\t%04X\t%s:%s_to_%s\n",
        frame, currentMap, x, y, pc, reason, previous, currentMap))
    events:flush()
    dumpRam("transition_" .. reason)
    probe = nil
    phase, phaseFrame, command = "transition_settle", 0, 0
end

local function chooseDirection(node)
    for _, direction in ipairs(directions) do
        if not node.tried[direction.name] then return direction end
    end
    if node.parent and not node.blocked[node.parent] then
        for _, direction in ipairs(directions) do
            if direction.name == node.parent then return direction end
        end
    end
    local best, bestCount = nil, math.huge
    for _, candidate in ipairs(directions) do
        local count = node.traversals[candidate.name] or 0
        if not node.blocked[candidate.name] and count < bestCount then
            best, bestCount = candidate, count
        end
    end
    if best == nil then best = directions[(nodeCount % #directions) + 1] end
    return best
end

local function startProbe()
    local x, y = readRam(X_ADDR), readRam(Y_ADDR)
    currentNode = getNode(currentMap, x, y)
    if avoidDirection ~= nil then
        currentNode.tried[avoidDirection] = true
        avoidDirection = nil
    end
    local direction = chooseDirection(currentNode)
    currentNode.tried[direction.name] = true
    currentNode.traversals[direction.name] = (currentNode.traversals[direction.name] or 0) + 1
    probe = {direction = direction, map = currentMap, x = x, y = y, node = currentNode}
    phase, phaseFrame = "probe", 0
end

local function beginSettle(nextPhase)
    phase, phaseFrame, command = nextPhase or "settle", 0, 0
end

local function recordProbe(allowInteraction)
    local x, y = readRam(X_ADDR), readRam(Y_ADDR)
    local transitioned = currentMap ~= probe.map
    local moved = x ~= probe.x or y ~= probe.y
    local result = transitioned and "transition" or (moved and "moved" or "blocked")
    edges:write(string.format("%d\t%s\t%02X\t%02X\t%s\t%s\t%s\t%02X\t%02X\n",
        frame, probe.map, probe.x, probe.y, probe.direction.name, result, currentMap, x, y))
    edges:flush()
    if transitioned then
        if not probe.transitionSeen then
            markTransition("probe", mapRamKey(), x, y, pcValue())
        end
        movedEdges = movedEdges + 1
    elseif moved then movedEdges = movedEdges + 1
    else
        blockedEdges = blockedEdges + 1
        probe.node.blocked[probe.direction.name] = true
    end
    local destination, created = getNode(
        currentMap, x, y, (moved or transitioned) and probe.direction.opposite or nil)
    if moved or transitioned then
        lastMoveDirection = probe.direction.name
        destination.tried[probe.direction.opposite] = true
        destination.traversals[probe.direction.opposite] =
            (destination.traversals[probe.direction.opposite] or 0) + 1
    end
    currentNode = destination
    if not moved and not transitioned and allowInteraction then
        phase, phaseFrame = "interact", 0
    else
        probe = nil
        beginSettle("settle")
    end
end

local function pcValue()
    return emu.getState()["cpu.pc"] or 0
end

local function rawBattleSignal(pc)
    if BATTLE_ADDR >= 0 then
        return (readRam(BATTLE_ADDR) & BATTLE_MASK) == BATTLE_VALUE, "ram"
    end
    return pc >= BATTLE_PC_MIN and pc <= BATTLE_PC_MAX and stationaryFrames >= BATTLE_CONFIRM,
        "pc_stationary_fallback"
end

local function updateBattle(pc, x, y)
    if lastX ~= nil and not battle and transitionCooldown == 0
        and (math.abs(x - lastX) > GRID * 2 or math.abs(y - lastY) > GRID * 2) then
        markTransition("coordinate_warp", mapRamKey(), x, y, pc)
    end
    if lastX == x and lastY == y then stationaryFrames = stationaryFrames + 1
    else stationaryFrames = 0 end
    lastX, lastY = x, y
    local signal, detector = rawBattleSignal(pc)
    if not battle then
        battleCandidateFrames = signal and (battleCandidateFrames + 1) or 0
        if battleCandidateFrames >= BATTLE_CONFIRM then
            battle, battles, battleFrames, battleReleaseFrames = true, battles + 1, 0, 0
            events:write(string.format("%d\tbattle_start\t%s\t%02X\t%02X\t%04X\t%s\n",
                frame, currentMap or "", x, y, pc, detector))
            events:flush(); dumpRam("battle_start")
        end
    else
        battleFrames = battleFrames + 1
        battleReleaseFrames = signal and 0 or (battleReleaseFrames + 1)
        if battleReleaseFrames >= BATTLE_RELEASE then
            battle, completedBattles, battleCandidateFrames = false, completedBattles + 1, 0
            events:write(string.format("%d\tbattle_end\t%s\t%02X\t%02X\t%04X\tstable_release\n",
                frame, currentMap or "", x, y, pc))
            events:flush(); dumpRam("battle_end"); beginSettle("settle")
        end
    end
end

local function updateStableMap(rawMap)
    if currentRawMap == nil then
        currentRawMap = rawMap
        currentMap = string.format("%s@%d", rawMap, zoneEpoch)
        return
    end
    if rawMap == currentRawMap then pendingMap, pendingMapFrames = nil, 0
    elseif rawMap == pendingMap then
        pendingMapFrames = pendingMapFrames + 1
        if pendingMapFrames >= TRANSITION_STABLE then
            pendingMap, pendingMapFrames = nil, 0
            markTransition("context_change", rawMap, readRam(X_ADDR), readRam(Y_ADDR), pcValue())
        end
    else pendingMap, pendingMapFrames = rawMap, 1 end
end

write("route_bot_boot.tsv", "loaded\n")
write("route_bot_config.tsv", string.format(
    "start_frame\t%d\nmax_frames\t%d\nx_addr\t%04X\ny_addr\t%04X\nmap_ram_start\t%04X\nmap_ram_length\t%d\ngrid_size\t%d\nprobe_frames\t%d\nsettle_frames\t%d\nbattle_addr\t%s\nbattle_mask\t%02X\nbattle_value\t%02X\nbattle_detector\t%s\n",
    START, BUDGET, X_ADDR, Y_ADDR, MAP_START, MAP_LENGTH, GRID, PROBE_FRAMES,
    SETTLE_FRAMES, BATTLE_ADDR >= 0 and string.format("%04X", BATTLE_ADDR) or "unset",
    BATTLE_MASK, BATTLE_VALUE, BATTLE_ADDR >= 0 and "ram" or "pc_stationary_fallback"))

emu.addEventCallback(function()
    local value = frame < START and (string.byte(opening, frame + 1) or 0) or command
    emu.setInput(controller(value), 0)
    frame = frame + 1
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if frame >= START then
        local x, y, pc = readRam(X_ADDR), readRam(Y_ADDR), pcValue()
        if transitionCooldown > 0 then transitionCooldown = transitionCooldown - 1 end
        updateStableMap(mapRamKey())
        updateBattle(pc, x, y)
        if frame == START then dumpRam("exploration_start"); beginSettle("settle") end

        if battle then
            local period = battleFrames % 60
            command = period < 12 and 0x01 or ((period >= 30 and period < 38) and 0x02 or 0)
        elseif phase == "settle" then
            command, phaseFrame = 0, phaseFrame + 1
            if phaseFrame >= SETTLE_FRAMES then startProbe() end
        elseif phase == "probe" then
            command, phaseFrame = probe.direction.value, phaseFrame + 1
            if phaseFrame >= PROBE_FRAMES then beginSettle("probe_settle") end
        elseif phase == "probe_settle" then
            command, phaseFrame = 0, phaseFrame + 1
            if phaseFrame >= SETTLE_FRAMES then recordProbe(true) end
        elseif phase == "interact" then
            command, phaseFrame = probe.direction.value | 0x01, phaseFrame + 1
            if phaseFrame >= ACTION_FRAMES then beginSettle("interact_settle") end
        elseif phase == "interact_settle" then
            command, phaseFrame = 0, phaseFrame + 1
            if phaseFrame >= SETTLE_FRAMES then recordProbe(false) end
        elseif phase == "transition_settle" then
            command, phaseFrame = 0, phaseFrame + 1
            if phaseFrame >= TRANSITION_SETTLE then beginSettle("settle") end
        end

        if frame % 120 == 0 then
            trace:write(string.format("%d\t%s\t%s\t%02X\t%02X\t%04X\t%02X\t%s\n",
                frame, phase, currentMap or "", x, y, pc, command, tostring(battle)))
            trace:flush()
        end
    end

    if frame >= START + BUDGET then
        local x, y, pc = readRam(X_ADDR), readRam(Y_ADDR), pcValue()
        local screenshot = io.open(out .. "\\route_bot_final.png", "wb")
        if screenshot then screenshot:write(emu.takeScreenshot()); screenshot:close() end
        write("route_bot_summary.tsv", string.format(
            "frames\t%d\nnodes\t%d\nmoved_edges\t%d\nblocked_edges\t%d\ntransitions\t%d\nbattles_started\t%d\nbattles_completed\t%d\nin_battle\t%s\nmap_ram\t%s\nx\t%02X\ny\t%02X\npc\t%04X\n",
            frame, nodeCount, movedEdges, blockedEdges, transitions, battles,
            completedBattles, tostring(battle), currentMap or "", x, y, pc))
        trace:close(); edges:close(); events:close(); ramProbe:close()
        print("POKEMON_ROUTE_BOT_PASS")
        emu.stop(0)
    end
end, emu.eventType.endFrame)
