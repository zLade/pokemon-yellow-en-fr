-- Capture the first five complete intro dialogue pages at the game's real
-- input prompt.
--
-- The dialogue wait arrow is sprite 63 at (208, 191), using tile $FF.
-- Capturing on this OAM invariant avoids arbitrary screenshots while text is
-- still printing or the two-line box is scrolling.  The signature is taken
-- from the rendered dialogue pixels and excludes the animated arrow.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local frames = 0
local nmiCount = 0
local promptCount = 0
local advanceAt = nil
local lastPromptSignature = nil
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

local function memoryBytes(memoryType, first, last)
    local chunks = {}
    local chunk = {}
    for address = first, last do
        chunk[#chunk + 1] = string.char(emu.read(address, memoryType))
        if #chunk == 512 then
            chunks[#chunks + 1] = table.concat(chunk)
            chunk = {}
        end
    end
    if #chunk > 0 then
        chunks[#chunks + 1] = table.concat(chunk)
    end
    return table.concat(chunks)
end

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

local function capturePrompt(signature)
    local nametable = memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
    if signature == lastPromptSignature then
        return false
    end
    lastPromptSignature = signature
    promptCount = promptCount + 1
    local prefix = string.format(
        "intro_prompt_%02d_frame_%04d",
        promptCount,
        frames
    )
    local screenshot = emu.takeScreenshot()
    writeBinary(prefix .. ".png", screenshot)
    writeBinary(prefix .. "_nametable_4k.bin", nametable)
    writeBinary(
        prefix .. "_oam_256.bin",
        memoryBytes(emu.memType.nesSpriteRam, 0x00, 0xFF)
    )
    print(string.format(
        "POKEMON_INTRO_PROMPT_CAPTURE index=%d frame=%d pngBytes=%d",
        promptCount,
        frames,
        #screenshot
    ))
    return true
end

emu.addEventCallback(function()
    nmiCount = nmiCount + 1
end, emu.eventType.nmi)

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1

    if frames == 180 then
        desiredInput.start = true
    elseif frames == 184 then
        desiredInput.start = false
    elseif frames == 360 then
        -- Select NOUV/new game after the title menu is fully rendered.
        desiredInput.a = true
    elseif frames == 364 then
        desiredInput.a = false
    end

    if advanceAt ~= nil then
        if frames == advanceAt then
            desiredInput.a = true
        elseif frames == advanceAt + 3 then
            desiredInput.a = false
            -- Some end-of-block prompts need another confirmation after the
            -- two-line page is dismissed.  Retry at a human-safe cadence
            -- while the same wait arrow remains visible.
            advanceAt = frames + 87
        end
    end

    local promptVisible = frames > 400 and promptArrowVisible()
    if promptVisible then
        local signature = dialoguePixelSignature()
        if capturePrompt(signature) then
            -- Match the proven human-safe cadence used by the broad intro
            -- smoke test, while leaving the completed page visible long
            -- enough for a deterministic capture.
            advanceAt = frames + 60
        end
    end
    if promptCount >= 5 and not finished then
        finished = true
        print(string.format(
            "POKEMON_INTRO_PROMPTS_PASS mapper=163 region=%s frames=%d " ..
            "nmi=%d prompts=%d",
            tostring(emu.getState()["region"]),
            frames,
            nmiCount,
            promptCount
        ))
        emu.stop(0)
    elseif frames == 3000 then
        writeBinary("intro_prompt_timeout.png", emu.takeScreenshot())
        writeBinary(
            "intro_prompt_timeout_oam_256.bin",
            memoryBytes(emu.memType.nesSpriteRam, 0x00, 0xFF)
        )
        writeBinary(
            "intro_prompt_timeout_nametable_4k.bin",
            memoryBytes(emu.memType.nesPpuDebug, 0x2000, 0x2FFF)
        )
        print(string.format(
            "POKEMON_INTRO_PROMPTS_FAIL mapper=163 region=%s frames=%d " ..
            "nmi=%d prompts=%d",
            tostring(emu.getState()["region"]),
            frames,
            nmiCount,
            promptCount
        ))
        emu.stop(1)
    end
end, emu.eventType.endFrame)
