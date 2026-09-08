-- Cold boot: preserve VERSION on the left, then show the French title menu.
-- These bytes are pinned to the canonical 2015 VERSION tiles, not the candidate.
local out = assert(os.getenv("POKEMON_YELLOW_MESEN_OUTPUT"))
local expected = "0053525257222300ffacadada8dd54770063545663515600f79caba99caea9ff0049555555554900ffb6aaaaaaaab6ff0020a0a060602000f8d858589898d8f80f030000000000001c07010000000000"
local frame = 0
local titleFrame = nil
local menuFrame = nil
local finished = false
local input = {a=false,b=false,start=false,select=false,up=false,down=false,left=false,right=false}
local function screenshot(name)
    local file = assert(io.open(out .. "/" .. name .. ".png", "wb"))
    file:write(emu.takeScreenshot())
    file:close()
end
local function fail(reason)
    screenshot("title_failure")
    print("FRENCH_TITLE_FAIL " .. reason)
    finished = true
    emu.stop(1)
end
local function checkVersion()
    for index = 1, #expected, 2 do
        local address = 0x510 + (index-1)/2
        if emu.read(address, emu.memType.nesChrRam) ~= tonumber(expected:sub(index,index+1),16) then
            return false
        end
    end
    for index = 0, 4 do
        if emu.read(0x21A9+index, emu.memType.nesPpuDebug) ~= 0x51+index then
            return false
        end
    end
    return true
end
emu.addEventCallback(function() emu.setInput(input,0) end, emu.eventType.inputPolled)
emu.addEventCallback(function()
    if finished then return end
    frame = frame + 1
    local state = emu.getState()
    if frame >= 120 and titleFrame == nil and state["ppu.mask.backgroundEnabled"]
       and emu.read(0x21A9,emu.memType.nesPpuDebug) == 0x51 then
        if not checkVersion() then fail("VERSION overwritten"); return end
        screenshot("title_version_jaune")
        titleFrame = frame
    end
    if titleFrame ~= nil and frame == titleFrame+30 then input.start=true end
    if titleFrame ~= nil and frame == titleFrame+34 then input.start=false end
    if titleFrame ~= nil and frame > titleFrame+40 and menuFrame == nil
       and emu.read(0x2267,emu.memType.nesPpuDebug) == 0x30
       and emu.read(0x22A7,emu.memType.nesPpuDebug) == 0x40 then
        if not checkVersion() then fail("menu VERSION overwritten"); return end
        screenshot("menu_version_jaune")
        menuFrame = frame
    end
    if menuFrame ~= nil and frame == menuFrame+15 then input.down=true end
    if menuFrame ~= nil and frame == menuFrame+19 then input.down=false end
    if menuFrame ~= nil and frame == menuFrame+30 then
        if not checkVersion() then fail("cursor VERSION overwritten"); return end
        screenshot("menu_continue")
        print("FRENCH_TITLE_PASS frames=" .. frame .. " region=" .. tostring(state["region"]))
        finished=true
        emu.stop(0)
    end
    if frame >= 600 then fail("timeout") end
end, emu.eventType.endFrame)
