-- Evidence-backed RAM map for the campaign harness.
--
-- Keep this file intentionally small.  Guesses and merely correlated offsets
-- must stay in discovery reports until a targeted probe proves their meaning.

local RamMap = {
    schema_version = 1,

    pokedex_unlock = {
        address = 0x6000,
        memory_domain = "nesMemory",
        required_mask = 0x20,
        access = "assisted_masked_or",
        evidence = "tools/mesen_pokedex_ram_probe.lua",
        note = "$6000 bit $20 makes the fresh-game Pokédex menu accessible.",
    },

    pokedex_seen_count = {
        address = 0x6031,
        memory_domain = "nesMemory",
        access = "read_only",
        evidence = "tools/mesen_pokedex_ram_probe.lua",
    },

    pokedex_caught_count = {
        address = 0x6032,
        memory_domain = "nesMemory",
        access = "read_only",
        evidence = "tools/mesen_pokedex_ram_probe.lua",
    },

    pokedex_caught_bitmap = {
        first = 0x609F,
        last = 0x60B1,
        memory_domain = "nesMemory",
        species_limit = 151,
        last_byte_mask = 0x7F,
        bit_order = "lsb_first",
        access = "read_only",
        evidence = "tools/mesen_pokedex_ram_probe.lua",
    },

    pokedex_seen_bitmap = {
        first = 0x60B3,
        last = 0x60C5,
        memory_domain = "nesMemory",
        species_limit = 151,
        last_byte_mask = 0x7F,
        bit_order = "lsb_first",
        access = "read_only",
        evidence = "tools/mesen_pokedex_ram_probe.lua",
    },

    pokedex_selected_species = {
        address = 0x60C8,
        memory_domain = "nesMemory",
        access = "read_only",
        evidence = "tools/mesen_pokedex_ram_probe.lua",
    },

    player_oam_shadow = {
        access = "read_only",
        x = {
            address = 0x0304,
            memory_domain = "nesDebug",
        },
        y = {
            address = 0x0306,
            memory_domain = "nesDebug",
        },
        evidence = "tools/mesen_campaign_house_exit_probe.lua",
        note = "Player screen coordinates observed during controller walking.",
    },
}

function RamMap.pokedex_unlock_value(currentValue)
    if type(currentValue) ~= "number"
        or currentValue < 0
        or currentValue > 0xFF
        or currentValue ~= math.floor(currentValue)
    then
        error("current Pokédex unlock byte must be an 8-bit integer", 2)
    end
    return currentValue | RamMap.pokedex_unlock.required_mask
end

function RamMap.pokedex_bit_location(kind, speciesId)
    local bitmap
    if kind == "seen" then
        bitmap = RamMap.pokedex_seen_bitmap
    elseif kind == "caught" then
        bitmap = RamMap.pokedex_caught_bitmap
    else
        error("Pokédex bitmap kind must be 'seen' or 'caught'", 2)
    end
    if type(speciesId) ~= "number"
        or speciesId ~= math.floor(speciesId)
        or speciesId < 1
        or speciesId > bitmap.species_limit
    then
        error("Pokédex species ID must be an integer in [1, 151]", 2)
    end
    local zeroBased = speciesId - 1
    return {
        address = bitmap.first + (zeroBased >> 3),
        mask = 1 << (zeroBased & 7),
    }
end

function RamMap.assisted_write_whitelist(memoryTypes)
    if type(memoryTypes) ~= "table" or memoryTypes.nesMemory == nil then
        error("memoryTypes.nesMemory is required", 2)
    end
    return {
        {
            address = RamMap.pokedex_unlock.address,
            mem_type = memoryTypes.nesMemory,
            label = "pokedex_unlock_mask_20",
            validate = function(_, value, before)
                if before == nil then
                    return false, "a pre-write value is required"
                end
                local expected = RamMap.pokedex_unlock_value(before)
                return value == expected,
                    "only a masked OR with $20 is permitted"
            end,
        },
    }
end

function RamMap.read_player_coordinates(readMemory, memoryTypes)
    if type(readMemory) ~= "function" then
        error("readMemory must be a function", 2)
    end
    if type(memoryTypes) ~= "table" or memoryTypes.nesDebug == nil then
        error("memoryTypes.nesDebug is required", 2)
    end
    return {
        x = readMemory(
            RamMap.player_oam_shadow.x.address,
            memoryTypes.nesDebug
        ),
        y = readMemory(
            RamMap.player_oam_shadow.y.address,
            memoryTypes.nesDebug
        ),
    }
end

return RamMap
