-- Exact title probe for the reviewed YELLOW VERSION screen and
-- the personalized English 2.0 credit row.
local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local function bytesFromHex(value)
    local result = {}
    for index = 1, #value, 2 do
        result[#result + 1] = tonumber(value:sub(index, index + 1), 16)
    end
    return result
end

local expectedTiles = {
    { 0x0510, "00020202010101000705050502020203" },
    { 0x0520, "009A92923A121B00FF656D6DC5EDA4BF" },
    { 0x0530, "00444A4A4A4A6400EFBBB5B5B5B59BFE" },
    { 0x0540, "00A8A8A8F8505000FC54545404ACA8F8" },
    { 0x0550, "0F030000000000001C07010000000000" },
    { 0x1660, "00000000000000000000000000000000" },
    { 0x1780, "00000000000000000000000000000000" },
    { 0x18C0, "00000000000000000000000000000000" },
    { 0x1910, "00000000000000000000000000000000" },
    { 0x1920, "00222222223B000000222222223B0000" },
    { 0x1930, "00BB929292BB000000BB929292BB0000" },
    { 0x1940, "00BB28BBAAAB000000BB28BBAAAB0000" },
    { 0x1950, "00BBAAAA2ABB000000BBAAAA2ABB0000" },
    { 0x1960, "00B8A8B88ABA000000B8A8B88ABA0000" },
    { 0x1970, "000E0204080E0000000E0204080E0000" },
    { 0x1980, "008E8A8E8AEA0000008E8A8E8AEA0000" },
    { 0x1990, "00CEA8ACA8CE000000CEA8ACA8CE0000" },
    { 0x19A0, "00030202828300000003020282830000" },
    { 0x19B0, "00AB2A3B2AAA000000AB2A3B2AAA0000" },
    { 0x19C0, "003AA231223A0000003AA231223A0000" },
    { 0x19D0, "00B8A828A8B8000000B8A828A8B80000" },
    { 0x1A00, "00000000000000000000000000000000" },
    { 0x1A10, "00000000000000000000000000000000" },
    { 0x1A20, "00000000000000000000000000000000" },
    { 0x1A30, "00000000000000000000000000000000" },
}
for _, item in ipairs(expectedTiles) do item[2] = bytesFromHex(item[2]) end

local frames = 0
local stable = 0
local signature = nil
local finished = false
local titleValidated = false
local startFrame = nil
local desiredInput = { a=false, b=false, select=false, start=false, up=false, down=false, left=false, right=false }

local function checksum(first, last)
    local value = 0
    for address = first, last do
        value = (value * 257 + emu.read(address, emu.memType.nesChrRam)) % 0x100000000
    end
    return value
end

local function fail(reason)
    if finished then return end
    finished = true
    local file = assert(io.open(outputDirectory .. "\\title_yellow_version_failure.png", "wb"))
    file:write(emu.takeScreenshot()); file:close()
    print("TITLE_YELLOW_VERSION_FAIL mapper=163 frame=" .. frames .. " reason=" .. reason)
    emu.stop(1)
end

local function validateExpectedTiles()
    for _, item in ipairs(expectedTiles) do
        for index, expected in ipairs(item[2]) do
            local actual = emu.read(item[1] + index - 1, emu.memType.nesChrRam)
            if actual ~= expected then
                return string.format("tile=$%04X actual=$%02X expected=$%02X", item[1] + index - 1, actual, expected)
            end
        end
    end
    return nil
end

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if finished then return end
    frames = frames + 1
    local state = emu.getState()
    local titlePresent = emu.read(0x204E, emu.memType.nesPpuDebug) == 0x40 and
        emu.read(0x21A9, emu.memType.nesPpuDebug) == 0x51 and
        emu.read(0x22E6, emu.memType.nesPpuDebug) == 0x66 and
        emu.read(0x22F9, emu.memType.nesPpuDebug) == 0xA3
    if not titleValidated and frames >= 60 and titlePresent and state["ppu.mask.backgroundEnabled"] then
        local current = checksum(0, 0x1FFF)
        if current == signature then stable = stable + 1 else signature = current; stable = 1 end
        if stable >= 3 then
            local mismatch = validateExpectedTiles()
            if mismatch ~= nil then fail(mismatch); return end
            local file = assert(io.open(outputDirectory .. "\\title_yellow_version_screen.png", "wb"))
            file:write(emu.takeScreenshot()); file:close()
            titleValidated = true
            startFrame = frames + 30
        end
    end
    if startFrame ~= nil and frames == startFrame then desiredInput.start = true end
    if startFrame ~= nil and frames == startFrame + 4 then desiredInput.start = false end
    local menuPresent = emu.read(0x2267, emu.memType.nesPpuDebug) == 0x30 and
        emu.read(0x2268, emu.memType.nesPpuDebug) == 0x31 and
        emu.read(0x2269, emu.memType.nesPpuDebug) == 0x32 and
        emu.read(0x22A7, emu.memType.nesPpuDebug) == 0x40 and
        emu.read(0x22AA, emu.memType.nesPpuDebug) == 0x43
    if titleValidated and frames > startFrame + 4 and menuPresent then
        local mismatch = validateExpectedTiles()
        if mismatch ~= nil then fail("menu_" .. mismatch); return end
        local file = assert(io.open(outputDirectory .. "\\title_yellow_version_menu_screen.png", "wb"))
        file:write(emu.takeScreenshot()); file:close()
        finished = true
        print("TITLE_YELLOW_VERSION_PASS mapper=163 region=" .. tostring(state["region"]) .. " frames=" .. frames .. " menu=NEW_LOAD credits=LUIGA2009_ZLADE_CHPEXO")
        emu.stop(0)
    end
    if frames == 1200 then fail("timeout") end
end, emu.eventType.endFrame)
