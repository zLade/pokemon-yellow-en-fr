-- Select the exact untouched English ITEMS/Ash/HMs/SAVE contract.
POKEMON_PLAYER_MENU_PROFILE = "en-US"

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
dofile(directory .. separator .. "mesen_player_menu_french_probe.lua")
