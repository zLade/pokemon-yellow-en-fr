-- Demonstrate and verify the 151-entry Pokédex layout in assisted mode.
--
-- The new-game flow and menu navigation use controller input.  The script
-- then marks the proven SEEN/CAUGHT bitmaps and counters, logging every RAM
-- write.  This validates Pokédex coverage but is intentionally not presented
-- as 151 battle captures.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local writes = {
    "frame,address,old_value,new_value,reason",
}
local desiredInput = {
    a = false,
    b = false,
    select = false,
    start = false,
    up = false,
    down = false,
    left = false,
    right = false,
}

local function pulseAt(frame, button, duration)
    if frames == frame then
        desiredInput[button] = true
    elseif frames == frame + duration then
        desiredInput[button] = false
    end
end

local function writeBinary(filename, data)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    file:write(data)
    file:close()
end

local function loggedWrite(address, value, reason)
    local oldValue = emu.read(address, emu.memType.nesDebug)
    emu.write(address, value, emu.memType.nesDebug)
    writes[#writes + 1] = string.format(
        "%d,%04X,%02X,%02X,%s",
        frames,
        address,
        oldValue,
        value,
        reason
    )
end

local function installCompleteKantoPokedex()
    local flags = emu.read(0x6000, emu.memType.nesDebug)
    loggedWrite(0x6000, flags | 0x20, "unlock_pokedex_bit5")
    for offset = 0, 18 do
        local value = offset == 18 and 0x7F or 0xFF
        loggedWrite(0x609F + offset, value, "caught_bitmap")
        loggedWrite(0x60B3 + offset, value, "seen_bitmap")
    end
    loggedWrite(0x6031, 151, "seen_counter")
    loggedWrite(0x6032, 151, "caught_counter")
    loggedWrite(0x60C8, 151, "selected_species")
end

local function verifyCompleteKantoPokedex()
    for offset = 0, 18 do
        local expected = offset == 18 and 0x7F or 0xFF
        if emu.read(0x609F + offset, emu.memType.nesDebug) ~= expected then
            return false, "caught bitmap mismatch"
        end
        if emu.read(0x60B3 + offset, emu.memType.nesDebug) ~= expected then
            return false, "seen bitmap mismatch"
        end
    end
    if emu.read(0x6031, emu.memType.nesDebug) ~= 151 then
        return false, "seen counter mismatch"
    end
    if emu.read(0x6032, emu.memType.nesDebug) ~= 151 then
        return false, "caught counter mismatch"
    end
    return true, ""
end

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1
    pulseAt(180, "start", 4)
    for pulseFrame = 360, 4500, 30 do
        pulseAt(pulseFrame, "a", 3)
    end

    pulseAt(4900, "start", 4)
    if frames == 5230 then
        installCompleteKantoPokedex()
    end
    pulseAt(5250, "a", 4)

    if frames ~= 5600 then
        return
    end

    local ok, reason = verifyCompleteKantoPokedex()
    writeBinary("pokedex_151_assisted_screen.png", emu.takeScreenshot())
    writeBinary(
        "pokedex_151_assisted_writes.csv",
        table.concat(writes, "\n") .. "\n"
    )
    if not ok then
        print("POKEMON_POKEDEX_151_ASSISTED_FAIL " .. reason)
        emu.stop(1)
        return
    end

    print(string.format(
        "POKEMON_POKEDEX_151_ASSISTED_PASS mapper=163 region=%s " ..
        "frames=%d seen=151 caught=151 writes=%d mode=assisted",
        tostring(emu.getState()["region"]),
        frames,
        #writes - 1
    ))
    emu.stop(0)
end, emu.eventType.endFrame)
