-- Controller-only campaign plus an exact PRG text-read trace.
--
-- This wrapper never writes game memory.  It observes which PRG-ROM bytes the
-- normal campaign prototype reads and records a second set while the forced
-- rival battle is active.  The release-side validator intersects those byte
-- sets with the final 1,912-reference pointer manifest.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local allReads = {}
local battleReads = {}
local frames = 0
local battleActive = false
local battleSeen = false

local function writeText(filename, data)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "w"))
    file:write(data)
    file:close()
end

local function countKeys(values)
    local count = 0
    for _ in pairs(values) do
        count = count + 1
    end
    return count
end

local function rangesText(values)
    local offsets = {}
    for offset in pairs(values) do
        offsets[#offsets + 1] = offset
    end
    table.sort(offsets)
    local lines = {
        "PRG offsets exclude the 16-byte iNES header.",
        "start_hex\tend_inclusive_hex\tbyte_count",
    }
    local first = nil
    local last = nil
    for _, offset in ipairs(offsets) do
        if first == nil then
            first = offset
            last = offset
        elseif offset == last + 1 then
            last = offset
        else
            lines[#lines + 1] = string.format(
                "%06X\t%06X\t%d",
                first,
                last,
                last - first + 1
            )
            first = offset
            last = offset
        end
    end
    if first ~= nil then
        lines[#lines + 1] = string.format(
            "%06X\t%06X\t%d",
            first,
            last,
            last - first + 1
        )
    end
    return table.concat(lines, "\n") .. "\n"
end

emu.addMemoryCallback(function(address)
    local converted = emu.convertAddress(address, emu.memType.nesMemory)
    if converted == nil or converted.memType ~= emu.memType.nesPrgRom then
        return
    end
    allReads[converted.address] = true
    if battleActive then
        battleReads[converted.address] = true
    end
end, emu.callbackType.read, 0x8000, 0xFFFF)

POKEMON_CAMPAIGN_JOURNAL_HOOK = function(row)
    if row.kind ~= "transition" then
        return
    end
    if row.target == "complete_rival_battle" then
        battleActive = true
        battleSeen = true
    elseif row.target == "leave_lab" then
        battleActive = false
    end
end

emu.addEventCallback(function()
    frames = frames + 1
end, emu.eventType.endFrame)

POKEMON_CAMPAIGN_FINALIZE_HOOK = function(status, endpoint, campaignFrame)
    local allCount = countKeys(allReads)
    local battleCount = countKeys(battleReads)
    if status ~= "completed" then
        error("campaign did not complete: " .. tostring(status))
    end
    if not battleSeen or battleCount == 0 then
        error("forced rival battle produced no isolated PRG reads")
    end
    if endpoint ~= "outside_lab_stable" then
        error("unexpected campaign endpoint: " .. tostring(endpoint))
    end
    writeText("campaign_english_prg_reads_all.tsv", rangesText(allReads))
    writeText("campaign_english_prg_reads_battle.tsv", rangesText(battleReads))
    writeText(
        "campaign_english_text_trace_summary.txt",
        "mode=controller_only_read_trace\n" ..
        "writes_to_game=0\n" ..
        "campaign_status=" .. tostring(status) .. "\n" ..
        "campaign_endpoint=" .. tostring(endpoint) .. "\n" ..
        "campaign_frame=" .. tostring(campaignFrame) .. "\n" ..
        "all_unique_prg_bytes=" .. tostring(allCount) .. "\n" ..
        "battle_unique_prg_bytes=" .. tostring(battleCount) .. "\n" ..
        "battle_seen=true\n"
    )
    print(string.format(
        "POKEMON_CAMPAIGN_ENGLISH_TRACE_PASS mapper=163 region=%s " ..
        "frames=%d allPrgBytes=%d battlePrgBytes=%d " ..
        "mode=controller writes_to_game=0",
        tostring(emu.getState()["region"]),
        campaignFrame,
        allCount,
        battleCount
    ))
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
dofile(
    directory .. separator .. "campaign" .. separator ..
    "mesen_campaign_prototype.lua"
)
