-- Short controller-only probe for the dedicated Viridian shop/parcel route.

local function scriptDirectory()
    local source = debug.getinfo(1, "S").source or ""
    if source:sub(1, 1) == "@" then
        source = source:sub(2)
    end
    return assert(source:match("^(.*)[/\\][^/\\]+$"))
end

local directory = scriptDirectory()
local separator = directory:find("\\", 1, true) and "\\" or "/"

POKEMON_FM3_ROUTE1_TRACE_FIRST = 7000
POKEMON_FM3_ROUTE1_TRACE_LAST = 7390
POKEMON_FM3_ROUTE1_CONTROL_START = 6407
POKEMON_FM3_PARCEL_ROUTE = true
POKEMON_FM3_ROUTE1_STOP_FRAME = 7400
POKEMON_FM3_ROUTE1_PASS_MARKER =
    "POKEMON_FM3_PARCEL_ROUTE_PROBE_PASS"
POKEMON_FM3_ROUTE1_FINAL_LABEL = "parcel_route_probe_end"

dofile(
    directory .. separator ..
        "mesen_fm3_route1_viridian_after_prototype.lua"
)
