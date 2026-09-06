-- Assisted renderer proof for three critical pair-6 restorations.
--
-- Three normal introduction pointer references are temporarily redirected to
-- the final Mew/Lorelei, Team Nanjing/Kameiyu and Parlyz Heal payloads.  The
-- game reaches and renders them through controller input.  Only loaded PRG
-- pointer bytes are changed; they are restored before PASS.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

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
local Runtime = dofile(
    directory .. separator .. "critical_restoration_runtime.lua"
)
local runtime = Runtime.new({group = "pair6", expectedCount = 3})
runtime:install()

local frames = 0
local prompts = 0
local lastPromptSignature = nil
local advanceAt = nil
local completedStableFrames = 0
local finished = false
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

local function writeBinary(filename, data)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    file:write(data)
    file:close()
end

local function promptArrowVisible()
    local sprite = 63 * 4
    local y = emu.read(sprite, emu.memType.nesSpriteRam)
    return y >= 190 and y <= 193 and
           emu.read(sprite + 1, emu.memType.nesSpriteRam) == 0xFF and
           emu.read(sprite + 3, emu.memType.nesSpriteRam) == 208
end

local function dialoguePixelSignature()
    local hash = 0
    for y = 165, 203, 2 do
        for x = 40, 199, 2 do
            hash = (hash * 257 + emu.getPixel(x, y)) % 0x100000000
        end
    end
    return hash
end

local function finishPass()
    if finished then
        return
    end
    finished = true
    desiredInput.a = false
    desiredInput.start = false
    if not runtime:restore() then
        error("pair6 critical restoration pointers were not restored")
    end
    writeBinary(
        "critical_restorations_pair6_final_screen.png",
        emu.takeScreenshot()
    )
    runtime:writeReport(
        "critical_restorations_pair6_validation.txt",
        {
            "frames=" .. tostring(frames),
            "prompts=" .. tostring(prompts),
            "result=PASS",
        }
    )
    print(string.format(
        "POKEMON_CRITICAL_RESTORATIONS_PAIR6_PASS mapper=163 region=%s " ..
        "frames=%d payloads=3 prompts=%d " ..
        "mode=assisted_transient_prg_pointer_patch restored=true",
        tostring(emu.getState()["region"]),
        frames,
        prompts
    ))
    emu.stop(0)
end

local function finishFailure(reason)
    if finished then
        return
    end
    finished = true
    desiredInput.a = false
    desiredInput.start = false
    local restored = runtime:restore()
    writeBinary(
        "critical_restorations_pair6_failure_screen.png",
        emu.takeScreenshot()
    )
    runtime:writeReport(
        "critical_restorations_pair6_validation.txt",
        {
            "frames=" .. tostring(frames),
            "prompts=" .. tostring(prompts),
            "failure=" .. tostring(reason),
            "result=FAIL",
        }
    )
    print(
        "POKEMON_CRITICAL_RESTORATIONS_PAIR6_FAIL mapper=163 region=" ..
        tostring(emu.getState()["region"]) ..
        " frames=" .. tostring(frames) ..
        " restored=" .. tostring(restored) ..
        " reason=" .. tostring(reason)
    )
    emu.stop(1)
end

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    if finished then
        return
    end
    frames = frames + 1
    if frames == 180 then
        desiredInput.start = true
    elseif frames == 184 then
        desiredInput.start = false
    elseif frames == 360 then
        desiredInput.a = true
    elseif frames == 364 then
        desiredInput.a = false
    end

    if advanceAt ~= nil then
        if frames == advanceAt then
            desiredInput.a = true
        elseif frames == advanceAt + 3 then
            desiredInput.a = false
            advanceAt = frames + 87
        end
    end

    if frames > 400 and promptArrowVisible() then
        local signature = dialoguePixelSignature()
        if signature ~= lastPromptSignature then
            lastPromptSignature = signature
            prompts = prompts + 1
            advanceAt = frames + 60
        end
    end

    -- A multi-page payload can finish rendering on the frame where the
    -- prompt arrow disappears.  The complete sequence of verified PRG reads
    -- is the renderer proof; do not make PASS depend on the arrow remaining
    -- visible after the terminator has been consumed.
    if runtime:allRead() then
        completedStableFrames = completedStableFrames + 1
        if completedStableFrames >= 3 then
            finishPass()
            return
        end
    else
        completedStableFrames = 0
    end

    if frames == 9000 then
        finishFailure("timeout before all final payload bytes were rendered")
    end
end, emu.eventType.endFrame)
