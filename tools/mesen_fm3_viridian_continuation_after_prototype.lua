-- Diagnostic controller-only continuation from the proven cold-boot route.
--
-- The shared bridge obtains Pikachu, wins the mandatory rival battle, exits
-- the laboratory, crosses Route 1 and aligns the player in Viridian.  This
-- wrapper then keeps consuming the frozen FM3 controller stream until just
-- after the reference movie's next natural Pokédex event (#021 at frame
-- 11915).  The trace remains read-only with respect to game memory.

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

POKEMON_FM3_ROUTE1_TRACE_FIRST = 7100
POKEMON_FM3_ROUTE1_TRACE_LAST = 43150
-- Controller recovery still begins at the proven Route 1 boundary.
-- TRACE_FIRST only limits the host-side continuation evidence.
POKEMON_FM3_ROUTE1_CONTROL_START = 6407
POKEMON_FM3_ROUTE1_STOP_FRAME = 43159
POKEMON_FM3_ROUTE1_PASS_MARKER =
    "POKEMON_FM3_VIRIDIAN_CONTINUATION_PASS"
POKEMON_FM3_ROUTE1_FINAL_LABEL =
    "full_reference_continuation_trace_end"

loadModule("mesen_fm3_route1_viridian_after_prototype.lua")
