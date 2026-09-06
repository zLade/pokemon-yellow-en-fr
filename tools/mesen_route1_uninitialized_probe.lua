-- Diagnostic wrapper: identify the CPU instruction that reads the strict-
-- debug uninitialized range during the Route 1 continuation.  This probe is
-- read-only and delegates the actual scenario to the certified bridge.

local seen = {}

local source = debug.getinfo(1, "S").source or ""
if source:sub(1, 1) == "@" then
    source = source:sub(2)
end
local directory = source:match("^(.*)[/\\][^/\\]+$")
if directory == nil or directory == "" then
    error("cannot determine script directory")
end
local separator = directory:find("\\", 1, true) and "\\" or "/"
local function loadModule(filename)
    return dofile(directory .. separator .. filename)
end

local function mappedMemoryName(memoryType)
    if memoryType == emu.memType.nesPrgRom then
        return "nesPrgRom"
    elseif memoryType == emu.memType.nesInternalRam then
        return "nesInternalRam"
    elseif memoryType == emu.memType.nesWorkRam then
        return "nesWorkRam"
    elseif memoryType == emu.memType.nesSaveRam then
        return "nesSaveRam"
    end
    return "other"
end

emu.addMemoryCallback(function(address)
    if address ~= 0x0161
        and address ~= 0x01C6
        and address ~= 0x01C7
    then
        return
    end
    local state = emu.getState()
    local pc = state["cpu.pc"] or 0
    local key = string.format("%04X:%04X", address, pc)
    if seen[key] then
        return
    end
    seen[key] = true
    local converted = emu.convertAddress(pc, emu.memType.nesMemory)
    local mappedOffset = -1
    local mappedType = "nil"
    local convertedDescription = "nil"
    if converted ~= nil then
        local parts = {}
        for key, value in pairs(converted) do
            parts[#parts + 1] = tostring(key) .. "=" .. tostring(value)
        end
        table.sort(parts)
        convertedDescription = table.concat(parts, ",")
        mappedType = mappedMemoryName(converted.memType)
    end
    if converted ~= nil and converted.address ~= nil then
        mappedOffset = converted.address
    end
    local sourcePointer =
        emu.read(0x0002, emu.memType.nesDebug)
        | (emu.read(0x0003, emu.memType.nesDebug) << 8)
    print(string.format(
        "POKEMON_UNINIT_READ_TRACE address=$%04X pc=$%04X " ..
            "mapped_offset=$%06X mapped_type=%s " ..
            "a=$%02X x=$%02X y=$%02X sp=$%02X " ..
            "source_pointer=$%04X absolute_frame=%s converted=%s",
        address,
        pc,
        mappedOffset,
        mappedType,
        state["cpu.a"] or 0,
        state["cpu.x"] or 0,
        state["cpu.y"] or 0,
        state["cpu.sp"] or 0,
        sourcePointer,
        tostring(rawget(_G, "POKEMON_FM3_ROUTE1_ABSOLUTE_FRAME") or ""),
        convertedDescription
    ))
end, emu.callbackType.read, 0x0161, 0x01C7)

loadModule("mesen_fm3_route1_viridian_after_prototype.lua")
