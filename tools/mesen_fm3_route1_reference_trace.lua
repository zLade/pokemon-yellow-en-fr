-- Direct FM3 reference trace on the canonical Chinese ROM.
--
-- French translated records are absent by construction, so the common route
-- tracer skips those passive targets while preserving all frame, nametable,
-- coordinate, input, and screenshot evidence.

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

POKEMON_FM3_ALLOW_MISSING_DIALOGUE_TARGETS = true
loadModule("mesen_fm3_route1_viridian_trace.lua")
