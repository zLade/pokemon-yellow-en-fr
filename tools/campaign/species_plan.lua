-- Numeric capture plan independent from the Pokédex storage representation.
--
-- Goal 151 represents the canonical Kanto Pokédex IDs. Goal 159 represents
-- every slot exposed by this ROM's 159-entry name table. Slots 152-159 are
-- named Raikou, Entei, Suicune, Lugia, Ho-Oh, Kyogre, Groudon and Rayquaza,
-- but are outside the proven 151-entry Pokédex bitmap/UI. Their presence in
-- the name table alone does not prove that all eight are catchable in-game.

local SpeciesPlan = {}
SpeciesPlan.__index = SpeciesPlan

local VALID_GOALS = {
    [151] = "canonical_gen1",
    [159] = "rom_table_159",
}

local function requirePositiveInteger(value, label)
    if type(value) ~= "number"
        or value < 1
        or value ~= math.floor(value)
    then
        error(label .. " must be a positive integer", 3)
    end
end

local function copyArray(source)
    local copy = {}
    for index, value in ipairs(source) do
        copy[index] = value
    end
    return copy
end

local function defaultOrder(goal)
    local order = {}
    for speciesId = 1, goal do
        order[#order + 1] = speciesId
    end
    return order
end

local function validateOrder(order, goal)
    if type(order) ~= "table" then
        error("species order must be a table", 3)
    end
    if #order ~= goal then
        error(string.format(
            "species order must contain exactly %d IDs",
            goal
        ), 3)
    end
    local seen = {}
    for position, speciesId in ipairs(order) do
        requirePositiveInteger(
            speciesId,
            "species order entry " .. position
        )
        if speciesId > goal then
            error("species ID is outside the selected goal", 3)
        end
        if seen[speciesId] then
            error("duplicate species ID: " .. speciesId, 3)
        end
        seen[speciesId] = true
    end
end

function SpeciesPlan.new(options)
    if type(options) == "number" then
        options = {goal = options}
    else
        options = options or {}
    end
    local goal = options.goal or 151
    if VALID_GOALS[goal] == nil then
        error("species goal must be exactly 151 or 159", 2)
    end

    local order = options.order or defaultOrder(goal)
    validateOrder(order, goal)
    return setmetatable({
        goal = goal,
        kind = VALID_GOALS[goal],
        _order = copyArray(order),
    }, SpeciesPlan)
end

function SpeciesPlan:targets()
    return copyArray(self._order)
end

function SpeciesPlan:contains(speciesId)
    return type(speciesId) == "number"
        and speciesId == math.floor(speciesId)
        and speciesId >= 1
        and speciesId <= self.goal
end

local function ownedPredicate(owned)
    if type(owned) == "function" then
        return owned
    end
    if type(owned) ~= "table" then
        error("owned must be a table or predicate", 3)
    end
    return function(speciesId)
        return owned[speciesId] == true
    end
end

function SpeciesPlan:progress(owned)
    local isOwned = ownedPredicate(owned)
    local ownedCount = 0
    local missing = {}
    for _, speciesId in ipairs(self._order) do
        if isOwned(speciesId) then
            ownedCount = ownedCount + 1
        else
            missing[#missing + 1] = speciesId
        end
    end
    return {
        goal = self.goal,
        owned = ownedCount,
        remaining = self.goal - ownedCount,
        complete = ownedCount == self.goal,
        missing = missing,
    }
end

function SpeciesPlan:next_missing(owned)
    local progress = self:progress(owned)
    return progress.missing[1]
end

function SpeciesPlan:checkpoint_batches(batchSize)
    requirePositiveInteger(batchSize, "batchSize")
    local batches = {}
    local current = {}
    for _, speciesId in ipairs(self._order) do
        current[#current + 1] = speciesId
        if #current == batchSize then
            batches[#batches + 1] = current
            current = {}
        end
    end
    if #current > 0 then
        batches[#batches + 1] = current
    end
    return batches
end

return SpeciesPlan
