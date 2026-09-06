-- Cold-boot bridge from the proven controller-only campaign prototype to the
-- FM3 Route 1/Viridian segment.  The first successful emu.stop(0) marks the
-- stable laboratory exit; the trace probe then replays FM3 frame 5194 onward.
-- A prototype failure still stops Mesen immediately with its original code.

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

local originalStop = emu.stop
local prototypeCompleted = false
POKEMON_FM3_ROUTE1_BOOTSTRAP = true
POKEMON_FM3_ROUTE1_BOOTSTRAP_READY = false
POKEMON_FM3_ROUTE1_STATE_DRIVEN = true
POKEMON_FM3_ROUTE1_ABSOLUTE_FRAME = 0

emu.stop = function(code)
    if code == 0 and not prototypeCompleted then
        prototypeCompleted = true
        POKEMON_FM3_ROUTE1_BOOTSTRAP_READY = true
        return
    end
    originalStop(code)
end

emu.addEventCallback(function()
    POKEMON_FM3_ROUTE1_ABSOLUTE_FRAME =
        POKEMON_FM3_ROUTE1_ABSOLUTE_FRAME + 1
end, emu.eventType.endFrame)

loadModule("campaign/mesen_campaign_prototype.lua")
loadModule("mesen_fm3_route1_viridian_trace.lua")
