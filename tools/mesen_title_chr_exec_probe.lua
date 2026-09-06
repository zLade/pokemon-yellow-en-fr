-- Detect whether title CHR source bytes are also executed as 6502 code.
--
-- Mapper 163 maps 32 KiB PRG banks.  In title bank 14, the raw CHR source
-- starts at CPU $859B; the original NEW and LOAD tile bytes correspond to
-- $889B-$88CA and $899B-$89DA.  This passive execution probe records every
-- instruction fetch in those ranges while entering the title menu.

local frames = 0
local hits = {}
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

local function record(address)
    local entry = hits[address]
    if entry == nil then
        hits[address] = { count = 1, firstFrame = frames }
    else
        entry.count = entry.count + 1
    end
end

emu.addMemoryCallback(
    function(address)
        record(address)
    end,
    emu.callbackType.exec,
    0x889B,
    0x89DA
)

emu.addEventCallback(function()
    emu.setInput(desiredInput, 0)
end, emu.eventType.inputPolled)

emu.addEventCallback(function()
    frames = frames + 1
    if frames == 180 then
        desiredInput.start = true
    elseif frames == 184 then
        desiredInput.start = false
    elseif frames == 600 then
        local addresses = {}
        for address in pairs(hits) do
            addresses[#addresses + 1] = address
        end
        table.sort(addresses)

        local total = 0
        local trace = {}
        for _, address in ipairs(addresses) do
            local entry = hits[address]
            total = total + entry.count
            trace[#trace + 1] = string.format(
                "$%04X:%d@%d",
                address,
                entry.count,
                entry.firstFrame
            )
        end
        print(
            string.format(
                "TITLE_CHR_EXEC_PASS mapper=163 region=%s frames=%d " ..
                "distinct=%d total=%d trace=%s",
                tostring(emu.getState()["region"]),
                frames,
                #addresses,
                total,
                table.concat(trace, ",")
            )
        )
        emu.stop(0)
    end
end, emu.eventType.endFrame)
