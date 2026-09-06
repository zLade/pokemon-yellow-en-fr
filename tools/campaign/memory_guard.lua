-- Guarded memory access for controller-only and explicitly assisted runs.
--
-- "controller" mode rejects every write.  "assisted" mode requires an exact
-- whitelist match (address, memory type and optional value validator).  Every
-- attempted write, allowed or denied, is journalled.

local MemoryGuard = {}
MemoryGuard.__index = MemoryGuard

local function requireInteger(value, label, minimum, maximum)
    if type(value) ~= "number"
        or value ~= math.floor(value)
        or value < minimum
        or value > maximum
    then
        error(string.format(
            "%s must be an integer in [%d, %d]",
            label,
            minimum,
            maximum
        ), 3)
    end
end

local function shallowCopy(source)
    local copy = {}
    for key, value in pairs(source) do
        copy[key] = value
    end
    return copy
end

local function normalizeWhitelist(entries)
    local normalized = {}
    for index, entry in ipairs(entries or {}) do
        if type(entry) ~= "table" then
            error("whitelist entry " .. index .. " must be a table", 3)
        end
        local first = entry.first or entry.address
        local last = entry.last or first
        requireInteger(first, "whitelist.first", 0, 0xFFFFFF)
        requireInteger(last, "whitelist.last", first, 0xFFFFFF)
        if entry.mem_type == nil then
            error("whitelist.mem_type is required", 3)
        end
        if entry.validate ~= nil and type(entry.validate) ~= "function" then
            error("whitelist.validate must be a function", 3)
        end
        normalized[#normalized + 1] = {
            first = first,
            last = last,
            mem_type = entry.mem_type,
            label = entry.label or string.format(
                "%06X-%06X",
                first,
                last
            ),
            validate = entry.validate,
        }
    end
    return normalized
end

function MemoryGuard.new(options)
    options = options or {}
    local mode = options.mode or "controller"
    if mode ~= "controller" and mode ~= "assisted" then
        error("memory mode must be 'controller' or 'assisted'", 2)
    end
    if options.read ~= nil and type(options.read) ~= "function" then
        error("options.read must be a function", 2)
    end
    if options.write ~= nil and type(options.write) ~= "function" then
        error("options.write must be a function", 2)
    end
    if mode == "assisted" and options.write == nil then
        error("assisted mode requires options.write", 2)
    end
    if options.frame ~= nil and type(options.frame) ~= "function" then
        error("options.frame must be a function", 2)
    end

    return setmetatable({
        _mode = mode,
        _read = options.read,
        _write = options.write,
        _frame = options.frame or function()
            return 0
        end,
        _deny_raises = options.deny_raises ~= false,
        _whitelist = normalizeWhitelist(options.whitelist),
        _journal = {},
    }, MemoryGuard)
end

function MemoryGuard:mode()
    return self._mode
end

function MemoryGuard:_matching_entry(address, memoryType)
    for _, entry in ipairs(self._whitelist) do
        if address >= entry.first
            and address <= entry.last
            and memoryType == entry.mem_type
        then
            return entry
        end
    end
    return nil
end

function MemoryGuard:_record(row)
    row.frame = self._frame()
    row.mode = self._mode
    self._journal[#self._journal + 1] = row
end

function MemoryGuard:_deny(
    address,
    value,
    memoryType,
    reason,
    denial,
    before
)
    self:_record({
        allowed = false,
        address = address,
        before = before,
        after = value,
        mem_type = memoryType,
        reason = reason,
        denial = denial,
    })
    if self._deny_raises then
        error("memory write denied: " .. denial, 3)
    end
    return false, denial
end

function MemoryGuard:read(address, memoryType)
    requireInteger(address, "address", 0, 0xFFFFFF)
    if self._read == nil then
        error("no memory reader configured", 2)
    end
    return self._read(address, memoryType)
end

function MemoryGuard:write(address, value, memoryType, reason)
    requireInteger(address, "address", 0, 0xFFFFFF)
    requireInteger(value, "value", 0, 0xFF)
    reason = reason or "unspecified"

    if self._mode == "controller" then
        return self:_deny(
            address,
            value,
            memoryType,
            reason,
            "controller mode is read-only",
            nil
        )
    end

    local entry = self:_matching_entry(address, memoryType)
    if entry == nil then
        return self:_deny(
            address,
            value,
            memoryType,
            reason,
            "address or memory type is not whitelisted",
            nil
        )
    end

    local before = nil
    if self._read ~= nil then
        before = self._read(address, memoryType)
    end
    if entry.validate ~= nil then
        local ok, accepted, validationMessage = pcall(
            entry.validate,
            address,
            value,
            before
        )
        if not ok then
            return self:_deny(
                address,
                value,
                memoryType,
                reason,
                "whitelist validator error: " .. tostring(accepted),
                before
            )
        end
        if not accepted then
            return self:_deny(
                address,
                value,
                memoryType,
                reason,
                validationMessage or "value rejected by whitelist",
                before
            )
        end
    end

    self._write(address, value, memoryType)
    self:_record({
        allowed = true,
        address = address,
        before = before,
        after = value,
        mem_type = memoryType,
        reason = reason,
        whitelist = entry.label,
    })
    return true
end

function MemoryGuard:get_journal()
    local copy = {}
    for index, row in ipairs(self._journal) do
        copy[index] = shallowCopy(row)
    end
    return copy
end

local function printable(value)
    if value == nil then
        return "-"
    end
    return tostring(value):gsub("[\t\r\n]", " ")
end

local function hexByte(value)
    if value == nil then
        return "-"
    end
    return string.format("%02X", value)
end

function MemoryGuard:format_journal()
    local lines = {
        "frame\tmode\tallowed\taddress\tbefore\tafter\tmemory_type"
            .. "\treason\twhitelist\tdenial",
    }
    for _, row in ipairs(self._journal) do
        lines[#lines + 1] = table.concat({
            printable(row.frame),
            printable(row.mode),
            row.allowed and "1" or "0",
            string.format("%06X", row.address),
            hexByte(row.before),
            hexByte(row.after),
            printable(row.mem_type),
            printable(row.reason),
            printable(row.whitelist),
            printable(row.denial),
        }, "\t")
    end
    return table.concat(lines, "\n") .. "\n"
end

function MemoryGuard:write_journal(path)
    local file = assert(io.open(path, "wb"))
    file:write(self:format_journal())
    file:close()
end

return MemoryGuard
