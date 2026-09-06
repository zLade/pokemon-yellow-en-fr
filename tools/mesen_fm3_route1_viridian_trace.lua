-- Read-only FM3 trace from the laboratory exit through Route 1 to Viridian.
--
-- The extracted controller stream is the route reference.  State-driven mode
-- may add controller-only A/Up pulses to recover a random battle or realign a
-- map transition.  This probe never writes emulated memory, loads a state, or
-- rewinds.  Host-side artifacts contain a frame trace, full nametable
-- snapshots, screen captures, and passive PRG-read evidence for the known
-- dialogue records.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
local inputPath = os.getenv("POKEMON_YELLOW_MESEN_INPUT")
local romPath = os.getenv("POKEMON_YELLOW_MESEN_ROM")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end
if inputPath == nil or inputPath == "" then
    error("POKEMON_YELLOW_MESEN_INPUT is not set")
end
if romPath == nil or romPath == "" then
    error("POKEMON_YELLOW_MESEN_ROM is not set")
end

local function scriptDirectory()
    local source = debug.getinfo(1, "S").source or ""
    if source:sub(1, 1) == "@" then
        source = source:sub(2)
    end
    local directory = source:match("^(.*)[/\\][^/\\]+$")
    if directory == nil or directory == "" then
        error("cannot determine script directory")
    end
    return directory
end

local directory = scriptDirectory()
local separator = directory:find("\\", 1, true) and "\\" or "/"
local function loadModule(filename)
    return dofile(directory .. separator .. filename)
end

local dialogueTargets = loadModule("campaign/dialogue_targets.lua")
local extraDialogueTargets =
    rawget(_G, "POKEMON_FM3_EXTRA_DIALOGUE_TARGETS")
if type(extraDialogueTargets) == "table" then
    for _, target in ipairs(extraDialogueTargets) do
        dialogueTargets[#dialogueTargets + 1] = target
    end
end
local allowMissingDialogueTargets =
    rawget(_G, "POKEMON_FM3_ALLOW_MISSING_DIALOGUE_TARGETS") == true

local function readFile(path)
    local file = assert(io.open(path, "rb"))
    local data = file:read("*a")
    file:close()
    return data
end

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

local function fromHex(hex)
    return (string.gsub(hex, "..", function(pair)
        return string.char(tonumber(pair, 16))
    end))
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

local function decodeInput(value)
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

local function promptArrowVisible()
    local sprite = 63 * 4
    local y = emu.read(sprite, emu.memType.nesSpriteRam)
    return y >= 190 and y <= 193
        and emu.read(sprite + 1, emu.memType.nesSpriteRam) == 0xFF
        and emu.read(sprite + 3, emu.memType.nesSpriteRam) == 208
end

local function dialogueBoxVisible()
    for tableIndex = 0, 3 do
        local tableBase = 0x2000 + tableIndex * 0x400
        for row = 0, 29 do
            local rowBase = tableBase + row * 32
            for column = 0, 21 do
                if emu.read(
                    rowBase + column,
                    emu.memType.nesPpuDebug
                ) == 0xCB
                then
                    local middle = 0
                    local cursor = column + 1
                    while cursor < 31
                        and emu.read(
                            rowBase + cursor,
                            emu.memType.nesPpuDebug
                        ) == 0xCC
                    do
                        middle = middle + 1
                        cursor = cursor + 1
                    end
                    if middle >= 8
                        and cursor < 32
                        and emu.read(
                            rowBase + cursor,
                            emu.memType.nesPpuDebug
                        ) == 0xCD
                    then
                        return true
                    end
                end
            end
        end
    end
    return false
end

local TRACE_FIRST =
    rawget(_G, "POKEMON_FM3_ROUTE1_TRACE_FIRST") or 5100
local TRACE_LAST =
    rawget(_G, "POKEMON_FM3_ROUTE1_TRACE_LAST") or 7100
local CONTROL_START =
    rawget(_G, "POKEMON_FM3_ROUTE1_CONTROL_START") or 6407
local BATTLE_RECOVERY_START =
    rawget(_G, "POKEMON_FM3_ROUTE1_BATTLE_RECOVERY_START") or 6200
local STOP_FRAME =
    rawget(_G, "POKEMON_FM3_ROUTE1_STOP_FRAME") or 7108
local PASS_MARKER =
    rawget(_G, "POKEMON_FM3_ROUTE1_PASS_MARKER")
    or "POKEMON_FM3_ROUTE1_VIRIDIAN_TRACE_PASS"
local FINAL_LABEL =
    rawget(_G, "POKEMON_FM3_ROUTE1_FINAL_LABEL")
    or "40_trace_end"

if TRACE_FIRST < 0
    or BATTLE_RECOVERY_START < 0
    or CONTROL_START < 0
    or BATTLE_RECOVERY_START >= STOP_FRAME
    or CONTROL_START >= STOP_FRAME
    or TRACE_LAST < TRACE_FIRST
    or STOP_FRAME <= TRACE_LAST
    or STOP_FRAME > 43160
then
    error(string.format(
        "invalid FM3 trace/control window: first=%d last=%d " ..
            "control=%d stop=%d",
        TRACE_FIRST,
        TRACE_LAST,
        CONTROL_START,
        STOP_FRAME
    ))
end

local checkpoints = {
    [5193] = "00_outside_lab",
    [5260] = "01_pallet_east",
    [5381] = "02_pallet_north",
    [5423] = "03_pallet_turn",
    [5509] = "04_pallet_exit_approach",
    [5585] = "05_route1_entry",
    [5671] = "06_route1_lower",
    [5740] = "07_route1_lower_turn",
    [5775] = "08_route1_west",
    [5816] = "09_route1_north",
    [5849] = "10_route1_west",
    [5882] = "11_route1_north",
    [5923] = "12_route1_east",
    [5956] = "13_route1_north",
    [5973] = "14_route1_east",
    [5991] = "15_route1_north",
    [6016] = "16_route1_west",
    [6041] = "17_route1_north",
    [6090] = "18_route1_west",
    [6115] = "19_route1_north",
    [6188] = "20_route1_east",
    [6197] = "21_route1_north",
    [6240] = "22_route1_west",
    [6249] = "23_route1_north",
    [6316] = "25_sample",
    [6368] = "26_sample",
    [6425] = "27_sample",
    [6459] = "28_sample",
    [6564] = "29_sample",
    [6615] = "30_sample",
    [6701] = "31_sample",
    [6764] = "32_sample",
    [6850] = "33_sample",
    [6867] = "34_sample",
    [6937] = "35_sample",
    [6969] = "36_sample",
    [7027] = "37_sample",
    [7063] = "38_sample",
    [7100] = "39_sample",
}

local inputBytes = readFile(inputPath)
if #inputBytes ~= 43160 then
    error(
        "unexpected controller stream length: " ..
        tostring(#inputBytes)
    )
end
local rom = readFile(romPath)
if string.sub(rom, 1, 4) ~= "NES\026" then
    error("not an iNES ROM")
end

local bootstrapMode =
    rawget(_G, "POKEMON_FM3_ROUTE1_BOOTSTRAP") == true
local stateDrivenMode =
    rawget(_G, "POKEMON_FM3_ROUTE1_STATE_DRIVEN") == true
local traceActive = not bootstrapMode
local traceFinalized = false
local frame = bootstrapMode and 5192 or 0
local traceTick = 0
local currentInput = 0
local lastArrow = false
local pendingTargetStarts = {}
local battleActive = false
local battleFrames = 0
local battleRecoveryCount = 0
local overworldStableFrames = 0
local lastDirectionInput = 0
local postBattleMovementFrames = 0
local viridianAlignmentActive = false
local viridianAlignmentDone = false
local viridianAlignmentStableFrames = 0
local viridianDfsFrames = 0
local viridianDfsNodeCount = 0
local viridianDfsStack = {}
local viridianDfsVisited = {}
local viridianDfsAction = nil
local viridianDfsStarted = false
local viridianTargetStage = nil
local viridianTargetSteps = 0
local viridianDialogueVisible = false
local lastViridianDialogueVisible = false
local viridianDialogueDismissCount = 0
local campaignDialogueDismissCount = 0
local lastCampaignDialogueVisible = false
local parcelRouteEnabled =
    rawget(_G, "POKEMON_FM3_PARCEL_ROUTE") == true
local parcelRouteActive = false
local parcelRouteDone = false
local parcelRouteTick = 0
local PARCEL_SHOP_NAMETABLE = 0x389CD31A
local PARCEL_ROUTE = {
    { frames = 40, input = 0x20 },
    { frames = 8, input = 0x00 },
    { frames = 104, input = 0x40 },
    { frames = 8, input = 0x00 },
    { frames = 40, input = 0x20 },
    { frames = 8, input = 0x00 },
    { frames = 32, input = 0x10 },
    { frames = 8, input = 0x00 },
    { frames = 2, input = 0x01 },
    { frames = 18, input = 0x00 },
}
local VIRIDIAN_CITY_NAMETABLE = 0x4E5109FA
local VIRIDIAN_DFS_MAX_NODES = 128
local VIRIDIAN_DFS_MAX_FRAMES = 3600
local VIRIDIAN_DFS_ACTION_TIMEOUT = 64
local VIRIDIAN_DFS_SETTLE_FRAMES = 12
local VIRIDIAN_TARGET_MAX_STEPS = 16
local VIRIDIAN_DFS_DIRECTIONS = {
    {
        name = "up",
        input = 0x10,
        opposite = 0x20,
        opposite_name = "down",
    },
    {
        name = "right",
        input = 0x80,
        opposite = 0x40,
        opposite_name = "left",
    },
    {
        name = "left",
        input = 0x40,
        opposite = 0x80,
        opposite_name = "right",
    },
    {
        name = "down",
        input = 0x20,
        opposite = 0x10,
        opposite_name = "up",
    },
}
local VIRIDIAN_TARGET_ROUTE = {
    primary_left = "left",
    fallback_down = "down",
    fallback_left = "left",
    fallback_up = "up",
    up_to_warp = "up",
}

local function viridianDfsSignature(nametableHash, x, y)
    return string.format("%08X:%02X:%02X", nametableHash, x, y)
end

local function parcelRouteInput(tick)
    local cursor = tick
    for _, step in ipairs(PARCEL_ROUTE) do
        if cursor < step.frames then
            return step.input
        end
        cursor = cursor - step.frames
    end
    return nil
end

local function beginViridianDfsAction(
    kind,
    directionName,
    direction,
    opposite,
    oppositeName,
    nametableHash,
    x,
    y,
    expectedSignature
)
    local signature = viridianDfsSignature(nametableHash, x, y)
    viridianDfsAction = {
        kind = kind,
        direction_name = directionName,
        direction = direction,
        opposite = opposite,
        opposite_name = oppositeName,
        start_signature = signature,
        expected_signature = expectedSignature,
        frames = 0,
        moved = false,
        stable_frames = 0,
        last_signature = signature,
    }
end

local function viridianDirectionByName(name)
    for _, direction in ipairs(VIRIDIAN_DFS_DIRECTIONS) do
        if direction.name == name then
            return direction
        end
    end
    error("unknown Viridian direction: " .. tostring(name))
end

local function beginViridianTargetAction(
    stage,
    nametableHash,
    x,
    y
)
    local direction =
        viridianDirectionByName(VIRIDIAN_TARGET_ROUTE[stage])
    viridianTargetStage = stage
    beginViridianDfsAction(
        "target",
        direction.name,
        direction.input,
        direction.opposite,
        direction.opposite_name,
        nametableHash,
        x,
        y,
        nil
    )
    viridianDfsAction.target_stage = stage
end
local traceRows = {
    "trace_tick\tframe\tinput\tnametable_checksum\tx\ty\tpc\t" ..
        "prompt_arrow\tbattle_recovery",
}
local checkpointRows = {
    "trace_tick\tframe\tlabel\tinput\tnametable_checksum\tx\ty\tpc\t" ..
        "prompt_arrow\tbattle_recovery\tpng\tnametable_bin",
}
local capturedFrames = {}
local pokedexEventRows = {
    "input_frame\tkind\taddress\told_value\tnew_value\t" ..
        "species_id\tpc\tprg_offset",
}
local naturallySeen = {}
local naturallyCaught = {}

local function prgOffsetForPc(pc)
    local converted = emu.convertAddress(
        pc,
        emu.memType.nesMemory
    )
    if converted ~= nil
        and converted.memType == emu.memType.nesPrgRom
    then
        return converted.address
    end
    return -1
end

local function tracePokedexWrite(
    kind,
    firstAddress,
    address,
    value
)
    if not traceActive then
        return
    end
    local oldValue = emu.read(address, emu.memType.nesDebug)
    if oldValue == value then
        return
    end
    local newBits = value & ((~oldValue) & 0xFF)
    local pc = emu.getState()["cpu.pc"] or 0
    for bit = 0, 7 do
        if (newBits & (1 << bit)) ~= 0 then
            local speciesId =
                (address - firstAddress) * 8 + bit + 1
            if speciesId <= 151 then
                local target =
                    kind == "caught"
                    and naturallyCaught
                    or naturallySeen
                target[speciesId] = true
                pokedexEventRows[#pokedexEventRows + 1] =
                    string.format(
                        "%d\t%s\t%04X\t%02X\t%02X\t%d\t" ..
                            "%04X\t%06X",
                        frame,
                        kind,
                        address,
                        oldValue,
                        value,
                        speciesId,
                        pc,
                        prgOffsetForPc(pc)
                    )
            end
        end
    end
end

for _, specification in ipairs({
    {
        kind = "caught",
        first = 0x609F,
        last = 0x60B1,
    },
    {
        kind = "seen",
        first = 0x60B3,
        last = 0x60C5,
    },
}) do
    local range = specification
    emu.addMemoryCallback(function(address, value)
        tracePokedexWrite(
            range.kind,
            range.first,
            address,
            value
        )
    end, emu.callbackType.write, range.first, range.last)
end

local function tableKeyCount(values)
    local count = 0
    for _ in pairs(values) do
        count = count + 1
    end
    return count
end

local observedTargets = {}
for _, specification in ipairs(dialogueTargets) do
    local record = fromHex(specification.payload_hex)
    local occurrenceCount = 0
    local foundAt = nil
    local searchAt = 1
    while true do
        local occurrence = string.find(rom, record, searchAt, true)
        if occurrence == nil then
            break
        end
        occurrenceCount = occurrenceCount + 1
        foundAt = occurrence
        searchAt = occurrence + 1
    end
    if occurrenceCount ~= 1
        and not (
            allowMissingDialogueTargets
            and occurrenceCount == 0
        )
    then
        error(string.format(
            "$%06X record occurrence count=%d",
            specification.source_offset,
            occurrenceCount
        ))
    end

    if occurrenceCount == 1 then
    local fileOffset = foundAt - 1
    local prgOffset = fileOffset - 16
    local pair = prgOffset // 0x8000
    local cpuFirst = 0x8000 + (prgOffset % 0x8000)
    local cpuLast = cpuFirst + #record - 1
    local target = {
        source_offset = specification.source_offset,
        label = specification.label,
        milestone = specification.milestone or "",
        record = record,
        file_offset = fileOffset,
        prg_offset = prgOffset,
        pair = pair,
        cpu_first = cpuFirst,
        cpu_last = cpuLast,
        read_events = 0,
        read_bytes = {},
        read_mismatches = 0,
        first_read_frame = nil,
        last_read_frame = nil,
    }
    observedTargets[#observedTargets + 1] = target

    local observedTarget = target
    emu.addMemoryCallback(function(address, value)
        if not traceActive
            or frame < TRACE_FIRST
            or frame > TRACE_LAST
        then
            return
        end
        local converted = emu.convertAddress(
            address,
            emu.memType.nesMemory
        )
        if converted == nil
            or converted.memType ~= emu.memType.nesPrgRom
            or converted.address < observedTarget.prg_offset
            or converted.address >=
                observedTarget.prg_offset + #observedTarget.record
        then
            return
        end
        local index = converted.address - observedTarget.prg_offset
        observedTarget.read_events =
            observedTarget.read_events + 1
        observedTarget.read_bytes[index] = true
        if value ~= string.byte(observedTarget.record, index + 1) then
            observedTarget.read_mismatches =
                observedTarget.read_mismatches + 1
        end
        if observedTarget.first_read_frame == nil then
            observedTarget.first_read_frame = frame
            pendingTargetStarts[#pendingTargetStarts + 1] =
                observedTarget.label
        end
        observedTarget.last_read_frame = frame
    end, emu.callbackType.read, cpuFirst, cpuLast)
    end
end

local function captureCheckpoint(label, arrow, includeScreenshot)
    local captureKey = tostring(frame) .. ":" .. label
    if capturedFrames[captureKey] then
        return
    end
    capturedFrames[captureKey] = true
    local prefix = string.format(
        "frame_%05d_%s",
        frame,
        label
    )
    local png = ""
    local nametable = prefix .. "_nametable_4k.bin"
    local nametableHash = checksum(
        emu.memType.nesPpuDebug,
        0x2000,
        0x2FFF
    )
    local x = emu.read(0x0304, emu.memType.nesDebug)
    local y = emu.read(0x0306, emu.memType.nesDebug)
    local pc = emu.getState()["cpu.pc"] or 0
    if includeScreenshot ~= false then
        png = prefix .. "_screen.png"
        writeBinary(png, emu.takeScreenshot())
    end
    writeBinary(
        nametable,
        memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
    )
    checkpointRows[#checkpointRows + 1] = string.format(
        "%d\t%d\t%s\t%02X\t%08X\t%02X\t%02X\t%04X\t%s\t" ..
            "%s\t%s\t%s",
        traceTick,
        frame,
        label,
        currentInput,
        nametableHash,
        x,
        y,
        pc,
        tostring(arrow),
        tostring(battleActive),
        png,
        nametable
    )
    writeText(
        "fm3_route1_viridian_checkpoints_partial.tsv",
        table.concat(checkpointRows, "\n") .. "\n"
    )
end

local function startViridianTargetStage(
    stage,
    nametableHash,
    x,
    y,
    arrow
)
    beginViridianTargetAction(stage, nametableHash, x, y)
    captureCheckpoint(
        "viridian_target_try_" .. stage,
        arrow,
        false
    )
end

local function startViridianDfs(
    nametableHash,
    x,
    y,
    arrow,
    reason
)
    local signature =
        viridianDfsSignature(nametableHash, x, y)
    viridianDfsStarted = true
    viridianTargetStage = nil
    viridianDfsNodeCount = 1
    viridianDfsStack = {
        {
            signature = signature,
            tested = {},
        },
    }
    viridianDfsVisited = {[signature] = true}
    viridianDfsAction = nil
    captureCheckpoint(
        "viridian_target_fallback_" .. reason,
        arrow
    )
    captureCheckpoint(
        string.format(
            "viridian_dfs_node_%03d_%08X_%02X_%02X",
            viridianDfsNodeCount,
            nametableHash,
            x,
            y
        ),
        arrow
    )
end

local function targetEvidence()
    local rows = {
        "source_offset\tlabel\tmilestone\tfile_offset\tpair\t" ..
            "cpu_first\tcpu_last\tpayload_bytes\tread_events\t" ..
            "unique_reads\tread_mismatches\tfirst_read_frame\t" ..
            "last_read_frame",
    }
    for _, target in ipairs(observedTargets) do
        local uniqueReads = 0
        for _ in pairs(target.read_bytes) do
            uniqueReads = uniqueReads + 1
        end
        rows[#rows + 1] = string.format(
            "%06X\t%s\t%s\t%06X\t%d\t%04X\t%04X\t%d\t%d\t" ..
                "%d\t%d\t%s\t%s",
            target.source_offset,
            target.label,
            target.milestone,
            target.file_offset,
            target.pair,
            target.cpu_first,
            target.cpu_last,
            #target.record,
            target.read_events,
            uniqueReads,
            target.read_mismatches,
            tostring(target.first_read_frame or ""),
            tostring(target.last_read_frame or "")
        )
    end
    return table.concat(rows, "\n") .. "\n"
end

emu.addEventCallback(function()
    if traceFinalized then
        return
    end
    if not traceActive then
        return
    end
    if battleActive then
        if overworldStableFrames > 0 then
            currentInput = 0
        else
            local phase = battleFrames % 30
            currentInput = phase < 2 and 0x01 or 0
        end
        emu.setInput(decodeInput(currentInput), 0)
        return
    end
    if postBattleMovementFrames > 0 then
        currentInput =
            postBattleMovementFrames >= 17
            and lastDirectionInput
            or 0
        emu.setInput(decodeInput(currentInput), 0)
        return
    end
    if viridianAlignmentActive then
        currentInput = 0
        if viridianDialogueVisible then
            local phase = viridianDfsFrames % 12
            currentInput = phase <= 1 and 0x01 or 0
        elseif viridianDfsAction ~= nil
            and not viridianDfsAction.moved
        then
            local phase = viridianDfsAction.frames % 8
            currentInput =
                phase <= 3 and viridianDfsAction.direction or 0
        end
        emu.setInput(decodeInput(currentInput), 0)
        return
    end
    if parcelRouteActive then
        currentInput = parcelRouteInput(parcelRouteTick) or 0
        emu.setInput(decodeInput(currentInput), 0)
        return
    end
    if stateDrivenMode
        and frame >= CONTROL_START
        and viridianDialogueVisible
    then
        local phase = traceTick % 12
        currentInput = phase <= 1 and 0x01 or 0
        emu.setInput(decodeInput(currentInput), 0)
        return
    end
    currentInput = 0
    if frame < #inputBytes then
        currentInput = string.byte(inputBytes, frame + 1)
    end
    if (currentInput & 0xF0) ~= 0 then
        lastDirectionInput = currentInput & 0xF0
    end
    emu.setInput(decodeInput(currentInput), 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if not traceActive then
        if bootstrapMode
            and rawget(
                _G,
                "POKEMON_FM3_ROUTE1_BOOTSTRAP_READY"
            ) == true
        then
            traceActive = true
        else
            return
        end
    end
    traceTick = traceTick + 1
    if not battleActive
        and postBattleMovementFrames == 0
        and not viridianAlignmentActive
        and not parcelRouteActive
        and not (
            stateDrivenMode
            and frame >= CONTROL_START
            and viridianDialogueVisible
        )
    then
        frame = frame + 1
    end
    local arrow = promptArrowVisible()
    viridianDialogueVisible = dialogueBoxVisible()
    if stateDrivenMode
        and frame >= CONTROL_START
        and not viridianAlignmentActive
    then
        if viridianDialogueVisible
            and not lastCampaignDialogueVisible
        then
            campaignDialogueDismissCount =
                campaignDialogueDismissCount + 1
            captureCheckpoint(
                "campaign_dialogue_dismiss_" ..
                    tostring(campaignDialogueDismissCount),
                arrow
            )
        end
        lastCampaignDialogueVisible = viridianDialogueVisible
    end
    local nametableHash = nil
    local traceFrame =
        frame >= TRACE_FIRST and frame <= TRACE_LAST
    local controlFrame =
        stateDrivenMode and frame >= CONTROL_START
    if traceFrame or controlFrame then
        nametableHash = checksum(
            emu.memType.nesPpuDebug,
            0x2000,
            0x2FFF
        )
    end
    if parcelRouteEnabled
        and not parcelRouteActive
        and not parcelRouteDone
        and frame >= 7100
        and nametableHash == PARCEL_SHOP_NAMETABLE
        and emu.read(0x0304, emu.memType.nesDebug) == 0x30
        and emu.read(0x0306, emu.memType.nesDebug) == 0xA0
    then
        parcelRouteActive = true
        parcelRouteTick = 0
        captureCheckpoint("parcel_route_start", arrow)
        writeBinary(
            "parcel_route_start_ram_2k.bin",
            memoryBytes(emu.memType.nesDebug, 0x0000, 0x07FF)
        )
    end
    if parcelRouteActive then
        parcelRouteTick = parcelRouteTick + 1
        if parcelRouteInput(parcelRouteTick) == nil then
            parcelRouteActive = false
            parcelRouteDone = true
            currentInput = 0
            captureCheckpoint("parcel_route_complete", arrow)
            writeBinary(
                "parcel_route_complete_ram_2k.bin",
                memoryBytes(emu.memType.nesDebug, 0x0000, 0x07FF)
            )
        end
    end
    if traceFrame then
        traceRows[#traceRows + 1] = string.format(
            "%d\t%d\t%02X\t%08X\t%02X\t%02X\t%04X\t%s\t%s",
            traceTick,
            frame,
            currentInput,
            nametableHash,
            emu.read(0x0304, emu.memType.nesDebug),
            emu.read(0x0306, emu.memType.nesDebug),
            emu.getState()["cpu.pc"] or 0,
            tostring(arrow),
            tostring(battleActive)
        )
    end

    local pc = emu.getState()["cpu.pc"] or 0
    if stateDrivenMode
        and frame >= BATTLE_RECOVERY_START
        and frame < STOP_FRAME
    then
        if not battleActive and pc >= 0xF200 and pc <= 0xF2FF then
            battleActive = true
            battleFrames = 0
            overworldStableFrames = 0
            battleRecoveryCount = battleRecoveryCount + 1
        elseif battleActive then
            battleFrames = battleFrames + 1
            if pc >= 0xD230 and pc <= 0xD240 then
                overworldStableFrames = overworldStableFrames + 1
            else
                overworldStableFrames = 0
            end
            if overworldStableFrames >= 90 then
                captureCheckpoint(
                    "battle_recovery_end_" ..
                        tostring(battleRecoveryCount),
                    arrow
                )
                battleActive = false
                battleFrames = 0
                overworldStableFrames = 0
                postBattleMovementFrames = 19
                currentInput = 0
            end
        end
    end
    if postBattleMovementFrames > 0 and not battleActive then
        postBattleMovementFrames = postBattleMovementFrames - 1
    end
    if stateDrivenMode
        and not viridianAlignmentDone
        and frame >= CONTROL_START
        and not battleActive
        and postBattleMovementFrames == 0
    then
        local y = emu.read(0x0306, emu.memType.nesDebug)
        local x = emu.read(0x0304, emu.memType.nesDebug)
        local signature =
            viridianDfsSignature(nametableHash, x, y)
        if not viridianAlignmentActive and y < 0xD0 then
            viridianAlignmentActive = true
            viridianDfsFrames = 0
            viridianDfsNodeCount = 0
            viridianDfsStack = {}
            viridianDfsVisited = {}
            viridianDfsStarted = false
            viridianTargetSteps = 0
            viridianAlignmentStableFrames = 0
            startViridianTargetStage(
                "primary_left",
                nametableHash,
                x,
                y,
                arrow
            )
            captureCheckpoint(
                "viridian_target_start",
                arrow,
                false
            )
        end
        if viridianAlignmentActive then
            local dfsFailureReason = nil
            if viridianDialogueVisible
                and not lastViridianDialogueVisible
            then
                viridianDialogueDismissCount =
                    viridianDialogueDismissCount + 1
                captureCheckpoint(
                    "viridian_dialogue_dismiss_" ..
                        tostring(viridianDialogueDismissCount),
                    arrow
                )
            end
            lastViridianDialogueVisible =
                viridianDialogueVisible
            local cityReached =
                y >= 0xD0
                or nametableHash == VIRIDIAN_CITY_NAMETABLE
            viridianDfsFrames = viridianDfsFrames + 1
            if cityReached then
                viridianAlignmentStableFrames =
                    viridianAlignmentStableFrames + 1
                if viridianDfsAction ~= nil then
                    viridianDfsAction.moved = true
                end
            else
                viridianAlignmentStableFrames = 0
            end

            if viridianDfsAction ~= nil
                and not cityReached
                and not viridianDialogueVisible
            then
                local action = viridianDfsAction
                action.frames = action.frames + 1
                if not action.moved then
                    if signature ~= action.start_signature then
                        action.moved = true
                        action.stable_frames = 0
                        action.last_signature = signature
                        captureCheckpoint(
                            string.format(
                                "viridian_dfs_move_%s_%s_" ..
                                    "%08X_%02X_%02X",
                                action.kind,
                                action.direction_name,
                                nametableHash,
                                x,
                                y
                            ),
                            arrow,
                            false
                        )
                    elseif action.frames >=
                        VIRIDIAN_DFS_ACTION_TIMEOUT
                    then
                        if action.kind == "target" then
                            local blockedStage = action.target_stage
                            captureCheckpoint(
                                "viridian_target_blocked_" ..
                                    blockedStage,
                                arrow
                            )
                            viridianDfsAction = nil
                            if blockedStage == "primary_left" then
                                startViridianTargetStage(
                                    "fallback_down",
                                    nametableHash,
                                    x,
                                    y,
                                    arrow
                                )
                            else
                                startViridianDfs(
                                    nametableHash,
                                    x,
                                    y,
                                    arrow,
                                    "blocked_" .. blockedStage
                                )
                            end
                        elseif action.kind == "explore" then
                            captureCheckpoint(
                                string.format(
                                    "viridian_dfs_blocked_%03d_%s",
                                    viridianDfsNodeCount,
                                    action.direction_name
                                ),
                                arrow
                            )
                            viridianDfsAction = nil
                        else
                            dfsFailureReason =
                                action.kind .. "_blocked_" ..
                                action.direction_name
                        end
                    end
                else
                    if signature == action.last_signature then
                        action.stable_frames =
                            action.stable_frames + 1
                    else
                        action.last_signature = signature
                        action.stable_frames = 0
                    end
                    if action.stable_frames >=
                        VIRIDIAN_DFS_SETTLE_FRAMES
                    then
                        local completed = action
                        viridianDfsAction = nil
                        if completed.kind == "target" then
                            viridianTargetSteps =
                                viridianTargetSteps + 1
                            captureCheckpoint(
                                "viridian_target_complete_" ..
                                    completed.target_stage,
                                arrow
                            )
                            local nextStage = nil
                            if completed.target_stage ==
                                "primary_left"
                            then
                                nextStage = "up_to_warp"
                            elseif completed.target_stage ==
                                "fallback_down"
                            then
                                nextStage = "fallback_left"
                            elseif completed.target_stage ==
                                "fallback_left"
                            then
                                nextStage = "fallback_up"
                            elseif completed.target_stage ==
                                "fallback_up"
                                or completed.target_stage ==
                                    "up_to_warp"
                            then
                                nextStage = "up_to_warp"
                            else
                                dfsFailureReason =
                                    "unknown_target_stage_" ..
                                    tostring(
                                        completed.target_stage
                                    )
                            end
                            if nextStage ~= nil then
                                if viridianTargetSteps >=
                                    VIRIDIAN_TARGET_MAX_STEPS
                                then
                                    startViridianDfs(
                                        nametableHash,
                                        x,
                                        y,
                                        arrow,
                                        "target_step_limit"
                                    )
                                else
                                    startViridianTargetStage(
                                        nextStage,
                                        nametableHash,
                                        x,
                                        y,
                                        arrow
                                    )
                                end
                            end
                        elseif completed.kind == "explore" then
                            if viridianDfsVisited[signature] then
                                captureCheckpoint(
                                    string.format(
                                        "viridian_dfs_seen_%03d_%s",
                                        viridianDfsNodeCount,
                                        completed.direction_name
                                    ),
                                    arrow
                                )
                                local currentNode =
                                    viridianDfsStack[
                                        #viridianDfsStack
                                    ]
                                if signature ==
                                    currentNode.signature
                                then
                                    captureCheckpoint(
                                        "viridian_dfs_seen_current_" ..
                                            completed.direction_name,
                                        arrow
                                    )
                                else
                                    beginViridianDfsAction(
                                        "return_seen",
                                        completed.opposite_name,
                                        completed.opposite,
                                        completed.direction,
                                        completed.direction_name,
                                        nametableHash,
                                        x,
                                        y,
                                        currentNode.signature
                                    )
                                end
                            else
                                viridianDfsNodeCount =
                                    viridianDfsNodeCount + 1
                                if viridianDfsNodeCount >
                                    VIRIDIAN_DFS_MAX_NODES
                                then
                                    dfsFailureReason = "node_limit"
                                else
                                    viridianDfsVisited[signature] = true
                                    viridianDfsStack[
                                        #viridianDfsStack + 1
                                    ] = {
                                        signature = signature,
                                        tested = {},
                                        back_direction =
                                            completed.opposite,
                                        back_name =
                                            completed.opposite_name,
                                        forward_direction =
                                            completed.direction,
                                        forward_name =
                                            completed.direction_name,
                                    }
                                    captureCheckpoint(
                                        string.format(
                                            "viridian_dfs_node_%03d_" ..
                                                "%08X_%02X_%02X",
                                            viridianDfsNodeCount,
                                            nametableHash,
                                            x,
                                            y
                                        ),
                                        arrow
                                    )
                                end
                            end
                        elseif completed.kind == "return_seen" then
                            if signature ~=
                                completed.expected_signature
                            then
                                dfsFailureReason =
                                    "return_seen_mismatch"
                            else
                                captureCheckpoint(
                                    "viridian_dfs_return_seen_complete",
                                    arrow
                                )
                            end
                        elseif completed.kind == "backtrack" then
                            if signature ~=
                                completed.expected_signature
                            then
                                dfsFailureReason =
                                    "backtrack_mismatch"
                            else
                                table.remove(viridianDfsStack)
                                captureCheckpoint(
                                    string.format(
                                        "viridian_dfs_backtrack_" ..
                                            "%03d_%08X_%02X_%02X",
                                        #viridianDfsStack,
                                        nametableHash,
                                        x,
                                        y
                                    ),
                                    arrow
                                )
                            end
                        else
                            dfsFailureReason =
                                "unknown_action_" .. completed.kind
                        end
                    end
                end
            end

            if viridianDfsAction == nil
                and not cityReached
                and not viridianDialogueVisible
                and dfsFailureReason == nil
                and viridianDfsStarted
            then
                local currentNode =
                    viridianDfsStack[#viridianDfsStack]
                local direction = nil
                for _, candidate in ipairs(
                    VIRIDIAN_DFS_DIRECTIONS
                ) do
                    if not currentNode.tested[candidate.name] then
                        direction = candidate
                        currentNode.tested[candidate.name] = true
                        break
                    end
                end
                if direction ~= nil then
                    beginViridianDfsAction(
                        "explore",
                        direction.name,
                        direction.input,
                        direction.opposite,
                        direction.opposite_name,
                        nametableHash,
                        x,
                        y,
                        nil
                    )
                    captureCheckpoint(
                        string.format(
                            "viridian_dfs_try_%03d_%s",
                            viridianDfsNodeCount,
                            direction.name
                        ),
                        arrow
                    )
                elseif #viridianDfsStack > 1 then
                    local childNode =
                        viridianDfsStack[#viridianDfsStack]
                    local parentNode =
                        viridianDfsStack[#viridianDfsStack - 1]
                    beginViridianDfsAction(
                        "backtrack",
                        childNode.back_name,
                        childNode.back_direction,
                        childNode.forward_direction,
                        childNode.forward_name,
                        nametableHash,
                        x,
                        y,
                        parentNode.signature
                    )
                    captureCheckpoint(
                        string.format(
                            "viridian_dfs_backtrack_try_%03d_%s",
                            viridianDfsNodeCount,
                            childNode.back_name
                        ),
                        arrow
                    )
                else
                    dfsFailureReason = "exhausted"
                end
            end

            if viridianAlignmentStableFrames >= 16 then
                captureCheckpoint("viridian_dfs_city_reached", arrow)
                viridianAlignmentActive = false
                viridianAlignmentDone = true
                viridianDfsAction = nil
                currentInput = 0
            elseif viridianDfsFrames >= VIRIDIAN_DFS_MAX_FRAMES then
                dfsFailureReason = "frame_limit"
            end

            if dfsFailureReason ~= nil then
                captureCheckpoint(
                    "viridian_dfs_fail_" .. dfsFailureReason,
                    arrow
                )
                writeText(
                    "fm3_route1_viridian_frames.tsv",
                    table.concat(traceRows, "\n") .. "\n"
                )
                writeText(
                    "fm3_route1_viridian_checkpoints.tsv",
                    table.concat(checkpointRows, "\n") .. "\n"
                )
                writeText(
                    "fm3_route1_viridian_dialogue_targets.tsv",
                    targetEvidence()
                )
                writeText(
                    "fm3_route1_viridian_pokedex_events.tsv",
                    table.concat(pokedexEventRows, "\n") .. "\n"
                )
                traceFinalized = true
                print(string.format(
                    "POKEMON_FM3_ROUTE1_VIRIDIAN_TRACE_FAIL " ..
                        "reason=viridian_dfs_%s frame=%d " ..
                        "dfs_frames=%d nodes=%d depth=%d " ..
                        "hash=%08X x=%02X y=%02X writes_to_game=0",
                    dfsFailureReason,
                    frame,
                    viridianDfsFrames,
                    viridianDfsNodeCount,
                    #viridianDfsStack,
                    nametableHash,
                    x,
                    y
                ))
                emu.stop(1)
                return
            end
        elseif y >= 0xD0 then
            viridianAlignmentDone = true
        end
    end

    local label = checkpoints[frame]
    if currentInput == 0x01
        and not battleActive
        and frame >= TRACE_FIRST
        and frame <= TRACE_LAST
    then
        label = label or "a_press"
    end
    if arrow and not lastArrow
        and frame >= TRACE_FIRST
        and frame <= TRACE_LAST
    then
        label = label or "dialogue_arrow"
    end
    if #pendingTargetStarts > 0 then
        label = label or (
            "target_" .. table.concat(pendingTargetStarts, "_")
        )
        pendingTargetStarts = {}
    end
    if label ~= nil then
        captureCheckpoint(label, arrow)
    end
    lastArrow = arrow

    if frame ~= STOP_FRAME then
        return
    end
    captureCheckpoint(FINAL_LABEL, arrow)
    writeText(
        "fm3_route1_viridian_frames.tsv",
        table.concat(traceRows, "\n") .. "\n"
    )
    writeText(
        "fm3_route1_viridian_checkpoints.tsv",
        table.concat(checkpointRows, "\n") .. "\n"
    )
    writeText(
        "fm3_route1_viridian_dialogue_targets.tsv",
        targetEvidence()
    )
    writeText(
        "fm3_route1_viridian_pokedex_events.tsv",
        table.concat(pokedexEventRows, "\n") .. "\n"
    )

    traceFinalized = true
    local hitLabels = {}
    for _, target in ipairs(observedTargets) do
        if target.read_events > 0 then
            hitLabels[#hitLabels + 1] = target.label
        end
    end
    print(string.format(
        PASS_MARKER .. " mapper=163 " ..
            "region=%s frames=%d trace=%d-%d checkpoints=%d " ..
            "dialogues=%s writes_to_game=0 input_frames=%d " ..
            "bootstrap=%s state_driven=%s battle_recoveries=%d " ..
            "viridian_aligned=%s alignment_dialogues_dismissed=%d " ..
            "campaign_dialogues_dismissed=%d " ..
            "parcel_route_done=%s " ..
            "newly_seen=%d newly_caught=%d " ..
            "absolute_end=%s",
        tostring(emu.getState()["region"]),
        frame,
        TRACE_FIRST,
        TRACE_LAST,
        #checkpointRows - 1,
        #hitLabels > 0 and table.concat(hitLabels, ",") or "none",
        #inputBytes,
        bootstrapMode and "campaign_prototype" or "none",
        tostring(stateDrivenMode),
        battleRecoveryCount,
        tostring(viridianAlignmentDone),
        viridianDialogueDismissCount,
        campaignDialogueDismissCount,
        tostring(parcelRouteDone),
        tableKeyCount(naturallySeen),
        tableKeyCount(naturallyCaught),
        tostring(
            rawget(_G, "POKEMON_FM3_ROUTE1_ABSOLUTE_FRAME")
                or ""
        )
    ))
    emu.stop(0)
end, emu.eventType.endFrame)
