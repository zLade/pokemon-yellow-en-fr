-- English 2.0 bridge from the controller-only campaign endpoint to the
-- Route 1/Viridian FM3 diagnostic.  English pagination changes the RNG phase,
-- so battle recovery begins at Route 1 entry instead of at the later French
-- reference frame.  The reference controller stream and game RAM stay
-- untouched.

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
POKEMON_FM3_ROUTE1_BATTLE_RECOVERY_START = 5500
POKEMON_FM3_ROUTE1_PASS_MARKER =
    "POKEMON_FM3_ROUTE1_VIRIDIAN_EN_TRACE_PASS"
POKEMON_FM3_ALLOW_MISSING_DIALOGUE_TARGETS = true

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
